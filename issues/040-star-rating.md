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

- [ ] `score(factors: dict)` 純函式 + 資料化權重表（加因子不改簽章）
- [ ] day-0 三因子變體（無觸發完成度時上限 4★）
- [ ] **回溯校準集 fixture**（機器可判驗收）：Vargas/Horwitz/O'Hearn ≥4★、Sheets/Pederson ≤3★
- [ ] 星等 + 因子明細注入報告，受 039 payload_budget 守門
- [ ] 單元測試：四因子各檔位 + day-0 變體 + 校準集回歸

## Blocked by

- Blocked by `issues/038-decision-ledger-core.md`

## User stories addressed

- User story 3
- User story 22
