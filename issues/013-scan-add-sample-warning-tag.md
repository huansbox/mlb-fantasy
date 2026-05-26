## Parent PRD

`issues/prd-stream-sp-optimization.md`

## What to build

`stream_sp_scan.py` candidates JSON 加 `sample_warning` tag（**2026 only**，不含 2025）。改 prompt 指引方向，不動 verdict 機械計算 — 避免衝突 v4「Sum 是材料、verdict 是 LLM」分層精神（agent review 修正 C2 不機械化的關鍵）。

### 實作層

1. **scan candidates schema 擴張**：每個 SP 加 top-level key：
   ```json
   "sample_warning": "low" | "medium" | "none"
   ```
   - 只標 2026 樣本信心
   - 2025 不標（agent review 結論：去年 BBE 已固定不會變，標 warning 多餘 noise）

2. **計算規則**（**AND-for-low**：實作對齊時釐清的語意，e2e 樣本為 ground truth）：
   - **BBE source**：`v4_2026.bbe`（batted-ball events，現 scan 已有此欄 line 105-106）
   - **場數 source**：`v4_2026.gs`（GS 數，現 scan 已有此欄）
   - 兩維度對應的 5-slot 軸不同：BBE 撐 GB% / xwOBACON 兩軸，GS 撐 IP/GS / Whiff% / BB/9 三軸。單邊 thin = 部分軸不可信；雙邊 thin = 全部軸不可信。
   - 門檻：
     - BBE <30 **AND** GS <6 → `"low"`（兩維度同時 thin，所有結構訊號降權 2 檔）
     - 否則若 BBE ≤80 **OR** GS ≤12 → `"medium"`（單邊 thin，降權 1 檔）
     - BBE >80 **AND** GS >12 → `"none"`（兩邊充足，結構訊號可信）
   - **v4 unavailable**（`v4_2026.v4_available == false`）→ `sample_warning = null`（沒材料判斷，不應預設 low 導致過度警告）

3. **SOP 改動**：
   - `.claude/commands/stream-sp-deep.md` Step 4 prompt 加文字指引（≤80 字）：
     > 讀到 `sample_warning="low"` 或 `"medium"` 時，**結構訊號（Sum / 5-slot percentile）信心降一檔**。需短期 game log 獨立支撐（近 N 場 ERA / QS / 對手 pattern）才能維持 verdict。

4. **明確不做的事**：
   - **不寫進機械層 verdict**：Sum 計算 / verdict mechanical rule 不變（agent review C2 評：機械 demote 會衝突 v4 分層精神）
   - **不改 scan 機械層 filter**：Rotation gate / Sum ≥15 hard floor 不動
   - **不改 stream-sp.md Step 2-6 filter 表**（filter 規則仍是 LLM 從 scan JSON 讀後執行，sample_warning 只進 deep skill）
   - **不標 2025**：去年數據已固定，標 sample_warning 無新增訊息

## Acceptance criteria

### Scan 機械層
- [x] `stream_sp_scan.py` 加 sample_warning 計算（reuse `v4_2026.bbe` + `v4_2026.gs`）+ tests（20 cases）：
  - [x] 雙軸雙 thin → "low"（BBE=0/GS=1）
  - [x] 單軸 thin（BBE 中段 + GS<6）→ "medium"（McDonald 65/4）
  - [x] 單軸 thin（BBE >80 + GS 6-12）→ "medium"（Springs 183/11）
  - [x] **AND-low 邊界 BBE=29 + GS=5 → "low"** vs **BBE=29 + GS=6 → "medium"** vs **BBE=30 + GS=5 → "medium"**
  - [x] **BBE 邊界 BBE=29/GS≥6 (medium) vs BBE=30 (medium) vs BBE=80 (medium) vs BBE=81/GS≥13 (none)**
  - [x] **GS 邊界 GS=5/BBE≥30 (medium) vs GS=6 (medium) vs GS=12 (medium) vs GS=13/BBE>80 (none)**
  - [x] BBE >80 AND GS >12 → "none"
  - [x] BBE 或 GS None（v4 unavailable）→ sample_warning=None
- [x] candidates JSON schema 含 `sample_warning` top-level key（字串，非 dict）
- [x] **不改 Sum 計算或 verdict mechanical rule**（Step 2-6 過濾規則未動 — 仍是 v4_available / rotation_gate / sum_score / opener_verdict 四條規則）
- [x] **不改 scan 機械層 filter**（Rotation gate / Sum ≥15 hard floor 邏輯 unchanged）

### Skill 層
- [x] `.claude/commands/stream-sp-deep.md` Step 4 prompt 加 sample_warning 處理指引（≤80 字）
- [x] `.claude/commands/stream-sp.md` Step 7 報告主表選擇性加 sample_warning column（如 SP 有 medium/low 才標 `⚠️ low/medium`，none/null 用 `—`；當天全表都 none/null 整欄可省略）

### E2E sanity check
- [x] CLAUDE.md「檔案索引」更新 stream_sp_scan.py 條目（新增 sample_warning 欄位說明 + AND-for-low 語意）
- [x] 單元測試覆蓋 issue 給的 6 個 e2e SP 樣本邏輯（AND-for-low 規則下）：
  - Alexander 2026 (BBE=0/GS=1) → `"low"` ✓（雙軸雙 thin）
  - McDonald 2026 (BBE=65/GS=4) → `"medium"` ✓（BBE 不夠 thin，未觸發 low）
  - Springs 2026 (BBE=183/GS=11) → `"medium"` ✓（BBE pass，GS=11 in 6-12）
  - Mikolas 2026 (BBE=158/GS=6) → `"medium"` ✓（GS=6 in 6-12）
  - Cameron 2026 (BBE=150/GS=9) → `"medium"` ✓
  - Rea 2026 (BBE=171/GS=8) → `"medium"` ✓
- [ ] VPS e2e 跑一次驗證（feat merge 後）：用 `python3 stream_sp_scan.py --et-dates {未來 ET 日} --pretty` 確認 candidates 含 sample_warning 欄
- （注意 5/26 多數 SP 仍是 medium 階段，「none」門檻 BBE>80 AND GS>12 對應 ~6 月後段 SP 才滿）

## HITL gate（上線後觀察）

- [ ] 上線 2 週後抽 spot-check 5 個 deep eval 案例：
  - 觀察 `sample_warning=medium/low` 觸發時 LLM 是否真在 verdict 理由中提到「信心降一檔」或樣本警示
  - 若 5 個案例中 ≤2 個提到 → prompt 指引太薄弱，加 explicit metadata（如 `<sample-warning>` tag）
  - 若 5 個案例中 ≥4 個提到 → prompt 指引足夠，lock-in
- [ ] 觀察結果記錄在 `docs/stream-sp-hard-rules-observations.md`（或併入 015 觀察檔）

## Blocked by

- Blocked by `issues/012-scan-add-vs-hand-split.md`（共用 candidates JSON schema 改動，sequential 避免 merge conflict）

## User stories addressed

- **US5** — BBE / 場數樣本信心警示沒機制
