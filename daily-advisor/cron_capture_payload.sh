#!/usr/bin/env bash
# fa_scan capture wrapper — runs daily fa-scan with --capture-payload, then
# auto-commits new fixtures back to git so spike runner can consume them.
#
# Issue 008 (SP B1 cutover spike fixture baseline) followup: cron-side glue
# so VPS-captured payloads land in the repo without manual sync.
#
# Cron usage (replaces the original `python3 daily-advisor/fa_scan.py ...` line):
#   30 4 * * * root <env-setup> && bash /opt/mlb-fantasy/daily-advisor/cron_capture_payload.sh
#
# Logs:
#   - fa_scan stdout/stderr → /var/log/fa-scan.log (unchanged)
#   - wrapper status        → /var/log/fa-scan-capture.log

set -uo pipefail

REPO=/opt/mlb-fantasy
FIXTURE_REL=daily-advisor/_tools/fixtures/b1_baseline
FIXTURE_ABS="$REPO/$FIXTURE_REL"
FA_LOG=/var/log/fa-scan.log
WRAP_LOG=/var/log/fa-scan-capture.log

ts() { date '+%F %T %Z'; }
log() { echo "[$(ts)] $*" >> "$WRAP_LOG"; }

cd "$REPO" || { log "FATAL: cd $REPO failed"; exit 1; }

log "=== fa_scan capture run start ==="

python3 daily-advisor/fa_scan.py --capture-payload "$FIXTURE_ABS" >> "$FA_LOG" 2>&1
fa_rc=$?

if [ $fa_rc -ne 0 ]; then
    log "fa_scan exited $fa_rc — fixture push skipped"
    exit $fa_rc
fi

new_files=$(git status --porcelain -- "$FIXTURE_REL" 2>/dev/null)
if [ -z "$new_files" ]; then
    log "no new/modified fixture in $FIXTURE_REL — nothing to push"
    exit 0
fi

log "fixture changes detected:"
echo "$new_files" >> "$WRAP_LOG"

# Sync before push to avoid conflict with concurrent commits (waiver-log
# auto-update, etc). fa_scan already pulled at startup but the cron tail
# may have produced upstream changes since. Delegates to git_sync.py, which
# auto-recovers harmless untracked-file collisions (identical-content shadow
# files) and aborts loudly on real divergence — see docs/handoff-vps-git-sync-fix.md.
if ! python3 daily-advisor/git_sync.py "$REPO" >> "$WRAP_LOG" 2>&1; then
    log "git pull --rebase failed (collision recovery did not resolve) — manual fix needed"
    exit 2
fi

git add "$FIXTURE_REL" >> "$WRAP_LOG" 2>&1
today=$(date '+%Y-%m-%d')
if ! git commit -m "chore(b1-baseline): capture fixture $today" >> "$WRAP_LOG" 2>&1; then
    log "git commit failed (race? nothing staged after pull?) — exit clean"
    exit 0
fi

if ! git push origin master >> "$WRAP_LOG" 2>&1; then
    log "git push failed — manual intervention needed"
    exit 3
fi

log "fixture committed + pushed OK"
