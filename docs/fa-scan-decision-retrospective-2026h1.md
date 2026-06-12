# fa_scan 全季決策回溯（2026-03-25 ~ 06-12）— Walker 是不是孤例？

> **緣起**：`docs/fa-scan-eval-brainstorm-7x7.md` 的腦力激盪重度引用 Jordan Walker 單一成功案例，用戶質疑「只考慮一個 Walker 可能太武斷（也有沒那麼成功的推薦）」。本文件是回答：盤點開季以來**全部** add / drop / watch / pass 決策的實際後果，並檢驗哪些訊號當時就能把命中與落空分開。
> **方法**：決策清單來自 waiver-log.md（含 git 歷史挖掘 — 4 月底曾 reset）+ roster_config.json commit 時間線；後果數據來自 MLB Stats API `byDateRange`（決策日起 30 天窗，至今未滿 30 天則到 06-12）。球員 ID 全部經 MLB search API 當場解析，無憑記憶 hardcode。
> **誠實註記**：①窗口用 OPS/counting 粗量，未做 7x7 類別加權；②傷病混雜（Correa/Jeffers 的退出是被迫非評估失誤）；③被搶球員的後續是「別隊拿到的」不完全等於「我們會拿到的」；④樣本小（打者 add n=13），結論只取方向不取精度。

## 1. 總分數板

| 決策類別 | n | 命中 | 落空 | 不可歸因（傷病/窗口太短）|
|---|---|---|---|---|
| 已執行 add（打者）| 13 | 8 | 1（Swanson）| 4（Correa 傷退 / Duran 中性 / Rafaela、Dubón 窗口太短）|
| 已執行 drop（打者）| 12 | 7 | **3（Hicks / Clemens / Steer — 全是「太快放掉自己撿對的人」）** | 2（強制：Jeffers IL、Altuve IL）|
| 觸發達成/被搶但未拿到 | 15 | —（hold 正確 9）| **6 真實漏接** | — |
| Pass 判斷（打者）| 12+ | 11+ | 1 邊緣（McMahon .773）| — |
| SP add/drop（4 月可考）| 8 | 7（Messick/Detmers add、Littell/Singer/Kwan 級 drop 全對）| — | 5-6 月 SP 高頻 churn 未逐一量化（見 §5）|

## 2. 已執行 add 的後果（撿入 vs 放掉，swap 日起 30 天）

| 日期 | 撿入（30d）| 放掉（30d）| 判定 |
|---|---|---|---|
| 04-01 | **Walker .951 / 8HR**（至今 .914 / 16HR）| Kwan .605 / 1HR（至今 .575）| 大勝 |
| 04-06 | Hicks .883 / 5HR | （Singer SP，跨類）| add 命中 |
| 04-10 | Grisham .682 / 5HR（至今 .783）| Butler .533（至今 .477）| 小勝 |
| 04-27 | Correa 6 場後傷退 | Tovar .606 | 傷病不可歸因 |
| 05-07 | **Swanson .452 / 1HR** | Correa（IL 無數據）| **唯一明確 add 失誤** |
| 05-19 | Clemens .801 / 5HR | Altuve（IL，.478）| 命中 |
| 05-20 | Duran .750 | Jeffers（IL）| 中性（被迫換）|
| 05-24 | Arraez .835 / AVG .338 | Swanson .464 | 命中（stop-loss 訊號正確）|
| 06-03 | Torres 1.005（7 場）| — | 早期命中 |
| 06-07 / 06-10 | Rafaela / Dubón | — | 窗口太短 |

**Add 端結論：可評估的 10 筆中 8 筆方向正確。Walker 不是孤例，是同一型成功裡最大的一筆。**

## 3. 三類失誤的解剖

### 失誤型 1 — Drop/churn 端（最貴、最集中）

