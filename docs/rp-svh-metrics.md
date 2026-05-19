# RP 評估：主攻 SV+H 時該看哪些數據

> 2026-05-19 建立。情境探索文件，**非正式框架定稿**。
> 觸發脈絡：假設策略從「Punt SV+H」翻轉為「主攻 SV+H」，盤點挑 FA RP 時該看的數據。
> 關聯待辦：CLAUDE.md「RP 框架 v4 升級」。此文件是該升級的前置素材之一。

## 背景

當前聯賽策略為 **Punt SV+H + 維持 2 位 RP**。本文件探討「若反過來主攻 SV+H」時的選人邏輯——
即假設不在乎 IP / K / WHIP / ERA / QS / W，只想最大化 SV+H 一個類別時，挑 FA RP 該看什麼。

由 3 個 agent 從不同視角分析後綜合。

## 核心結論

**SV+H 是 opportunity-driven 類別**。SV+H 不由投球技術品質直接產生——
個人能力只負責「轉換率」，機會總量由球隊戰力與調度決定。
傳統 ratio / strikeout 數據對 SV+H 產量幾乎無預測力，它們只在「影響教練換不換人」時間接相關。

挑人邏輯三層：**機會供給 → 角色歸屬 → 角色續航**。

## 三 Agent 視角綜述

### 視角 1 — 機會與角色（誰拿得到第 8/9 局）

- 近 7-10 天**實際被擺的局面**比 depth chart 標籤可靠；「最近一次 save situation 教練派誰」= 最強單一訊號。
- **holds 路徑優於 saves**：save 一場最多 1 個、條件窄（登場領先 ≤3 分且收尾）；hold 機會池更大。撿兩個強隊固定 setup man 常勝過搶一個有爭議的 closer。
- 紅旗排除：committee bullpen、菜鳥試用 closer、傷兵即將回歸擠壓。
- 傳統 K/WHIP/ERA 衡量「投得好不好」，不是「教練給不給第 9 局」——對機會無預測力。

### 視角 2 — 角色續航（保得住多久）

不計分的品質指標真正用途 = **角色崩盤的領先指標**。

- **BB/9 是第一品質篩選器**：失控是 RP 被降級最快的原因。P70+（≤2.4）才算控球撐得住角色。
- **Barrel% allowed / xwOBACON**：被打品質差 = 下次崩盤只是時間問題。
- **xERA − ERA 落差**：ERA 遠低於 xERA = 運氣撐著、即將回歸的假貨（賣高訊號，不是買進）。
- **ERA / WHIP 雖不計分仍要看**——那是教練的決策輸入（換不換人看的是肉眼可見的 ERA/WHIP）。
- 樣本量：RP 季中 BBE 少，BBE <30 的 contact 數據低信心，此時權重移回 BB/9 + whiff%（累積快、樣本穩）。務必拉 2025 全季對照。
- 「機會穩但結構脆弱」的 RP 只能當 1-2 週短期賭注，不能當長持資產。

### 視角 3 — 球隊環境（機會總量上限）

- **球隊戰力區間**：SV+H 機會密度最高的是勝率約 .520-.580、靠 bullpen 守小分差贏球的隊。碾壓強隊 blowout 多反而稀釋 hold（領先 5 分以上不算 hold）。
- closer 看「1-2 分領先進第 9 局頻率」；setup man 看「領先交棒情境頻率」。
- **H2H 週賽制**：看未來一週場次數、對手強弱、主客場（多場次 + 對弱隊 + 多主場 = 機會多）。
- **bullpen 深度雙面性**：深度好 → 角色明確但 hold 被瓜分；深度差 → 機會集中但角色亂。要 save 找深度好球隊固定 closer，要 hold 找 8th-inning 角色單一的隊。
- **近 2-4 週實際累積 SV+H 速率** = 最直接主訊號（一次包進機會供給 + 角色 + 轉換率）。

## 挑選數據清單（優先序）

| 層級 | 看什麼 | 為什麼 |
|------|--------|--------|
| 1. 主訊號 | 近 2-4 週實際累積 SV+H 速率 | 一個數字包進機會 + 角色 + 轉換率 |
| 2. 角色歸屬 | 近 7-10 天進場情境（第 9 局?第 8 局?）+ 教練明示 | 行為 > 標籤 |
| 3. 機會總量 | 球隊勝率區間 + 本週場次/對手/主客場 | SV+H 上限由球隊製造的領先局面決定 |
| 4. 角色續航 | BB/9（≥P70）→ Barrel% allowed / xwOBACON → xERA−ERA 落差 | 預判機會會不會在 1-2 週內消失 |
| 排除 | committee、菜鳥試用、傷兵歸期、近期被降級使用 | 機會供給不穩 = 拿不滿 |

