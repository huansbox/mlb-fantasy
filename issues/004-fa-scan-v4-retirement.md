## Parent PRD

`issues/prd.md`

## What to build

退役 `daily-advisor/fa_scan_v4.py` CLI 工具。v4 已 production，CLI frontend 命運不需保留（CLAUDE.md 既有 TODO 三選一決定為「退役」）。

操作：把檔案移到 `archive/` 目錄（保留 git history 可查）或 `git rm`；同步移除 CLAUDE.md「檔案索引」+「待辦」段對 fa_scan_v4.py 的引用。

詳見 PRD `Implementation Decisions` 段「退役」+ CLAUDE.md 既有 TODO「fa_scan_v4.py CLI 命運」。

## Acceptance criteria

- [ ] `daily-advisor/fa_scan_v4.py` 移到 `archive/fa_scan_v4.py` 或 `git rm`
- [ ] CLAUDE.md「檔案索引」表移除該行
- [ ] CLAUDE.md「待辦」段移除「fa_scan_v4.py CLI 命運」整條 TODO
- [ ] grep 全 repo 確認沒有其他檔案 import / 引用 fa_scan_v4（cron 排程 / shell script / 其他 .py）
- [ ] commit message 註明退役原因（v4 已 production，不需保留 CLI frontend）

## Blocked by

None - can start immediately

## User stories addressed

- User story 18
