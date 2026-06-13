## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

decision_ledger 的薄消費端三件 + 全域行數預算守門：

1. **發現路徑分類**：pool assembly 時依候選來源（SCAN_QUERIES / owned risers / watchlist）判定 structure / heat / market / news，**首次接觸時持久化一次**（經 038 `record` 寫入 channel 欄），star 只讀不重判 — 防 heat-led 球員養出季線後洗白。
2. **payload 注入**：經 038 `get_history` 讀出「上次 verdict + 幾天前 + 理由」與「原 add 理由」兩行注入候選 payload。
3. **legacy backfill 一次性腳本**：存量 watchlist 從 git 歷史/觸發文字推回發現路徑（推不出標 unknown）；既有 roster 球員以上線日季線快照充 add 理由 — 上線第一天即保護全名單。
4. **payload_budget 守門模組**（獨立深模組）：`register(slice_id, lines)` / `assert_within(candidate)`，行數預算（每候選 ≤3 新行）是橫跨 7 片的全域不變量，獨立而非埋在 ledger 內。

詳見 PRD Implementation Decisions「ledger 消費端」。

## 拆分（2026-06-13，因 Explore 揭露 channel 在組裝時已遺失 + payload 注入成本敏感需 A/B）

- **318a（機械持久化半，✅ 完成 merge `e48b956`）**：不動 LLM payload、零成本風險。
- **318b（LLM 注入半，⏳ 待辦，與 042 同批上 VPS A/B）**：payload_budget 模組 + 注入 prev-verdict/add-reason/star 三行 + legacy backfill + 配對 A/B。

## Acceptance criteria

### 318a（已完成）
- [x] 發現路徑於首次接觸持久化、不重判（`first_channel` honored；heat-led 不洗白）— `ledger_enrich.classify_channel` + `compute_candidate_stars`，channel 寫進 ledger
- [x] source 標記（scan-query / owned-riser）池層注入 + 經 normalize 保留 + thread 到寫入點（做法 A）
- [x] star 因子萃取 + day0 判定（empty history → day0 cap 4★；established → 4-factor trigger 暫 none）+ stars 回寫 ledger
- [x] 單元測試：channel 四分類 + first_channel 不重判 + day0/established + 薄樣本 + wiring entry 萃取（17 cases，851 全綠）

### 318b（待辦，與 042 同批）— 注意：318b 現在是「全 payload 注入批」
> 量修復鏈（#322-#327）模組已全部建好+測過（merge `9a9eeb4`），它們的 LLM payload 注入也併入此批一起上 VPS A/B：platoon tag（#323）、PA 投影行（#324）、swap-batter 行（#326）、swap-SP 行（#327）、SP 場次行（#325）。connect 點：candidate entry → 各模組計算 → payload 行，受 payload_budget 守門。
> **+ micro-fields（#328 / 049，引擎 merge PR #333+#334）**：post-hype tag（`prospect_pedigree.post_hype_tag`，需餵 mlb_id + age + batter Sum）、chase/zone-contact tag（`batter_discipline.discipline_tag`，需 join 當季+前季 bulk custom CSV）。同 candidate entry → 模組 → payload 行，受 payload_budget 守門。
- [ ] payload_budget `register`/`assert_within` 純函式 + 超限 assert（≤3 行/候選）
- [ ] payload 注入 prev-verdict + add-reason + star 三行，格式機械可解析
- [ ] 量修復鏈注入：platoon tag / PA 投影 / swap-batter / swap-SP / SP 場次（模組已備，串 candidate entry → payload 行）
- [ ] micro-fields 注入：post-hype tag（#328）/ chase-zone-contact tag（#328）（引擎已備 merge #333+#334，串 candidate entry → payload 行）
- [ ] sp_start_projector ≥85% retro 準確率 gate（VPS 歷史資料跑）
- [ ] legacy backfill 覆蓋率：跑後無「缺 add 理由」roster 球員、無「缺 channel」watchlist 條目
- [ ] 配對 A/B（VPS，比照 037）量 payload input/output token delta；trigger-completeness 評估（5★ 精度）一併補
- [ ] **owned-rising 快軌 shape 串接**：把候選 %owned shape 傳進 `_gate_notifications` 的 `owned_trend`（現 hardcode None，gate 已支援）
- [ ] **5★ 噪音 backoff（#320 三審警示）**：觸發評估上線後 5★ 變 reachable，多個滯留 5★ 會每日多行推播且無 cap/decay。若實測吵 → 在 `decision_gate.gate` 加 5★ re-escalation backoff（如 day 1/2/3 後改每 3 天）。先觀察再決定。

## 審查補充（來自 #317/#319 三審，開工必讀）

- **發現路徑「永不重判」用 `DecisionLedger.first_channel(player)`**：038 已提供此 helper（回傳最早一筆有 channel 的值）。039 寫 channel 前先查 first_channel，非 None 就沿用，不可重判 — 這是 user story 9 的不變量，務必在這層強制。同日多次 enrich 也不可用不同 channel 覆蓋。
- **day0 路徑選擇是 039 的責任（PRD 未指派，本片補上）**：star `score(factors, day0=?)` 的 day0 由 039 決定，規則 = `day0 = (get_history(player) == [] )` 或「該球員從無觸發驗證過的 entry」。day0=True 走三因子上限 4★（5★ 須經觸發驗證）。把此規則寫進本片 AC + 測試。
- **stars 要回寫 ledger**：039 算完 star 後 `record(..., stars=)` 持久化，供 041/051 直接讀，不重算。

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`

## User stories addressed

- User story 1
- User story 9
- User story 18
- User story 20