| 案例 | 經過 | 代價 |
|---|---|---|
| **Liam Hicks** | 04-06 撿入 → 04-12/13 僅 7 天就換掉（理由：9 場 .185 BABIP 噪音）| drop 後 30 天 **.892 / 6HR / 25RBI**（C 位稀缺產出）；至今 .769 / 9HR |
| **Kody Clemens** | 05-19 撿入（雙年 P80/P80 確認）→ 05-28 僅 9 天 drop 換 RP | 之後 .801+ / 5HR；06-09 起 fa_scan 連 4 天推薦**撿回他** |
| **Spencer Steer** | 05-05 撿入（30d .863 命中）→ 06-10 換 Dubón | **隔天** fa_scan 即推薦撿回 Steer（「三軸碾壓 Dubón」）|

三案同構：**撿的判斷對了，放的判斷把對的成果丟掉**。當初的 add 理由（結構確認）並沒有失效，drop 是被當週情境（換 RP、換工具人）或短期噪音推走的。系統對「自己 9 天前為什麼撿這個人」沒有記憶。

### 失誤型 2 — 觸發達成但未執行（執行洞）

| 案例 | 觸發/推薦日 | 未執行原因 | 後 30 天 |
|---|---|---|---|
| **Miguel Vargas** | 04-12 觸發達成、建議 FAAB claim | 無對應執行（38% owned 升、疑被搶）| **.945 / 8HR / 21BB — 全季最大漏接** |
| Ryan O'Hearn | 03-27 首標 | 03-30 被搶（猶豫 3 天）| .871 / 4HR |
| Spencer Horwitz | ~05-19 起追蹤 | 05-28 確認期中被搶 | .886 / 3HR（12 場）|
| Kyle Manzardo | 05-19 起 watch | B-plan/C-plan 排隊 + K% spike 疑慮，至今未執行 | .872 / 3HR（18 場）|
| J.P. Crawford | 05-26 正式推薦 | 連 12 天未執行 | 1.150 / 3HR（9 場）後進 IL |
| Kody Clemens（首次）| 05-12 標「立即行動」| 7 天後才執行 | 幸運無代價（5% owned 沒人搶）|

對照組 — **品質 gate 擋下、事後證明擋對的**：Alvarez（觸發但 14d 下滑中 → 後 30 天 .536）、Evan Carter（單年 BB% 跳升未驗 → .534）、Garrett Mitchell（prior 全 <P40 → .615）、Brady House / Nolan Gorman（觸發進行中品質崩 → 正確淘汰）。**四月「觸發但未執行」的 4 案裡，gate 擋下的 3 案全對，唯一全 gate 通過的 Vargas 正是該執行而沒執行的。**

→ 評估層的校準其實不錯；**失靈的是「評估 → 執行」這條線**（位置衝突排隊、備案序列、確認天數、被搶競速）。

### 失誤型 3 — 熱度前導型推薦（用戶否決/猶豫反而對）

| 案例 | 推薦理由（當時）| 後果 |
|---|---|---|
| Joc Pederson（取代 Arraez）| 14d 5HR/OPS .945 爆發 + season P95/P95 | 被搶後 6 場 **.443**；且 platoon -28% 週 PA 盲區 |
| Gavin Sheets（A-plan）| 14d OPS 1.123 + prior P80 | 一週內崩至 .5 上下，Savant Δ 連跌被 LLM 敘事成「BABIP 有利」|
| Jac Caglianone（取代 Arraez）| 用戶 06-11 否決 | 結構性歸因後建立 Arraez 框架偏見標註 |

## 4. 最強的區辨器：發現路徑（structure-led vs heat-led）

把全部案例按「這個球員當初是**怎麼浮上來的**」分組：

- **Structure-led**（季線結構 / 雙年確認 / process 訊號帶出，14d 只作確認）：Walker、Vargas、Horwitz、O'Hearn、Clemens、Manzardo、Crawford、Steer、Arraez → **後果幾乎全部命中**（.80-.95 OPS 級）。
- **Heat-led**（14d OPS 爆發 / %owned ramp 帶出，季線數據事後補強）：Sheets、Pederson、Ballesteros、Mead、Caglianone → **後果幾乎全部落空**（.44-.73）。
- **品牌/急就章**（傷病空格急補大牌）：Swanson → 落空。