傳統 K/WHIP/ERA 只當「角色會不會崩」的旁證，不當選人主指標。

---

## 數據可得性盤點

依「本文件清單中的訊號」對照 `daily-advisor/` 現有程式碼，分三類。

### A. 目前程式碼可直接拿到

| 訊號 | 來源 | 現況 |
|------|------|------|
| SV+H 累積數（單期 / biweekly） | Yahoo API（stat id 89） | `RP_QUERIES` 已用 biweekly sort；`filter_by_savant` 已讀 `SV+H` 做 ≥2 門檻 |
| BB/9 | MLB Stats API season | `fetch_mlb_season_stats` 已算 `bb9` |
| ERA / WHIP | MLB Stats API season | 已抓 |
| K/9 | MLB Stats API season | RP path `_compute_derived_pitcher` 已算 `k_per_9` |
| xERA / xwOBA allowed / xwOBACON | Savant custom CSV | `fetch_savant_custom` 已抓三者（RP 顯示路徑目前只用 xERA/xwOBA） |
| GB% / BBE | Savant batted-ball CSV | `fetch_savant_batted_ball` 已抓 |
| whiff% | Savant pitch-arsenal CSV | `fetch_savant_arsenal_whiff` 已抓 |
| xERA − ERA 運氣落差 | 衍生 | `_compute_derived_pitcher` 已算 `era_diff` |
| IP/Team_G | 衍生 | RP path 已算 `ip_per_tg` |
| 2025 prior（上述同指標） | Savant 2025 CSV | `download_savant_csvs(2025)` 已支援 |

注意：xwOBACON / whiff% / GB% 的 **fetcher 存在**，但 RP 顯示路徑（`_fmt_roster_pitcher_rp`）仍是 v2（xERA/xwOBA/HH%/K9），未接 v4 指標。算「拿得到但 RP 路徑未接線」，工程量小。

### B. 可拿到但需寫程式碼

| 訊號 | 來源 | 缺口 |
|------|------|------|
| **saves / holds / blownSaves / saveOpportunities（個人累積）** | MLB Stats API pitching stat | API 回應已含這些欄位，`fetch_mlb_season_stats` 目前只 parse g/gs/ip/bb/k/era/whip — 加欄位即可。**這是 SV+H 真實產量，最優先** |
| **inheritedRunners / inheritedRunnersScored** | MLB Stats API pitching stat | 同上未 parse。inheritedRunners = setup man 被放在中段高 leverage 的訊號（holds 來源管道）；scored 比例 = 救火能力 |
| gamesFinished（GF） | MLB Stats API pitching stat | 同上未 parse。GF = closer 識別 proxy。**但 SV+H 不分 save/hold → GF 非必須**：有真實 saves/holds 數就不需此 proxy。殘餘價值僅 closer 角色穩定度（只服務 save 半邊），優先序低 |
| Barrel% allowed | Savant custom（加 `barrels_per_bbe` selection） | SP v4 沒用 Barrel%，RP 路徑需自行加 selection |
| 球隊勝率 / 戰力 | MLB Stats API standings | `_fetch_team_games` 只抓 team games 數，沒抓 W-L 戰績 |
| 本週對戰行程（場次/對手/主客場） | MLB Stats API schedule | `stream_sp_scan.py` 已有 schedule parser，但 RP scan 未接入 |
| 近 2-4 週 SV+H 速率趨勢 | Yahoo biweekly 多期 snapshot | 目前 `fa_history.json` 只存 %owned snapshot；要存多期 SV+H 才能算趨勢 |
| 球隊 save situation 供給（小分差勝場頻率） | MLB schedule + linescore final score | 抓賽程最終比分算分差分布，需新程式碼 |
| 近期 game log 角色 proxy | MLB Stats API gameLog | gameLog 可抓 per-game saves/holds — 能看「最近幾場有沒有記 SV/H」（非進場局數，但可作角色 proxy） |

### C. 無法拿到 / 無法量化（只能靠判斷）

