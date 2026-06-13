# Waiver Log — RP（SV+H 主攻）

> RP-SV+H 子系統的球員追蹤，與 `waiver-log.md`（打者 / SP）分離。
> 評估 SOP 見 [`docs/rp-svh-metrics.md`](docs/rp-svh-metrics.md)。
> 每週用該 SOP 重掃 FA SV+H 產出者，與隊上 RP（incumbent benchmark）比較 → 明顯更優才換。

## 隊上 RP（SV+H 持有）

> 2026-06-13：drop Soto 後，隊上僅剩 Ferrer 1 位純 RP（隊形考量讓出 1 格）。1 RP 與 punt SV+H 一致；若 SV+H 轉 contested 再用 `/rp-svh` 從 FA 串 save-getter。

### José A. Ferrer（SEA, RP）— 隊上唯一 RP（2026-06-13 留人）

- **2026-06-13 [eval] vs Soto（drop 1 RP，二選一）**：結論 = **留 Ferrer**。rp-svh 三軸 1-1-平（BB/9 **2.10** 勝 Soto 3.71 / K9 7.80 輸 / 30d SV+H 5 平）→ 決於角色安全層：Soto 三重威脅（球隊找 closer 取代 + deadline 交易籌碼 + 30d ERA 7.88 崩盤），Ferrer 控球菁英 + 角色上升 + ERA/WHIP 正資產 → 留 Ferrer。
- 2026 數據：SV+H 11、ERA **2.10** / WHIP 1.33 / K 26 / BB/9 2.10。Savant（v2）xERA 2.84 / xwOBA-a .267（>P90）/ Barrel%-a 4.2%（>P90）。
- role：SEA「牛棚最有價值手臂」、領銜全 MLB 中繼出賽、隊上多名後援傷兵 → leverage 升高；後段 setup（closer = Andrés Muñoz）→ hold 為主、SV 偶有。本週 3 home NYM + 3 away DET（中等）。
- **incumbent benchmark**：Soto 已 drop（6/13），Ferrer 現為唯一隊上 RP / FA RP 掃描比較基準 — 新候選需**明顯優於** Ferrer 才換。

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

### Gregory Soto（PIT, RP）— dropped 2026-06-13（隊形考量，drop 1 RP，留 Ferrer）

- **drop 理由（2026-06-13 /player-eval，vs Ferrer 二選一）**：rp-svh 三軸 1-1-平（BB/9 3.71 輸 Ferrer 2.10 / K9 10.43 贏 / 30d SV+H 5 平），決於角色安全層 — Soto 三重威脅同時觸發：① PIT 積極找 closer 取代他（Rosenthal 報導）② deadline 熱門交易籌碼（左投 + $7.75M 一年約，換隊恐丟 closer 變 setup）③ 30d 崩盤 ERA 7.88 / 2 BS + 季 ERA 靠 .194 BABIP + 3.6% HR/FB 撐（回歸已啟動）。SV+H 是 punt 類別不追上限，且其 SV+H 附帶 7.88 ERA 毒害 ERA/WHIP 兩格。6/01 撿入時標的 trade/role watch point 已成真。
- 持有期間：6/01 撿入（drop Kevin Kelly），約 12 天。closer 角色（9SV/12SVO）是唯一偏他的點，但角色三方受侵蝕 + 比率回吐 → 讓位給穩定的 Ferrer。
- ⚠️ 2026 live Savant 抓到同名打者（homonym），投手 contact quality 以 2025 prior（xERA 3.85 / xwOBA-a .305）為準。

### Bryan King（HOU, RP）— dropped 2026-06-01（撿 Trevor McDonald）

- VPS roster_sync 自動 commit `a149b1a`（`+Trevor McDonald, -Bryan King`）。
- **drop 理由（2026-06-01 eval 確認）**：三者數據墊底（SV+H 11、WHIP 1.30 / K 19 / ERA 2.84）+ role 下降（HOU 明說要分散其 high-leverage、「為第七局找別人」+ 去年被操過頭 workload-health 疑慮）。closer = Hader，無 SV 路徑。本週賽程順風（全主場打 PIT/ATH 弱旅）是唯一優勢但屬單週 noise，不敵結構性 role 下滑。

### Kevin Kelly（TB, RP）— dropped 2026-06-01（撿 Gregory Soto）

- VPS roster_sync 自動 commit `71168c7`（`+Gregory Soto, -Kevin Kelly`）。added 2026-05-19，持有約 2 週。
- **drop 背景**：2026-06-01 RP eval 順帶註記 Kelly（2025 xERA 6.39，候選池最弱 stuff / whiff% 21.1%）比 King 更該檢視 → 實際被 drop 換 Soto。
- 持有期間：5/19 撿入（rank-sum #1 險勝 Morejon），30d SV+H 8 一度候選池最高、BB/9 1.61 控球菁英、ERA 2.42；但 whiff% 21.1% stuff 弱 + TB committee 無 SV 路徑（落後 Jax / Baker / Cleavinger）→ 升級空間有限，Soto 出現後讓位。
