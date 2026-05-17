# Agent Handoff

This file is the durable handoff note for Codex sessions taking over this repo.
It records confirmed operating rules and current exploration findings. Treat it
as a map, not as a substitute for reading code and recent production output.

## Operating Rules

- Core product: `daily-advisor` daily reports and FA scans.
- Treat docs as clues, not facts. If docs, code, and recent production output
  conflict, list the conflict and ask the user one plain-language question with
  a recommendation.
- Ask the user one question at a time.
- Prefer read-only exploration first. Run `--help`, dry-runs, compile checks,
  and tests before any live task.
- Do not automatically execute Yahoo state-changing operations: waiver claims,
  add/drop, trades, or anything that changes league state.
- Do not print secrets. It is OK to check whether env/token files exist or use
  them for minimal validation, but never echo token contents.
- Local repo is development/dry-run:
  `/Users/linshuhuan/mywork/mlb-fantasy`.
- VPS `/opt/mlb-fantasy` is production.
- GitHub Issues may be read as production output baselines. Default is read-only:
  no comments, labels, closes, or mutations unless explicitly asked.

## Confirmed League Rules

- H2H One Win uses majority rule.
- `7-5-2` is a win.
- `6-6-2` is a tie.
- `README.md` currently says `8+`; that statement is stale/incorrect.

## Current Production Baselines

Latest FA scan baselines checked during 2026-05-17 exploration:

- GitHub Issue `#207`: `[FA Scan 打者] 2026-05-17`
- GitHub Issue `#208`: `[FA Scan SP-v4] 2026-05-17`

Use recent GitHub Issues first when validating production output shape, because
they show what the cron/VPS pipeline actually produced.

## Local Environment Findings

- Default local `python3` is macOS Python 3.9.6 at `/usr/bin/python3`.
- Parts of `daily-advisor` require newer Python syntax such as `dict | None`.
- Local Python 3.12 exists at:
  `/Users/linshuhuan/.local/bin/python3.12`
- Python 3.12 compile check passed:
  `/Users/linshuhuan/.local/bin/python3.12 -m compileall -q daily-advisor`
- Python 3.12 currently does not have `pytest` installed.
- Default Python 3.9 has `pytest 8.4.2`, but it is not the intended runtime for
  files using newer syntax.
- No local `daily-advisor/.env` or `daily-advisor/yahoo_token.json` was found
  during exploration. Only `daily-advisor/.env.example` exists.

## Command Safety Map

| Command | Current understanding |
| --- | --- |
| `python3 daily-advisor/daily_advisor.py --help` | Safe; no external calls. |
| `/Users/linshuhuan/.local/bin/python3.12 daily-advisor/fa_scan.py --help` | Safe after the `%owned` argparse fix. |
| `/Users/linshuhuan/.local/bin/python3.12 -m compileall -q daily-advisor` | Safe syntax check; no API calls. |
| `daily_advisor.py --dry-run` | Skips Claude and Telegram after building the data summary, but may fetch Yahoo/MLB/Savant data depending on available env/token. |
| `daily_advisor.py --no-send` | Runs Claude, prints advice, skips GitHub Issue and Telegram. |
| `fa_scan.py --dry-run` | Skips Claude, Telegram, GitHub Issue, and waiver-log updates. Still refreshes Yahoo token, queries Yahoo, downloads Savant, checks watchlist ownership, and writes ignored local `fa_history.json`. |
| `roster_sync.py --dry-run` | Skips pre-edit git pull, config write, git commit/push, and notification. Still refreshes Yahoo token and queries Yahoo. |
| `weekly_review.py --prepare --dry-run` | Skips file write and git push. Still refreshes Yahoo token and queries Yahoo/GitHub/MLB data. |

## Known Repo State During Exploration

- `AGENTS.md` was untracked and now includes `@CLAUDE.md` plus this handoff
  file.
- `daily-advisor/fa_scan.py` was modified to fix `--help` handling of `%owned`
  in argparse help text.

## Open Questions

- Whether to track `AGENTS.md` in git.
- Whether to add a repo-local Python version marker or setup doc so local Codex
  sessions use Python 3.12 instead of `/usr/bin/python3`.
- Whether to add a lightweight test environment for Python 3.12, since pytest is
  installed only for the older default Python on this machine.
