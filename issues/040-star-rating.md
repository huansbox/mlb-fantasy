## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

機械星等（1-5★）— pre-LLM 決定論公式，AI 只消費不打分。星等驅動通知門檻（041 只推 4★+）與差額表預篩（047/048 只給 4★+）。

介面（凍結）：`score(factors: dict) → StarResult`（**具名因子字典 + 資料化權重表，非定位參數** — 之後加因子是資料變更不是介面變更）。四因子：
- 發現路徑（structure +1 / market·news·unknown +0.5 / heat +0）
- 雙年確認（prior 核心 ≥2 項 P70+ 且樣本足 +1 / 部分 +0.5 / 無 +0）
- 上場量（PA/TG ≥3.5 +1 / 2.5-3.5 +0.5 / <2.5 +0；SP 以 IP/GS + Rotation Gate 對應）
- 觸發完成度（全達成 +1 / 部分 +0.5）

`stars = 1 + round(Σ)`。day-0 變體：三因子按比例放大、上限 4★（5★ 必須經觸發驗證）。門檻以回溯案例集校準定案。

詳見 PRD Implementation Decisions「star_rating」。

## Acceptance criteria

- [x] `score(factors: dict)` 純函式 + 資料化權重表 `WEIGHTS[factor][level]`（加因子=加一列資料，簽章不變）
- [x] day-0 三因子變體（去 trigger、×4/3 放大、上限 4★ — 5★ 須經觸發驗證）
- [x] **回溯校準集 fixture**（機器可判驗收）：Vargas/Horwitz/O'Hearn ≥4★、Sheets/Pederson ≤3★ + winners 嚴格 > losers（structure/heat 發現路徑為主鑑別器）
- [~] 星等 + 因子明細注入報告 — `format_stars()` 已備（★bar + 因子明細）；**實際報告注入受 039 payload_budget 守門，wiring 待 039**
- [x] 單元測試：四因子各檔位 + day-0 變體 + bucketers（PA-TG/雙年/觸發）+ 校準集回歸（22 cases）

## 狀態

✅ 模組完成（merge `f0d789d`）+ **三審硬化（`49e9741`）**。`daily-advisor/star_rating.py`，`score()` + bucketers + `format_stars()` 凍結介面。報告注入留待 039（payload_budget）。

三審（#317/#319）修正 — **校準失真（C1/C2/D1）**：原校準把 Sheets 硬編 `dual_year=partial`（但文件說「prior P80」=強）、Pederson 編 `mid`（但他是 platoon -28%PA 反例=`low`），是自我實現的假校準。修法 = **heat-led 硬上限 3★**（忠於文件「channel 才是鑑別器、雙年/上場量不分勝負」），讓校準改用忠實等級仍 ≤3★。新增 channel-only-differs 鑑別測試 + day-0 上限邊界 + P70 邊界 + 清死碼。27 star tests，834 全綠。

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`

## User stories addressed

- User story 3
- User story 22
