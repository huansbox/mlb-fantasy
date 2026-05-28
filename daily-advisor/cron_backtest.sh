#!/usr/bin/env bash
# cron_backtest.sh — weekly B2 SP backtest auto-update wrapper.
#
# Runs backtest_track.py --days 7 --update-doc, then commits any change to
# docs/sp-decisions-backtest.md back to git so the result is visible from
# local checkouts without manual VPS pulls.
#
# Issue 024 shipped the script; issue 025 wires the cron entry. Mirrors
# cron_capture_payload.sh pattern (pull-rebase via git_sync.py, run, commit,
# push, fail loud on push collision).
#
# Cron usage (weekly Sunday, paired with /weekly-review cadence):
#   0 6 * * 0 root <env-setup> && bash /opt/mlb-fantasy/daily-advisor/cron_backtest.sh
#
# Logs:
#   - backtest_track stdout/stderr → /var/log/sp-backtest.log
#   - wrapper status               → /var/log/sp-backtest-wrap.log

set -uo pipefail

REPO=/opt/mlb-fantasy
BACKTEST_DOC=docs/sp-decisions-backtest.md
RUN_LOG=/var/log/sp-backtest.log
WRAP_LOG=/var/log/sp-backtest-wrap.log

ts() { date '+%F %T %Z'; }
log() { echo "[$(ts)] $*" >> "$WRAP_LOG"; }

cd "$REPO" || { log "FATAL: cd $REPO failed"; exit 1; }

log "=== backtest wrapper start ==="

# Pull first — pick up any concurrent VPS commits (waiver-log auto-update,
# fa-scan fixture push) so our commit lands on fresh HEAD.
if ! python3 daily-advisor/git_sync.py "$REPO" >> "$WRAP_LOG" 2>&1; then
    log "git pull --rebase failed (collision recovery did not resolve) — exiting"
    exit 2
fi

python3 daily-advisor/backtest_track.py --days 7 --update-doc >> "$RUN_LOG" 2>&1
bt_rc=$?

if [ $bt_rc -ne 0 ]; then
    log "backtest_track exited $bt_rc — no commit"
    exit $bt_rc
fi

changes=$(git status --porcelain -- "$BACKTEST_DOC" 2>/dev/null)
if [ -z "$changes" ]; then
    log "no change to $BACKTEST_DOC — nothing to commit"
    exit 0
fi

log "backtest doc changed:"
echo "$changes" >> "$WRAP_LOG"

git add "$BACKTEST_DOC" >> "$WRAP_LOG" 2>&1
today=$(date '+%Y-%m-%d')
if ! git commit -m "chore(sp-backtest): weekly auto-update $today" >> "$WRAP_LOG" 2>&1; then
    log "git commit failed (race? nothing staged after pull?) — exit clean"
    exit 0
fi

if ! git push origin master >> "$WRAP_LOG" 2>&1; then
    log "git push failed — manual intervention needed"
    exit 3
fi

log "backtest committed + pushed OK"
