## Parent PRD

`issues/prd.md`

## What to build

新建 `metrics_reader` 深模組 + CLI：給定一組 issue body 字串（或內建 `gh api` 抓取），parse 出 metric blocks，aggregate 成 rate stats。

**接口**：`aggregate_metrics(issue_bodies: list[str]) -> dict` → 回傳 `{p1_match_rate, review_trigger_rate, n_samples, date_range, sp_breakdown, fa_breakdown}`

**CLI**：`python metrics_reader.py --days 7` → 內部跑 `gh issue list -R huansbox/mlb-fantasy --label fa-scan --limit N --json body` → parse → 算 rate → stdout 輸出。

**Robustness**：fixture issue body 含 / 不含 / 損壞 metric block 三種情境都需正確處理（不含 → skip 該筆；損壞 JSON → 記錯誤但繼續）。

詳見 PRD `Implementation Decisions` 段「Metrics Reader」+ `docs/sp-b1-cutover-design.md` §3 監控。

## Acceptance criteria

- [ ] `aggregate_metrics(issue_bodies)` 為純函式，pure parse + count
- [ ] Regex 正確抽出 `<!-- phase6_metrics: { ... } -->` block
- [ ] `json.loads` parse 後 aggregate：p1_match_rate / review_trigger_rate / n_samples / date_range
- [ ] SP / FA 兩個路徑分開統計：sp_breakdown / fa_breakdown 各含 p1_match_rate + review_trigger_rate
- [ ] CLI `python metrics_reader.py --days 7` 端對端跑通：gh api 抓 → parse → 輸出 stdout
- [ ] Fixture test：含 metric block → parse 成 dict
- [ ] Fixture test：不含 metric block → 該 issue skip
- [ ] Fixture test：損壞 JSON → 記 warning 但繼續處理其他 issue
- [ ] Aggregate test：給 7 筆 fixture（5 P1 match + 2 不 match）→ p1_match_rate = 5/7 ≈ 0.714

## Blocked by

- Blocked by `issues/003-metrics-emitter.md`

## User stories addressed

- User story 10
- User story 25
