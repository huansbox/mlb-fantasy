## Parent PRD

`issues/prd.md`

## What to build

把 B1 改動 merge 到 master 並上線到 VPS production，同步建立觀察期 SOP 文件。

**操作步驟**：
- merge slices 001 / 005 / 006 / 003 / 008 進 master（007 可在 cutover 後再 merge，觀察期才需要 reader）
- VPS 拉新 commit 後跑下次 daily fa-scan（cron TW 12:30 自動觸發，或手動觸發測試）
- 確認每日 fa-scan GitHub Issue body 結尾出現 `phase6_metrics` HTML 註解 block
- 文件化觀察期 SOP（每週日跑 `metrics_reader.py --days 7` → 比對撤退門檻 → 記入 `waiver-log.md` 或 `docs/sp-b1-observation.md`）
- 觀察期 4 週：Week 1-2 baseline 校準 + 不撤退；Week 3-4 套門檻 + 觸發判定

**Rollback 策略**：git revert（不引入 feature flag）。粒度依 commit 拆分，可選擇性 revert（見 PRD `Further Notes` §Rollback 粒度）。

**G-pre2 fallback 觸發後**：才寫 `prompt_phase6_sp_single.txt` + dispatcher flag（不在本 issue scope，撤退觸發再開新 issue）。

詳見 PRD `Solution` + `Further Notes` §觀察期 + `docs/sp-b1-cutover-design.md` §觀察期 SOP。

## Acceptance criteria

- [ ] All blocker issues（001 / 005 / 006 / 003 / 008）已完成且 merged
- [ ] VPS 拉新 commit，下次 daily fa-scan 跑通
- [ ] GitHub Issue body 結尾出現 `<!-- phase6_metrics: { ... } -->` block 結構正確
- [ ] `gh issue view <最新> -R huansbox/mlb-fantasy` 手動 sanity check：body 完整 / metric block parse-able
- [ ] 跑 `python metrics_reader.py --days 1` 對最新 issue 算出單筆 metric → 結果合理
- [ ] 文件化觀察期 SOP：每週日跑 reader → 比對 baseline 撤退門檻 → 記錄判定
- [ ] CLAUDE.md 同步更新：「待辦」段移除「框架對稱性檢視」+「SP Phase 6 prompt 拿掉 Sum 暴露」兩條 TODO；新增「B1 觀察期（4 週）+ multi-agent 命運判定」一條
- [ ] HITL：用戶 review 第 1 週 daily issue 確認 LLM 行為符合 B1 設計預期（非 lazy / 非 hallucinate）

## Blocked by

- Blocked by `issues/001-sp-sum-40-hard-filter.md`
- Blocked by `issues/005-sp-myteam-prompt-b1.md`
- Blocked by `issues/006-fa-path-prompt-b1.md`
- Blocked by `issues/003-metrics-emitter.md`
- Blocked by `issues/008-spike-fixture-baseline.md`

## User stories addressed

- User story 14
- User story 15
- User story 16
- User story 17
- User story 27