| 訊號 | 為什麼 |
|------|--------|
| 教練明示 closer（記者會語言、beat writer 引用） | 文字新聞，無結構化來源 |
| committee bullpen 宣告 | 同上 |
| 傷兵即將回歸的具體時間表 | 新聞 / 球隊內部資訊；MLB API 只給 IL 狀態，不給「預計幾號歸隊」 |
| 菜鳥試用期 / 角色未定的脈絡 | 質性判斷 |
| 進場「局數」精確值（第 8 vs 第 9 局） | 需逐場 parse play-by-play game feed，成本過高；實務上以 GF / gameLog SV/H 作 proxy 替代 |
| leverage index（gmLI / pLI） | MLB Stats API 不提供，需 FanGraphs；目前無此資料源 |
| bullpen 深度的質性判斷（角色分工明不明確） | 可從 RP 使用分布粗估，但「明確 vs 混亂」終究是判讀 |

---

## 落地建議（給 RP 框架 v4 升級時參考）

優先序明確：B 類的 **saves / holds / blownSaves / saveOpportunities / inheritedRunners**
是 SV+H 評估缺最大的一塊，來源就在現有 MLB API 回應裡，只差 `fetch_mlb_season_stats` 加 parse——投報率最高，應優先做。

**GF 不在必做之列**：SV+H 為合併類別、不分 save/hold，GF 作為「closer 識別 proxy」的功能用不上；
且有真實 saves/holds 數後 proxy 即多餘。GF 留作 closer 角色穩定度的 optional 旁證。

機會供給類（球隊勝率、賽程）次之。趨勢類（多期 SV+H snapshot）需要先改 `fa_history.json` schema。

C 類訊號保留給 `/player-eval` / `/waiver-scan` 手動判斷層，不進機械層。

---

## 大名單產生方式（2026-05-19 手動走驗證）

挑 FA RP 的 step 1-2 — 產生候選大名單。採 **production-first**：先從 SV+H 產出源頭找人，
再回頭篩 FA。優於 FA-first（先撈 Yahoo FA RP 清單再逐人看 SV+H）——
後者受 Yahoo AR 排序失準影響會漏掉真正的角色持有者（驗證：全聯盟 14d SV+H 第一的
Cade Smith 不在 FA-AR-top-25 清單裡，FA-first 會完全漏掉）。

### Step 1 — MLB 全聯盟 14d SV+H 排行

MLB Stats API byDateRange 投手排行榜，一次 call 拿全聯盟（免 token）：

```
https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group=pitching
  &startDate=<today-14d>&endDate=<today>&sportId=1&playerPool=All&limit=900
```

每筆 split 取 `stat.saves + stat.holds`，filter `≥3` → 全聯盟 SV+H 產出者。
2026-05-19 跑出 33 人。

> 「各隊 SV+H 前三名」的構想實務上塌縮成此「全聯盟 ≥3」— 一隊 14 天內 4+ 人同時
> SV+H≥3 幾乎不發生，per-team-top-3 條件不起作用。直接全聯盟排行，省掉逐隊撈 roster
> （30 隊 × ~8 RP ≈ 240 次 gameLog call）。

### Step 2 — 交叉 Yahoo FA

把 Step 1 名單餵 `yahoo_query.py fa --position P --names "<逗號分隔名單>"`，
回傳的即 FA（`--names` 會自動翻頁直到全部找到或 max_pages）。
2026-05-19：33 人 → 23 人確認 FA（+2 筆名字比對失敗，見下）。

### 已知限制 / SOP code 待辦

- **`SV+H≥3` 是 floor 不是 trimmer**：23 人中 16+ 人並列 SV+H=3，光憑 SV+H 排不出前 4
  → 收斂到 LLM 的 4 人必須靠後續品質/角色/球隊供給數據（step 3）。
- **`--names` filter 比對失敗**：對撇號（Riley O'Brien）/ 重音（Luis García）exact match
  失敗 → 需加 accent + apostrophe 正規化。
- **不以 position label 剔除候選**（2026-05-19 修正）：SP,RP 兩用 ≠ 非 SV+H 來源。
  position 是 eligibility 不是現役角色 — swingman 若正被用於 SV+H 局面（如 PJ Poulin
  14d 2SV/1H），`SV+H≥3` floor 已證明其現役角色。floor 本身即角色證明，不需也不應再加
  position hard rule。
- **floor 鬆緊待校準**：`≥3` 不漏剛沉寂的 closer 但留太多人（23）；`≥4` 較準但有 SV+H
  lumpiness（剛上任 <14d 的 closer 累積不足）漏接風險。程式碼版機器可對 23 人全跑
  step 3 → 用 ≥3；手動走階段收 ≥4 求 tractable。
- **production-first 副產物**：23 個 FA SV+H 產出者證實本聯賽 punt-SV+H 風氣濃，
  SV+H 在 waiver wire 上很便宜。

---

## 候選池縮減方式（2026-05-19 手動走驗證）

