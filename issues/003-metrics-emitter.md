## Parent PRD

`issues/prd.md`

## What to build

新建 `metrics_emitter` 深模組：給定 SP / FA pipeline 結果（step1 results、master decision、anchor / fa_top entries），輸出 HTML 註解 metric block 字串，append 至每日 fa-scan GitHub Issue body 結尾。

接口：`emit_metric_block(date, sp_step1_results, sp_master, fa_classify_results, fa_master, anchor, fa_top) -> str`

Block 格式：
```html
<!-- phase6_metrics:
{
  "date": "2026-05-06",
  "sp_p1_match": true,
  "sp_review_triggered": false,
  "sp_anchor_name": "Detmers",
  "fa_p1_match": true,
  "fa_review_triggered": false,
  "fa_top_name": "Junk"
}
-->
```

寫入點：`_phase6_sp.py` `_emit_final` / `_emit_pass`（issue body 組裝邏輯尾端 append）。純函式無 side effect（純字串組裝）。

詳見 PRD `Implementation Decisions` 段「Metrics Emitter」+ `docs/sp-b1-cutover-design.md` §3 監控。

## Acceptance criteria

- [ ] `metrics_emitter.emit_metric_block(...)` 為純函式（無 IO 副作用，輸入相同 → 輸出相同）
- [ ] 輸出字串符合 `<!-- phase6_metrics: { ... } -->` 格式（HTML 註解 + JSON）
- [ ] 必含 7 欄位：date / sp_p1_match / sp_review_triggered / sp_anchor_name / fa_p1_match / fa_review_triggered / fa_top_name
- [ ] JSON 部分必須 `json.loads` parse-able（測試反向驗證）
- [ ] M1 計算邏輯：sp_p1_match = 三 agent step1 ranking[0]name 是否同一個（fa_p1_match 同理對 classify 結論）
- [ ] M4 計算邏輯：sp_review_triggered = master step2 是否回傳 borderline_pairs 非空（fa_review_triggered 同理對 fa_master）
- [ ] `_emit_final` / `_emit_pass` 整合：issue body 結尾 append metric block，不影響現有 body 內容
- [ ] 測試覆蓋：給 fixture pipeline 結果，輸出符合結構

## Blocked by

None - can start immediately

## User stories addressed

- User story 8
- User story 9
- User story 24
