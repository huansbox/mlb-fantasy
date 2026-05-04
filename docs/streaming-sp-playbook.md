# 串流 SP Playbook

> CLAUDE.md「執行中策略」段定調：**預設不串流**。本文件是觸發串流時的具體 mental model / 決策規則 / 操作流程，平時不需讀。

## Mental model

**正確心態：用 1 acquisition 額度租用 1 場數據**（不是「加入隊伍」）

- Drop 對象優先序：BN borderline anchor > BN 觀察中球員 > active worst SP
- BN 投手 drop 後可在下次 acquisition 撿回（FA 池基本不缺中等 SP）
- **Sunk cost 警示**：「不想動 roster」是心理摩擦，不是戰術理由
- 1 場操作後，串流 SP 通常隔天就 drop 換下一個 — 不該對串流 SP 產生情感
- Acquisition 成本：1/6 週額度（≈ 16%）+ FAAB 1 元（≈ 1% 季預算）；補 1 contested 類別期望勝率提升 ≥ 30% → 成本值得

## 決策規則

| 情境 | 做法 |
|------|------|
| 某項 counting stat 接近翻盤（K 差 3-5 個） | 精準撿 1 場高 K 率 SP |
| 對手弱到本週穩贏 | 可用 2-3 次異動測試串流效果 |
| **預設** | **不串流，留異動額度給傷兵替補和 hot bat** |

> Contested 門檻判斷見 CLAUDE.md「Week 中 H2H 決策框架」段。

## 操作流程

### 查先發日程的正確方法

```bash
# 用 MLB API 逐日查 probable pitcher（只提前 1-2 天公布）
curl -s "https://statsapi.mlb.com/api/v1/schedule?date=2026-04-08&sportId=1&hydrate=probablePitcher"
```

- ⚠️ **不要用 FanGraphs/FantasyPros 的 probables grid 推測**（常有錯誤，例如把 5 天間隔排成 3 天）
- **正確方式**：查球員 game log 最後一場日期 + 5 天推算，再用 MLB API 確認
- MLB API 只提前 1-2 天公布 probable，更遠的日期需用輪值間隔推算

### FAAB 時效與串流時程

1. 提交 FAAB claim（在每日 TW 15:00 前）
2. 當日 TW 15:00（= ET 3AM）處理
3. 處理後當晚設 Daily-Tomorrow lineup
4. **隔天上場（前置 1 天）**
5. → 串流 SP 需在目標先發日的**前一天** TW 15:00 前 claim
6. ⚠️ 若 claim 在 TW 15:00 後提交，順延到次日處理（多等 1 天）

### 串流測試策略（適用於觀察中候選 SP）

- 搶先發日最近的候選 → 看一場結果
- 好就留（轉為正式 roster），不好就 drop 換下一位候選
- 每週 6 次異動上限需預留 1-2 次給傷兵替補
