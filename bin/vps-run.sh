#!/usr/bin/env bash
# vps-run.sh — run a command on the VPS over SSH, surviving the lossy network
# path between this machine and the VPS.
#
# Background: the path has intermittent bidirectional packet loss (root cause
# confirmed 2026-05-19, see issues/vps-ssh-handshake-hang.md). An SSH handshake
# that lands in a lossy burst hangs ~30-40s and will NOT self-recover within a
# useful window; but a fresh connection a few seconds later usually lands in a
# clean window. So: kill a stuck attempt with `timeout`, then retry.
#
# What actually kills a hung handshake is the outer `timeout` — NOT the ssh
# options below. `-o ConnectTimeout` only covers TCP connect (the hang is
# post-connect, in KEX/userauth); `-o ServerAlive*` only runs once the session
# is established (after userauth). They guard other, lesser failure modes;
# the handshake hang is handled solely by `timeout`.
#
# Usage:  bash bin/vps-run.sh [--no-retry] [--] '<remote command>'
#   --no-retry   single attempt, no retry. Use for commands with side effects
#                (writes / git): a timeout can kill the local ssh while the
#                remote command keeps running, so a retry could double-run it.
#                NOTE: --no-retry only stops THIS wrapper from retrying. It
#                cannot stop a caller from re-invoking after a timeout — for
#                side-effecting commands the caller must still check state
#                (e.g. did the file/commit land?) before re-running.
#   --           end of options; everything after is the remote command.
#
# Env overrides:
#   VPS_RUN_TIMEOUT   per-attempt timeout in seconds (default 90 — above any
#                     legitimate command runtime, so only true hangs get cut)
#   VPS_RUN_TRIES     max attempts including the first (default 3)
#
# Exit code: the remote command's exit code on success or on a genuine remote
# failure (1-123/125-254 — NOT retried, retrying won't fix a real failure).
# 124 if every attempt timed out; 255 if every attempt hit an SSH error.
#
# stdout: buffered per attempt and emitted only for the final (non-retryable)
# result, so a partial dump from a timed-out attempt can't be concatenated
# ahead of the good output. Retry notices and ssh's own diagnostics go to
# stderr, so stdout stays exactly the remote command's stdout.
set -u

VPS_HOST="root@107.175.30.172"
TIMEOUT="${VPS_RUN_TIMEOUT:-90}"
TRIES="${VPS_RUN_TRIES:-3}"

# `timeout` is GNU coreutils — present on Linux and git-bash, but NOT on macOS
# by default (there it is `gtimeout`, from `brew install coreutils`).
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN=timeout
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN=gtimeout
else
  echo "vps-run: needs 'timeout' (Linux/git-bash) or 'gtimeout' (macOS: brew install coreutils)" >&2
  exit 2
fi

if [ "${1:-}" = "--no-retry" ]; then
  TRIES=1
  shift
fi
[ "${1:-}" = "--" ] && shift

if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  echo "vps-run: usage: bash bin/vps-run.sh [--no-retry] [--] '<remote command>'" >&2
  exit 2
fi
REMOTE_CMD="$1"

attempt=1
while : ; do
  # stdout captured; stderr left to stream live (ssh diagnostics stay visible).
  out=$("$TIMEOUT_BIN" -k 5 "$TIMEOUT" ssh \
    -o ConnectTimeout=15 -o BatchMode=yes \
    -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
    "$VPS_HOST" "$REMOTE_CMD")
  rc=$?

  # Retryable: 124 = timed out (SIGTERM), 137 = SIGKILL after `-k`, 255 = ssh
  # error. NOTE 255 is ambiguous — it is also what ssh returns if the remote
  # command itself exits 255; we cannot tell them apart, so an unrecoverable
  # ssh error (host key changed, auth failure) will still be retried up to
  # TRIES times. BatchMode makes those fail fast, so the wasted time is small.
  # Anything else (0 success, or 1-254 genuine remote exit) -> done.
  case "$rc" in
    124|137|255) : ;;  # retryable
    *) printf '%s\n' "$out"; exit "$rc" ;;
  esac

  if [ "$attempt" -ge "$TRIES" ]; then
    echo "vps-run: failed after ${attempt} attempt(s), last exit ${rc} — SSH hang or error (lossy path, or a non-network ssh failure; check ssh output above)" >&2
    exit "$rc"
  fi
  echo "vps-run: attempt ${attempt} hit exit ${rc} (SSH hang/error), retrying ($((attempt + 1))/${TRIES})..." >&2
  attempt=$((attempt + 1))
  sleep 3
done
