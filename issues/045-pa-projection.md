## Parent PRD

`issues/prd-decision-execution.md`（主 issue GitHub #316）

## What to build

打者下週 PA 投影（P-b）— 把 platoon 分類 + 賽程轉成「候選下週預期 PA」，餵給 047 swap-batter 把 rate 折成 counting 期望。

機制：球隊下週場次（賽程）× 對手先發慣用手份額（044 分類）× PA/G → 下週 PA 投影。用 043 weekly_projection 算術把 PA 折成逐類別期望。

詳見 PRD Implementation Decisions「platoon 拆兩片」P-b。

## Acceptance criteria

- [ ] 下週 PA 投影純函式（賽程 × 手性份額 × PA/G），schedule/probable 注入式
- [ ] 復用 043 `project()`，不另寫一份算術
- [ ] retro：預測下週 PA vs 實際 PA（快收斂、可日級驗證）
- [ ] 單元測試：場次×份額邊界 + 缺 probable 降級
- [ ] payload 行注入，受 039 payload_budget 守門

## Blocked by

- Blocked by `issues/043-weekly-projection-arithmetic.md`
- Blocked by `issues/044-platoon-share-classifier.md`

## User stories addressed

- User story 11
