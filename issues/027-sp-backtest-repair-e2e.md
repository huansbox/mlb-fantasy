# 027 — SP backtest 修復端到端

## Parent PRD

`issues/prd-fa-scan-batter-quality.md`（§Implementation Decisions「對帳引擎」）

## What to build

把 SP 決策對帳從「跑了兩週、一筆帳都沒對過的空殼」修成端到端可信：verdict 解析穿過真實 issue 格式（code fence + 摺疊標籤包裹）、outcome 取數接上既有 Savant rolling（補掉永遠回 None 的 stub）、取帳邏輯改為帳齡 21-28 天窗口（修掉「觀察窗沒走完就對帳」的第三個破洞）。episode 去重（同一組 drop/add 連續多天 = 一筆帳，從首日起算）以共用純函式落地，供 batter 端（`issues/029`）重用。

Demo 判準：本機對真實 issue archive 跑一次，產出第一份 n_total > 0、hit_rate 非「—」的 SP 週報 section。

## Acceptance criteria

- [ ] verdict 解析對真實 production issue body（含 code fence + `</details>` 包裹）成功抽出 Step B verdict
- [ ] 解析測試 fixture 一律取自 `gh issue view --json body` 的真實存檔（如 #305），**禁止手寫模板樣本**（PRD Testing Decisions 鐵律）
- [ ] outcome 取數不再是 stub：drop / add / watch 對象的 post-verdict 21 天 xwOBACON 由 Savant rolling 實際取得
- [ ] 取帳改為帳齡 21-28 天窗口：觀察窗未走完的 verdict 不對帳；跨週重跑同一筆 verdict 不重複對帳
- [ ] episode 去重為共用純函式（落在共用對帳函式庫），batter 端可直接 import
- [ ] 對真實 issue archive 跑出第一份 n_total > 0 的 SP 週報 section，append 到既有 SP 對帳 doc
- [ ] 純函式層（解析 / 帳齡選擇 / 去重 / outcome 分類）有單元測試；外部邊界（gh / Savant fetch）注入式

## Blocked by

None - can start immediately

## User stories addressed

- User story 2（SP 對帳真的對出帳）
- User story 3（帳齡 21-28 天）
- User story 4（episode 去重）
- User story 25（真實 fixture）
- User story 27（純函式 + 注入邊界）
