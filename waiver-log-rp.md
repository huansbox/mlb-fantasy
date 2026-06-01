# Waiver Log — RP（SV+H 主攻）

> RP-SV+H 子系統的球員追蹤，與 `waiver-log.md`（打者 / SP）分離。
> 評估 SOP 見 [`docs/rp-svh-metrics.md`](docs/rp-svh-metrics.md)。
> 每週用該 SOP 重掃 FA SV+H 產出者，與隊上 RP（incumbent benchmark）比較 → 明顯更優才換。

## 隊上 RP（SV+H 持有）

### Gregory Soto（PIT, RP）— added 2026-06-01（drop Kevin Kelly）

- **取得**：FA $0 即時生效（VPS roster_sync 自動偵測，commit `71168c7` `+Gregory Soto, -Kevin Kelly`）。
- **2026-06-01 eval（vs King/Ferrer，只看 SV+H）**：三者最強 — SV+H 13（最高）、ERA 1.95 / WHIP **0.76** / K 32。46% owned（市場已認證）。
- **選他理由**：三者唯一往 closer 走（save 上限 > setup hold）；近 9 場 8 場無失分、11:2 K:BB；教練 Don Kelly 偏好 closer 選項（雖 noncommittal）。
- **監看點**：① **trade risk** — PIT 賣家 + 左投 closer = 7 月 deadline 熱門標的，換隊後 SV+H 角色或波動。② closer 角色未完全坐穩 + PIT 弱隊（本週客場打 HOU/ATL 強旅）→ 短期 save 產量可能僅 0-2，價值看中期接管九局後兌現。
- **incumbent benchmark**：與 Ferrer 並列為 FA RP 掃描比較基準 — 新 FA 候選需**明顯優於** Soto/Ferrer 才換。

### José A. Ferrer（SEA, RP）— hold（2026-06-01 eval）

- **2026-06-01 [eval] vs Soto/King（只看 SV+H，drop 一人）**：結論 = **hold（留）**。
- 本季 SV+H 10、ERA **1.75** / WHIP 1.25 / K 22。季中由 WSH 交易至 SEA（換 Harry Ford + Issac Lyon）。
- role 上升：Dipoto 稱 Mariners「No.1 bullpen target」、定位 7-8 局 setup（左投版 Matt Brash）、fastball 觸 100 mph、近況好（剛 close out vs ATL）。closer = Andrés Muñoz → hold 為主、SV 偶有。
- 本週賽程 3 home NYM + 3 away DET（中等）。role 軌跡向上，留著。
- **incumbent benchmark**：與 Soto 並列為 FA RP 掃描比較基準。

## FA 觀察中

### Rico Garcia（BAL, RP）— 短期 SV 窗口

- 2026-05-19 掃描 rank-sum #3（24.5），38% owned（聯盟關注度高）、ERA 0.45、14d 3（2SV/1H）。
- BAL closer Ryan Helsley 在 IL（肘部發炎，無韌帶傷），**目標 5 月底回歸** → Garcia 的代理 closer
  SV 窗口僅剩 ~1-2 週，回歸後降回 committee setup。30d SV+H 5（當時對照 incumbent Kelly 8，Kelly 現已換成 Soto/Ferrer）。
- **不換理由**：SV 窗口短 + 30d 產量低，非「明顯優於」。一次 acquisition 不為一週 SV 租約 churn。
- **觸發條件**：若 incumbent（Soto/Ferrer）監看點觸發且 Helsley 尚未回歸 → Garcia 可作短期 SV 補強。

### Adrian Morejon（SD, RP）

- 2026-05-19 連兩週 rank-sum #1，SD 首席 setup（closer = Mason Miller，無 SV 路徑）。
- 角色穩，但 ERA 5.09（HR 率異常高、command 問題）、4 BS / 5 SVO（多為 setup 揹的失分，非 closer 降級）。
- 若 incumbent 監看點觸發，Morejon 是 holds 路徑替代候選 — 但近況 ERA 風險未解，優先序低於角色穩定的選項。

## 已結案

### Bryan King（HOU, RP）— dropped 2026-06-01（撿 Trevor McDonald）

- VPS roster_sync 自動 commit `a149b1a`（`+Trevor McDonald, -Bryan King`）。
- **drop 理由（2026-06-01 eval 確認）**：三者數據墊底（SV+H 11、WHIP 1.30 / K 19 / ERA 2.84）+ role 下降（HOU 明說要分散其 high-leverage、「為第七局找別人」+ 去年被操過頭 workload-health 疑慮）。closer = Hader，無 SV 路徑。本週賽程順風（全主場打 PIT/ATH 弱旅）是唯一優勢但屬單週 noise，不敵結構性 role 下滑。

### Kevin Kelly（TB, RP）— dropped 2026-06-01（撿 Gregory Soto）

- VPS roster_sync 自動 commit `71168c7`（`+Gregory Soto, -Kevin Kelly`）。added 2026-05-19，持有約 2 週。
- **drop 背景**：2026-06-01 RP eval 順帶註記 Kelly（2025 xERA 6.39，候選池最弱 stuff / whiff% 21.1%）比 King 更該檢視 → 實際被 drop 換 Soto。
- 持有期間：5/19 撿入（rank-sum #1 險勝 Morejon），30d SV+H 8 一度候選池最高、BB/9 1.61 控球菁英、ERA 2.42；但 whiff% 21.1% stuff 弱 + TB committee 無 SV 路徑（落後 Jax / Baker / Cleavinger）→ 升級空間有限，Soto 出現後讓位。
