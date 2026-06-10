# 028 — batter waiver-log 區塊文法擴充端到端（HITL）

> **狀態：✅ 完工部署 2026-06-10（merge `c549fe0`）**；唯一剩餘 = 部署後首班 cron 驗證（06-11 12:30 TW，見下方未勾項）。文法定版 / A/B 證據 / 部署細節見主 issue 進度看板「028 部署日」段。

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「建議紀錄區塊文法擴充」）

## What to build

batter 報告尾端的機器可讀區塊（```waiver-log fenced block）文法擴充三件：① NEW 行補「vs 對象」欄位；② 新增 `ACTION|球員|取代類型|vs對象` 行 — 每日 actionable 判斷顯式化，解決「已在追蹤中、當天升級成取代」只有 UPDATE 行、升級事件隱形的盲點；③ 新增 `CLOSE|球員|理由` 行 — 結案從 LLM 自發行為變成正式輸出契約，寫入端自動搬移到已結案段。同波把「已推薦 N 天未執行」警示計數改由程式算好注入（LLM 只引用不數）。

**這是全計畫的曆法長竿，必須最早上線** — batter 對帳（`issues/029`）只能讀新文法的帳，部署後要等 21 天才有第一筆帳齡達標的帳。

HITL 點：文法細節定版（欄位順序 / 分隔符相容）+ 配對 A/B 結果人工審（prompt 輸出格式變更，lever 2 前車之鑑）。

## Acceptance criteria

- [x] 文法定版：NEW 行 vs 欄位、ACTION 行、CLOSE 行的欄位契約寫進 prompt 輸出規則（HITL 三題皆選推薦案）
- [x] 寫入端解析支援新行型：CLOSE 自動把對應條目搬到「已結案」段（整條連歷史搬移）；ACTION 行不破壞既有 NEW/UPDATE 處理
- [x] 向後相容：無新欄位的舊格式區塊仍可正常解析（6 欄 NEW 實測 #306 真實區塊）
- [x] 「已推薦 N 天未執行」計數由程式從區塊歷史計算注入 payload；prompt 對應規則改為「引用注入值」
- [x] 配對 A/B（同 payload、同模型、neutral cwd）：核心決策一致 + output_tokens +52% 與可見輸出 +48% 等比成長（tokens/char 持平，非 thinking 誘發）
- [ ] ⏳ 部署後隔日 production issue 區塊出現新行型、waiver-log 寫入無解析錯誤（既有 Telegram 報警覆蓋）— **待 06-11 12:30 TW 首班 cron 觀察**
- [x] 解析端測試 fixture 用真實 production 區塊內容（#306 + 真實 waiver-log.md snapshot，24 cases）

## Blocked by

None - can start immediately（建議與 `issues/027` 並行，本片優先部署）

## User stories addressed

- User story 11（vs 對象）
- User story 12（升級事件顯式化）
- User story 13（結案自動執行）
- User story 14（計數機械化 — 連續推薦部分）
- User story 25（真實 fixture）
- User story 26（prompt 變更配對 A/B）
