#!/usr/bin/env bash
# cron_backtest.sh — weekly decision-backtest auto-update wrapper (SP + batter).
#
# Runs backtest_track.py --update-doc (SP) and backtest_batter.py --update-doc
# (batter, issue 029) in one Sunday pass. Both use the default reconciliation
# window (episode age [21, 28) days; weekly Sunday stride 7 means each episode
# is reconciled exactly once, after its 21-day observation window elapsed),
# then any change to either backtest doc is committed back to git so results
# are visible from local checkouts without manual VPS pulls.
#
# Issue 024 shipped the SP script; issue 025 wired the cron entry; issue 027
# repaired the SP parse/outcome/age holes; issue 029 added the batter side.
# Mirrors cron_capture_payload.sh pattern (pull-rebase via git_sync.py, run,
# commit, push, fail loud on push collision).
#
# Cron usage (weekly Sunday, paired with /weekly-review cadence):
#   0 6 * * 0 root <env-setup> && bash /opt/mlb-fantasy/daily-advisor/cron_backtest.sh
#
# Logs:
#   - backtest stdout/stderr → /var/log/sp-backtest.log
#   - wrapper status         → /var/log/sp-backtest-wrap.log
#
# Exit codes: 0 ok (including partial-side failure with the other side
# committed) / 2 pull failure / 3 push failure / N both sides failed
# (SP's exit code).

set -uo pipefail

REPO=/opt/mlb-fantasy
SP_DOC=docs/sp-decisions-backtest.md
BATTER_DOC=docs/batter-decisions-backtest.md
RUN_LOG=/var/log/sp-backtest.log
WRAP_LOG=/var/log/sp-backtest-wrap.log

ts() { date '+%F %T %Z'; }
log() { echo "[$(ts)] $*" >> "$WRAP_LOG"; }

cd "$REPO" || { log "FATAL: cd $REPO failed"; exit 1; }

log "=== backtest wrapper start (SP + batter) ==="

# Pull first — pick up any concurrent VPS commits (waiver-log auto-update,
# fa-scan fixture push) so our commit lands on fresh HEAD.
if ! python3 daily-advisor/git_sync.py "$REPO" >> "$WRAP_LOG" 2>&1; then
    log "git pull --rebase failed (collision recovery did not resolve) — exiting"
    exit 2
fi

python3 daily-advisor/backtest_track.py --update-doc >> "$RUN_LOG" 2>&1
sp_rc=$?
[ $sp_rc -ne 0 ] && log "backtest_track (SP) exited $sp_rc"

python3 daily-advisor/backtest_batter.py --update-doc >> "$RUN_LOG" 2>&1
batter_rc=$?
[ $batter_rc -ne 0 ] && log "backtest_batter exited $batter_rc"

if [ $sp_rc -ne 0 ] && [ $batter_rc -ne 0 ]; then
    log "both sides failed — no commit"
    exit $sp_rc
fi

changes=$(git status --porcelain -- "$SP_DOC" "$BATTER_DOC" 2>/dev/null)
if [ -z "$changes" ]; then
    log "no change to backtest docs — nothing to commit"
    exit 0
fi

log "backtest docs changed:"
echo "$changes" >> "$WRAP_LOG"

git add "$SP_DOC" "$BATTER_DOC" >> "$WRAP_LOG" 2>&1
today=$(date '+%Y-%m-%d')
if ! git commit -m "chore(backtest): weekly auto-update $today (SP + batter)" >> "$WRAP_LOG" 2>&1; then
    log "git commit failed (race? nothing staged after pull?) — exit clean"
    exit 0
fi

if ! git push origin master >> "$WRAP_LOG" 2>&1; then
    log "git push failed — manual intervention needed"
    exit 3
fi

log "backtest committed + pushed OK"