注意「雙年確認」**不是**充分區辨器 — Sheets prior P80、Pederson prior 雙年、Swanson 雙年全有，照樣崩。真正的差別在**誰是主驅動**：結構先看到、熱度來確認 = 可信；熱度先看到、結構來背書 = 不可信。這與專案既有的 no-hot-streak 哲學一致，但現行 payload 並沒有把「候選是從哪個訊號浮上來的」標出來 — LLM 每天看到的是同一張混合資料表。

## 5. SP 端速記（未逐一量化）

4 月的 SP 決策全對（Messick/Detmers add、Littell/Singer drop、Painter/Cavalli pass）。5 月起出現高頻 churn：Povich 持有 1 天、May 4 天、Holmes 添了又 drop 又添又 drop、Burke 三進三出。與打者端 churn 同病：**單日 verdict 被當成終局**，沒有跨日穩定性檢查。（SP 端的逐案 21d 對帳本來就是 C1 backtest 的工作，此處不重做。）

## 6. 對腦力激盪提案的修正（回答「Walker 武斷」質疑）

**質疑的回答**：Walker 不是孤例 — add 端命中率 ~8/10，structure-led 路徑整批有效。但質疑帶出了報告原本沒有的東西：**「找人」根本不是系統最弱的環節**。按實證代價重排：

1. **最貴：churn / drop 紀律**（Hicks、Clemens、Steer 三案 + SP 端同病）→ 直接強化 `verdict-ledger`（+stability gate）與 `marginal-swap-vector` 的 adopt_now 地位；ledger 應**同時記 add 理由**，drop 推薦必須面對「9 天前撿他的理由是否已失效」。
2. **次貴：執行洞**（Vargas/O'Hearn/Horwitz/Manzardo/Crawford 合計漏接 ~5 名 .85+ OPS 球員）→ 強化 037 trigger-schema（結構化觸發→行動）優先序；確認週期天數（「連 N 天」設計）在競速市場是成本，被搶 12 案中真有產出的僅 2 案說明聯盟整體很慢，但**好貨（gate 全過的）恰恰是會被搶走的那種** — 確認天數應與 %owned 動能聯動（owned-velocity divergence 提案的直接用例）。
3. **再次：heat-led 通道要降權**→ 新增一個腦力激盪清單上沒有的零成本提案：**discovery-channel tag**（機械層標注候選浮上來的首要訊號：structure / heat / market / news），讓 LLM 對 heat-led 候選強制提高證據門檻。`pass-audit-rescan` 的 14d OPS 重注入觸發須搭結構 co-signal（critic 已預警，本回溯實證確認）。
4. **breakout 家族（pedigree / process / projection prior）維持 pilot 不變**：它們強化的是 structure-led 路徑（實證有效側），但本回溯顯示其邊際價值排在 1-3 之後 — Walker 型的訊號系統其實「抓得到」（Vargas/Horwitz/Manzardo 都被抓到了），抓到後死在執行。先修執行，再放大偵測。

## 7. 結論一句話

系統的「眼睛」（structure-led 評估）已經及格，「手」（執行、放人、記憶）不及格 — 升級預算應該先花在手上。

## 附錄：數據快照

- 被搶 12 案後 30 天：真有產出僅 O'Hearn .871、Horwitz .886；其餘（Benge .465 / Young .562 / Raley .351 / Mead .729 / Lowe .696 / Cowser .717(3場) / McLain / Pederson .443 等）全數平庸 — **別隊的搶人命中率遠低於我們的 add 命中率**，耐心門檻本身是對的。
- Pass 後 30 天：Ballesteros .539 / Caballero .647 / Meidroth .703 / Stott .749 / McMahon .773 / Lewis .635 / Keith .701 — 全部未構成痛失。
- 量化窗口原始 JSON 由一次性腳本產出（MLB Stats API byDateRange），未入 repo；複現方式見標頭方法段。
