# Stream-SP Skill Optimization PRD

> **Type**: Optimization PRD（非新功能，是 evaluation logic + 工程改進）
> **Origin**: 2026-05-26 session — 跑完 4 位 SP 深評（McDonald / Springs / Cameron / Rea）後產出 11 條建議，3 agent review 後修正成 6 條落地項
> **Scope**: `/stream-sp` + `/stream-sp-deep` 兩個 skill + 後端機械層 (`daily-advisor/stream_sp_scan.py` + `daily-advisor/mlb_query.py`)

## 背景

過去 4-6 週 stream-sp 跑了至少 8 輪，實際 add SP 後常見「deep eval 翻 scan verdict」現象。Backtest 顯示 scan ✅ 被 deep 翻 ❌ 至少 5 次（Pallante / Springs / Canning 等），scan ⚠️ 偏推被翻 ✅ 強推 1 次（Springs 5/27），證明 deep 階段補的是 scan 結構面之外的訊號。常見訊號類型：vs hand OPS split、樣本量信心、7d/14d 回歸、對弱打崩盤 floor risk。

## 用戶痛點（user stories）

| # | 痛點 | 歷史證據 |
|---|---|---|
| **US1** | vs hand OPS 訊號要 deep eval 才看到（scan 階段缺）| Springs 5/27（SEA vs LHP **.592** P10 翻盤）/ Holmes 5/16 / Cameron 5/27 vs LHP .788 |
| **US2** | 補查模式下 pending evaluations 中的 SP 可能 schedule 已變或被聯盟認領，手動偵測 friction | 5/26 Canning→Vásquez 替換 / Burke 認領；過去 Kolek / Holmes / Junk 被搶。每週 1-3 次 |
| **US3** | 7d 與 14d/30d 落差大時 LLM 容易違反「14d 主錨」soft rule，用 7d 升 verdict | Cameron 5/27 (NYY 30d→7d -.130 cool 但 vs LHP .788 強底盤) / 過去 PHI / HOU / SEA 三案 |
| **US4** | 對弱打崩盤的 floor risk 判斷 LLM 不一致（Springs 4HR 過 / Rea 4ER 不過）| Bassitt / Rea / Pallante / Canning / Springs 6+ 次 |
| **US5** | BBE 30-80 區間 / 場數 ≤12 樣本信心警示沒機制 | McDonald 5/27 (BBE 65) / Canning 5/25 (4 場) / Alexander 5/26 (BBE 0) |
| **US6** | Deep eval N 位 = 2N 個 SSH 並行 + 比較表 LLM 手填，latency 高 | 5/16 一次評 4 位 / 5/27 一次評 3 位 |

## 落地藍圖

### Stage 1（強 ROI · 3 vertical slices + 1 SOP refinement）— ✅ 4/4 merged 2026-05-26

- **015 sop-deep-hard-rules**（US3 + US4）— **SOP refinement**（不是嚴格 vertical slice，純 SOP 文字升 hard rule，30 分鐘可完，熱身用）— ✅ commit `0407d5c`
- **012 scan-add-vs-hand-split**（US1）— scan emit vs_hand_2026 + SOP 強弱表改 vs hand + PA<400 sample gate — ✅ commit `c350e3d`
- **013 scan-add-sample-warning-tag**（US5）— scan emit sample_warning tag（**2026 only**）+ deep skill prompt 指引（非機械 demote）— ✅ commit `7e50f46`
- **014 scan-auto-diff-pending**（US2）— `--pending-file` + pending_parser + emit pending_diff — ✅ commit `366365e`

### Stage 2（次優先 · 1 個 vertical slice）— ⏳ 0/1

- **016 deep-batch-cli-and-comparison-raw**（US6）— mlb_query.py deep_batch + 比較表 raw JSON（**不依賴 014 pending_parser**，獨立可平行起跑，但建議排最後做避免 SOP 改動 stale）

### Dependency 視圖

```
015 (SOP refinement, 30 分鐘) ─┐
014 (auto-diff, 3-4 hr) ──────┼── 都可平行起跑
012 (vs_hand, 2-3 hr) ────────┘
   └── 013 (sample_warning, 1 hr, sequential, schema 共用 candidates JSON top-level key)
                                                       └── 016 (deep batch, Stage 2, 獨立)
```

Stage 1 起手意向順序（用戶決定）：**015 → 012 → 013 → 014 → 016**
（016 排最後避免改 stream-sp-deep.md Step 1-2 命令後讓 013/015 prompt 變 stale）

## 撤回 / 不做的項目

從 11 條原建議撤回（agent review 修正）：

- **A4 team_strength.json cron**：工程成本高（cron + 全聯盟 byDateRange）+ 記憶 take 實測零失誤
- **B1 刪「補查無新評」分支**：衛生整理，順手做
- **B2 簡化 `(deep)` 戳記**：撤回 — Springs 5/16 → 5/27 跨輪 deep baseline 真實用過
- **B3 刪備註區 free-form**：撤回 — 備註區實際承載 TBD 補查指示 / 排序 / decision tree

## 評價邏輯改寫關鍵（agent review 學到的）

- **C2 不能機械化**：違反 v4「Sum 是材料、verdict 是 LLM」分層精神 → 改 prompt 指引（issue 013）
- **C4 不能無條件**：單次崩盤套到 Springs 4/19 會誤殺 → 改 OR 雙條件門檻（issue 015）
- **C3 直接升 hard rule 零副作用**：Logic agent 評最高優先（issue 015）

## 三個 agent review 角度

| Agent | 角度 | 主要修正貢獻 |
|---|---|---|
| Engineering | 實作複雜度 / 摩擦 / 價值 | A4 工程成本評分；A3 純加法 reuse helper |
| Evaluation logic | fantasy baseball 邏輯 + v4 框架對齊 | C1 加 PA<400 sample gate；C2 改 prompt 指引（不機械化）；C4 改 OR 雙條件 |
| Historical backtest | pending file git log + waiver-log 痛點頻率 | B2/B3 撤回（找到實用案例）；C1 / C4 反覆出現確認真痛點 |

## Stage 1 完成標準

- [ ] 012-015 全部 merged 到 master
- [ ] 跑 `/stream-sp` 至少 3 輪驗證 candidates JSON 含 vs_hand_2026 + sample_warning
- [ ] 跑 `/stream-sp-deep` 至少 1 輪驗證 SOP hard rules 觸發（C3 + C4 各一次）
- [ ] 跑補查模式至少 2 次驗證 pending_diff 正確分類

## Stage 2 完成標準

- [ ] 016 merged
- [ ] 4 位 SP 深評批次跑 < 30 秒（vs 目前 60-80 秒）
- [ ] 比較表 raw JSON 結構穩定，LLM 只填 verdict 字串
