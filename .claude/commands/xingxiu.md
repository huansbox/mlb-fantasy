---
name: xingxiu
description: "Fantasy Baseball 更新「星宿老仙群雄譜」靜態網站並重新部署到 Netlify。從 VPS 撈全聯盟 12 隊每週對手投打累積 + 當週名次 + 運氣分 → 本機生成 HTML → deploy 到 workwork-xingxiu-scout.netlify.app。用戶說「更新星宿譜」「更新群雄譜」「重新部署 scout」「刷新對手數據網站」「xingxiu」「update scout」時觸發。不用於評估球員（/player-eval）、FA 掃描（/waiver-scan）、週覆盤（/weekly-review）。"
---

# 更新星宿老仙群雄譜並部署

把全聯盟 12 隊「每週 H2H 對手的投打累積 + 當週名次 + 運氣分」重新撈一次、重生 HTML、部署到 Netlify production。

> **產物**：https://workwork-xingxiu-scout.netlify.app（Netlify site name：`workwork-xingxiu-scout`，account slug `huansbox`）
> **資料流**：VPS Yahoo scoreboard（每週 matchup + 全隊 stats）→ `_scout_all.py` 算名次 + 運氣分 → JSON → `build_scout_html.mjs` 生 `scout-site/index.html` → `netlify deploy`。
> **不碰本機 Yahoo**：撈數據在 VPS（token 只在 VPS）；本機只做 build HTML + deploy。

## Step 1：VPS 撈最新數據 → 本機 JSON

```bash
bash bin/vps-run.sh 'cd /opt/mlb-fantasy && git pull --ff-only -q >&2 && python3 daily-advisor/_tools/_scout_all.py' > daily-advisor/_tools/_scout_all.json
```

- 先 `git pull` 確保 VPS 有最新 driver（`git pull` 輸出導到 `>&2`，避免污染 stdout 的 JSON）。
- `_scout_all.py` 自包含（stdlib only），讀 `daily-advisor/` 的 `.env` / `yahoo_token.json` / `roster_config.json`，對 week 2..當前週各撈一次 scoreboard，輸出 JSON 到 stdout。
- ssh stdout 重導向到本機 `daily-advisor/_tools/_scout_all.json`。
- **驗證**：PowerShell `(Get-Content daily-advisor/_tools/_scout_all.json -Raw | ConvertFrom-Json).teams.PSObject.Properties.Name.Count`（應為 12），或 `wc -c`（應 ~190KB+）。
- git pull 衝突 / driver 報錯 / JSON 非 12 隊 → 停手回報，別硬跑下一步。

## Step 2：本機生成 HTML

```bash
node daily-advisor/_tools/build_scout_html.mjs
```

- 從 repo root 跑（cwd）；讀 `daily-advisor/_tools/_scout_all.json` → 寫 `scout-site/index.html`。
- 輸出印 `WROTE ... (N bytes, 12 teams)` + `ORDER ...`（WorkWork 本尊置頂、99 TeTe / YoBonBonLo 門徒次之、其餘照原序）。

## Step 3：部署到 Netlify production

```bash
netlify deploy --dir=scout-site --prod --site workwork-xingxiu-scout --json
```

- 已登入（team `huansbox`）+ site 已建，用 `--site workwork-xingxiu-scout` 非互動部署，`--json` 抑制互動。
- 輸出 JSON 的 `url` = https://workwork-xingxiu-scout.netlify.app。
- 若報未登入（`netlify status` 確認）→ 請用戶自行 `! netlify login`（OAuth 瀏覽器互動，無法代跑），完成後重試本步。

## Step 4：回報 + 線上驗證（選）

- 回報 production URL。
- 選做：playwright `browser_navigate` 線上 URL（手機寬度 390 為主訴求）截圖確認渲染，完事 `browser_close` + 清掉截圖。

## 設計規格（改 HTML 時參考）

- **數據口徑**：每隊列「該隊每週 H2H 對手」的隊級累積（投：IP/W/K/ERA/WHIP/QS/SV+H；打：R/HR/RBI/SB/BB/AVG/OPS）。名次 = 當週全聯盟 12 隊相較（#1 最佳；ERA/WHIP 低者為尊）。本週進行中 → rank null 顯示 —。
- **運氣分**：對手各類別名次反推 `(of+1 − 名次)`（12 隊：#1=12 分…#12=1 分）加總；投/打各 7 項（滿分 84）、投+打 14 項（滿分 168）；投+打另附「當週 12 隊對手強度排名」（#1 = 該週對手最強，標準競賽排名並列同名次）。
- **視覺**：淺底專業 data-table（FanGraphs/Savant 風）+ RWD 手機優先（首欄 sticky、nav 橫捲、字級縮放）；明細表僅前三名淡藍底、普通數字 #n（不用圓圈）；色弱友善（無紅綠濃彩，藍色克制）。星宿主題留在深綠 header banner + 本尊(金)/門徒(綠)徽章 + 吹捧文案。
- **本尊 / 門徒名單**：在 `build_scout_html.mjs` 開頭手動維護 — `MASTER`（目前 `WorkWork`）、`DISCIPLES` set（目前 `99 TeTe` / `YoBonBonLo`）。聯盟成員改名或門徒異動 → 改這兩處常數。
- **腳本**：`daily-advisor/_tools/_scout_all.py`（VPS 撈數據，stdlib 自包含，讀 parent `daily-advisor/` 的 secrets）+ `daily-advisor/_tools/build_scout_html.mjs`（本機 JSON→HTML）。中間產物 `_scout_all.json` / `scout-site/` 已 gitignore，每次重生。

## 不做的事

- 不評估球員（/player-eval）、不掃 FA（/waiver-scan）、不做週覆盤（/weekly-review）。
- 不改 roster / lineup。
- 不改聯盟對戰數據（純讀 Yahoo scoreboard）。
- 不在本機跑任何 call Yahoo 的腳本（撈數據一律在 VPS）。
