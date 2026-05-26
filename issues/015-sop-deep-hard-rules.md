## Parent PRD

`issues/prd-stream-sp-optimization.md`

> **Type**: SOP refinement（不是嚴格 vertical slice — 無 schema/code/test 層改動，只動 SOP markdown）。30 分鐘可完，作 Stage 1 熱身。Agent review 標 vertical slice 純度 2/5，但實務保留。

## What to build

純 SOP 文字更新（零 code 動）。在 `.claude/commands/stream-sp-deep.md` 加兩條 hard rule。

### C3 — 7d 落差 hard rule（Step 2b 升級 soft → hard）

> **Hard rule**：7d 與 14d 落差 ≥.080 + 7d 樣本 ≤6 場 → **強制 14d 為錨**，不可單獨依 7d 升 verdict。
>
> 例外：明確 lineup 變動 / 主力傷退 / 換投手教練 / 球隊風格重大改變這類獨立支撐才能 override hard rule。
>
> Why: Cameron 5/27 ground truth — NYY 30d→7d -.130 cool 但 vs LHP .788 強底盤 + 4/18 fingerprint，LLM 違反 soft rule 升 ⚠️ 後事後判定該維持 ❌。

### C4 — 對弱打崩盤 floor=高 OR 雙條件（Step 1c 加 hard rule）

> **Hard rule**：近 6 場對「弱打 vs SP 慣用手 OPS ≤.680」隊伍崩盤（ER≥4）→ floor risk 「高」。
>
> 須滿足以下**任一**：
> - 近 6 場崩盤 ≥2 次，或
> - 1 次崩盤 + 近 N 場 ERA ≥4.50
>
> 例外：PC <70 + IP <4 控管短局（PC 觸頂限制）不計入崩盤。
>
> Why: Rea 5/28 ground truth（近 6 場 6.10 ERA + 對 CWS 4.2IP/4ER 5/17）vs Springs 4/19（單次 5IP/7ER/4HR 但後續 ERA 3.94 + SEA vs LHP .592 強訊號）— 用 OR 雙條件門檻避免單事件誤殺強訊號。

## Acceptance criteria

- [ ] `.claude/commands/stream-sp-deep.md` Step 2b 由 soft guidance 升 hard rule（加 `**Hard rule**:` 標記 + 例外條件 + 「Why」一行 ground truth case reference）
- [ ] `.claude/commands/stream-sp-deep.md` Step 1c 加 floor risk hard rule（OR 雙條件 + 例外條件 + 「Why」一行）
- [ ] 兩條規則行文長度 ≤5 行，不要膨脹 SOP（其他段落不動）
- [ ] **Negative assertion**：deep skill 其餘段落（Step 0/1a/1b/1d/2a/3/4/5/6/7）逐字 unchanged，diff 只在 Step 1c + Step 2b
- [ ] commit 訊息含 ground truth case reference（C3: Cameron 5/27 案例 / C4: Rea 5/28 vs Springs 4/19 對比）
- [ ] 不動 code、不動 test、不動 fixture
- [ ] sanity check：另一個 session 讀 hard rule 段落確認 trigger 條件不歧義（特別是 C4 「弱打」定義 + 「崩盤」ER 門檻 + 「PC<70+IP<4 控管短局」例外）

## HITL gate（上線後觀察）

- [ ] 上線 2 週後 review hard rule 觸發次數 + verdict 命中率：
  - C3 觸發 ≥3 次且 ≥1 次被 user override（用戶覺得 14d 主錨壓掉真實短期 signal）→ 降回 soft guidance + 改門檻
  - C4 觸發 ≥3 次且 ≥1 次被事後驗證誤殺（pending verdict ❌/⚠️ 但實際串流結果好）→ 改 AND 雙條件門檻
- [ ] 觀察期內若無觸發 → 規則 lock-in，不撤退
- [ ] 觀察結果記錄在 `docs/stream-sp-hard-rules-observations.md`（新檔，或併入 `docs/streaming-sp-playbook.md`）

## Blocked by

None - can start immediately.

## User stories addressed

- **US3** — 7d / 14d 主錨規則 LLM 違反
- **US4** — 對弱打崩盤 floor risk 判斷不一致