step 3 — 把大名單（23 人）縮到交 LLM 的 ~4 人。手動走實測多種篩法，定案 **rank-sum**。

### 三個排序軸（皆可量化、皆 cheap fetch）

| 軸 | 指標 | 角色 | 來源 |
|----|------|------|------|
| 角色續航 | BB/9（季線）| 控球，崩盤領先指標；RP 小樣本下信心最高（保送不產生 BBE）| MLB season |
| 角色續航 | whiff%（usage-weighted）| stuff，BB/9 的 cross-check（高 BB/9 + 高 whiff = 風格非崩盤）| Savant arsenal |
| 機會供給 | 球隊近 14d 勝率 | 球隊製造 SV+H 機會的環境 | MLB schedule |

> 為何不用 Barrel%/xwOBACON：RP 季中 BBE 常 <40，contact-quality 指標噪音過大，
> 不適合當篩選層（見上「核心結論」）。三軸全用 MLB API + Savant arsenal，零 contact CSV。

### 篩法演進（手動走實測）

| 篩法 | 23 人 → | 問題 |
|------|--------|------|
| 負向淘汰（SV+H floor / BB/9 / BB/9∩whiff bottom-on-both）| 每招只縮一點（→19）| 報酬遞減；負向淘汰湊不到目標人數 |
| 三軸皆 top-1/3 交集 | → 1 | 過度塌縮（(1/3)³≈1/27）；邊界脆弱；獎勵全能、懲罰專才 |
| 三軸 ≥2 在 top-1/3 | → 6 | 退化成「熱隊 + 一項技術」；對失敗軸無下限（Stanek BB/9 全池最後仍過關）|
| **rank-sum top-N** ✅ | **→ 取 top-4** | 按比例懲罰爛軸、不卡硬門檻、對最吵那軸的邊界噪音不敏感 |

**定案**：三軸各自 rank → rank-sum 升序 → 取 top-N（N 視 LLM 窗口品質，目前 4）。

### 2026-05-19 結果（rank-sum top-4）

| 球員 | BB/9 rk | whiff rk | 團隊 rk | rank-sum |
|------|:---:|:---:|:---:|:---:|
| Adrian Morejon (SD) | 5 | 6 | 3 | 14 |
| Matt Festa (CLE) | 4 | 12 | 3 | 19 |
| Jason Adam (SD) | 7 | 13 | 3 | 23 |
| Kevin Kelly (TB) | 3 | 20 | 1 | 24 |

→ 交 LLM 層做角色查核 / news / 賽程前瞻。

### 已知限制 / SOP code 待辦

- **團隊 14d 勝率是三軸最吵的**：13 場樣本、回溯型、且是球隊非球員。Agent 3 視角原選的
  機會供給指標是「本週對戰場次數」（前瞻、schedule 可精確讀）。落地時應評估改用前瞻
  場次數，或兩者並用。
- **rank-sum 等權加總**：三軸權重相同未經驗證。若實戰發現某軸更具預測力，可改加權。
- **whiff% 樣本邊緣**：RP 季中 ~300 球，低於 Savant arsenal 百分位基線 ≥500 球；rank
  仍可用（相對排序），但絕對值信心打折。
- rank-sum 法不需 top-1/3 cutoff（直接排序取 top-N），比嚴格/≥2 交集法穩健 — cutoff
  只在交集法用到。

---

## LLM 層輸入設計（2026-05-19 手動走驗證）

step 4-5 — 把 rank-sum top-4 交 LLM 做 4 選 1。

### 設計原則：LLM 層要 thin

機械層（step 1-3）**已經用 quant 數據選出 top-4**。LLM 層的工作是 C 類判斷
（角色安全 news / committee / 傷兵 / 賽程前瞻），**不是重做 quant 排序**。

把全部 quant 數據丟給 LLM 會：(a) 叫它重算機械層做過的事；(b) 稀釋它對 C 類的注意力；
(c) 14 個指標各佔 ~7%，單一指標影響性過小、被做成無重點的平均。對齊專案 v4 砍相關
指標家族、避免「重複投票」的同一原則。

### LLM 輸入結構（兩層）

**核心層（LLM 主戰場）**：角色安全 news check（closer/setup 確定性、committee、傷兵
擠壓、菜鳥試用）+ 本週賽程前瞻（場次/對手/主客場）。

**精簡 context（每位 1 行 profile，不是 N 個獨立指標）**：
`14d SV+H(SV/H split) · BB/9 · whiff% · ERA+IP · 球隊14d勝率 · rank-sum名次`
+ 3 個角色相關訊號：近 10 場 SV/H pattern · blownSaves（+SVO 成對）· 本週賽程。

