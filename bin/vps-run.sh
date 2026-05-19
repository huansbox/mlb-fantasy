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
# Usage:  bash bin/vps-run.sh [--no-retry] '<remote command>'
#   --no-retry   single attempt, no retry. Use for commands with side effects
#                (writes / git): a timeout can kill the local ssh while the
#                remote command keeps running, so a retry could double-run it.
#                Read-only commands (the *_scan.py scans) are idempotent and
#                safe to retry.
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
# Retry messages go to stderr, so stdout stays exactly the remote command's
# stdout (skills parse it as JSON).
set -u

VPS_HOST="root@107.175.30.172"
TIMEOUT="${VPS_RUN_TIMEOUT:-90}"
TRIES="${VPS_RUN_TRIES:-3}"

if [ "${1:-}" = "--no-retry" ]; then
  TRIES=1
  shift
fi

if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  echo "vps-run: usage: bash bin/vps-run.sh [--no-retry] '<remote command>'" >&2
  exit 2
fi
REMOTE_CMD="$1"

attempt=1
while : ; do
  timeout -k 5 "$TIMEOUT" ssh \
    -o ConnectTimeout=15 -o BatchMode=yes \
    -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
    "$VPS_HOST" "$REMOTE_CMD"
  rc=$?

  # 124 = timed out, 137 = SIGKILL after -k, 255 = ssh connection error.
  # Anything else (0 success, or 1-254 genuine remote exit) -> done.
  case "$rc" in
    124|137|255) : ;;  # retryable
    *) exit "$rc" ;;
  esac

  if [ "$attempt" -ge "$TRIES" ]; then
    echo "vps-run: failed after ${attempt} attempt(s), last exit ${rc} (SSH hang/error — lossy path)" >&2
    exit "$rc"
  fi
  echo "vps-run: attempt ${attempt} hit exit ${rc} (SSH hang/error), retrying ($((attempt + 1))/${TRIES})..." >&2
  attempt=$((attempt + 1))
  sleep 3
done
