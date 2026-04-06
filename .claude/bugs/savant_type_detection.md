---
name: savant player type detection bug
description: yahoo_query.py savant command misdetects pitchers as batters when they have batting data in Savant CSV
status: fixed
found: 2026-04-06
file: daily-advisor/yahoo_query.py
lines: 465-471
---

## 問題

`cmd_savant()` 偵測 player type 時先查 batter CSV，找到就停。
投手若在 Savant batter CSV 有資料（少量打擊 PA），會被誤判為打者。

## 影響

- 無 xERA 輸出（batter CSV 不含）
- 百分位標記用打者表（方向相反）
- 實際案例：Eduardo Rodriguez、Reynaldo López（2026-04-06 waiver-scan 發現）

## 根因

```python
# yahoo_query.py:465-471
for player_type in ["batter", "pitcher"]:
    test = _savant_lookup(query, years[0], player_type)
    if test:
        detected_type = player_type
        break  # ← 找到就停，不比較兩邊
```

## 修復方向

查完 batter 和 pitcher 兩邊，比較 BBE 數量，取高的。
投手作為 pitcher 的 BBE（被打球數）遠大於作為 batter 的 BBE（自己打擊）。

```python
# 修復思路
best_type = None
best_bbe = -1
for player_type in ["batter", "pitcher"]:
    test = _savant_lookup(query, years[0], player_type)
    if test and (test.get("bbe") or 0) > best_bbe:
        best_bbe = test.get("bbe") or 0
        best_type = player_type
detected_type = best_type
```