**明告決策階層**：角色安全是 first-order，quant profile 是 second-order context。
不要 LLM 做指標平均。

### 排除的指標 + 理由（實撈驗證）

| 指標 | 排除理由 |
|------|---------|
| Barrel% / xwOBACON | 實撈 4 人驗證：兩指標**自相矛盾**（Morejon xwOBACON 全組最差 .350 / Barrel% 全組最好 3.2%）；RP BBE 僅 50-63（剛過門檻）、Adam BBE 小到 Savant batted-ball 榜不收錄；barrel 計數 2-5，一支 ≈1.6pp 噪音 → context-only，最多一行 caveat，不進篩選層、不當 LLM 主指標 |
| xERA − ERA | 對 SV+H 決策落在兩張凳子間：角色安全看的是**教練視角 raw ERA**（教練看不到 xERA）；投手品質已被 BB/9+whiff% 涵蓋。與主指標一致時冗餘（Morejon/Festa）、不一致時不可信 → 不進 LLM 輸入。ERA 的「shiny 數字陷阱」（如 Adam ERA 1.15/僅 15.7 IP）由 profile 行 **ERA 永遠配 IP** 解決，不需 composite |
| 2025 prior / BBE 獨立項 / inheritedRunners | 對 4 選 1 邊際效用低；prior 是抓 breakout/slump 用，4 人當季 quant 已過關 |

> **SVO（saveOpportunities）修正**：原列排除，2026-05-19 實撈修正 — blownSaves 單看不可
> 解讀（BS=4 是多是少要看分母），SVO 與 blownSaves **成對**提供（不獨立排序用）。

### 決策脈絡（非數據，但 LLM 必須知道）

- **機會成本 / 比較對象**：我方**無** SV+H RP 時 → 撿人 = 放棄一個 SP 串流格（跨類別取捨）；
  我方**已有** SV+H RP（incumbent，2026-05-19 起為 Kelly）時 → 比較對象是 incumbent，
  換人 = drop incumbent（同類別替換）。
- **聯賽策略**：現行 Punt SV+H，這是「放 1 個 RP 主攻 SV+H」的小幅調整，非全盤轉向。
- 賽制 7×7 H2H One Win；**只挑 1 個**。

### 要 LLM 輸出

verdict 視我方是否已有 SV+H RP 分兩種情況：

**情況 A — 已有 SV+H RP（incumbent）**：scan 產出純 FA 候選（incumbent 已 rostered、
不在 FA 池）。verdict = 最佳 FA **vs incumbent** → 「換」（指名 FA + drop incumbent）
或「hold」（不動）。**預設 hold** — FA 需在 SV+H 產出 + 角色穩定度上**明顯**優於
incumbent 才換（一次 acquisition 成本，不為邊際提升 churn）。「明顯優於」交 LLM 自由
reasoning，不卡 binary 門檻。

**情況 B — 無 SV+H RP**：verdict = top-N 選 1 + 理由，或「都不值得佔一個 SP 串流格
→ pass」。

機械層 Step 5 一併撈 incumbent 當週同款三軸 + 訊號，供情況 A 做 apples-to-apples 比較。

### LLM 自己探索（C 類，無結構化數據）

closer/setup 角色確定性、committee 與否、傷兵（本人 IL / 球隊 closer 傷癒回歸擠壓）、
菜鳥試用、近期角色變動。針對性問題：SD 是否已因連續 blown saves 移除某人 save 角色。
本週對手脈絡（對手戰績 / 打線強弱）亦由 LLM 自行查證。

### 2026-05-19 verdict（手動走完整跑完）

news check 後 4 選 1 → **Kevin Kelly**（險勝 rank-sum #1 Morejon），**已執行 add**。

- 決定關鍵：實際 SV+H 產出最高（14d 5 / 近 10 場 7）、控球菁英（BB/9 1.61）、blownSaves 僅 1。
- rank-sum #1 Morejon 被 C 類資料降級：SD 首席 setup 角色雖穩，但 save 上限封死
  （SVO 5 / blownSaves 4）、產出反輸 Kelly — 正是 LLM 層存在的意義。
- 監看點：Kelly whiff% 21.1%（全池最弱）；TB committee 環境下若 stuff 續跌可能被往下調。

→ 完整 SOP（step 1 production-first → step 2 Yahoo 交叉 → step 3 rank-sum → LLM news
check → verdict）手動走一輪驗證完成。落地為自動化腳本時以此文件為規格依據。
