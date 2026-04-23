# SP 決策回測追蹤

> **用途**：記錄每次 SP drop / hold / add / pass 決策當下的框架判斷與實際執行，後續（2-8 週後）回頭驗證框架準確度。每筆決策附「回測問題」供將來回頭比對。
>
> **維護**：每次做 SP 重大決策時新增條目。每 2-4 週一次回測 session 更新「後續走勢」欄位。

## 如何讀這份文件

每個條目有：
- **決策內容**：做了什麼
- **框架依據**：當時用哪個 framework / 訊號
- **當時數據 snapshot**：凍結當下數據
- **回測問題**：未來回來要問的具體問題
- **後續走勢**：（回測時填）球員後續實際表現
- **回測判定**：（回測時填）框架判對 / 判錯 / 部分對

---

## 2026 賽季決策紀錄

### 1. Littell → Messick 開季替換（2026-04-01）

**決策**：開季時把 Tyler Littell 換成 Parker Messick
**執行方**：用戶手動（賽季準備期）
**框架依據**：2025 Savant 對比 — Messick P80-90（xERA 3.07 / HH% 29.8% / 121 BBE）vs Littell 未知數據
**當時數據**：Messick 2025 xERA 3.07（僅 AAA 120+ 局）

**回測問題**：
- Messick 2026 賽季至少有一段期間 Sum ≥20？
- CLE 是否給他完整 rotation slot（無 innings limit）？
- 有無更值得優先 slot 給他的 FA 出現被錯過？

**後續走勢（2026-04-23 更新）**：Messick 5 GS / v3 Sum 22（xwOBA .285 / IP/GS 6.13 / K/9 8.51 / BB/9 2.35），球隊主力無 innings limit 跡象
**回測判定**：**✅ 正確**（當季 v3 顯示他已是真菁英）

---

### 2. Whitlock 軟 cut（2026-04-13）

**決策**：Whitlock（RP/SP 雙資格）drop，用 Detmers 取代 + Kelly 從 IL 歸隊進 SP slot
**執行方**：用戶執行（軟 cut 策略 — 每天排 BN 不上場，等 Kelly 歸隊完成 drop）
**框架依據**：v2 框架 — Whitlock 2026 xERA 6.31 / xwOBA .390 雙項 <P25 + 2025 亦中後段 → 雙年結構性弱確認
**當時數據**：Whitlock BBE 13（低信心）/ HH% 30.8% P90（唯一亮點 — 但樣本不足撐）

**回測問題**：
- Whitlock drop 後 ERA 是否回歸真實水準（xERA 6.31）？還是反彈為 slump 誤判？
- Detmers 接替後 5-10 場表現如何？值回票價？
- Kelly 歸隊後 2-3 場實測（BBE 30+）下 Savant 品質對應 2025 水準？

**後續走勢（2026-04-23 更新）**：
- Whitlock 04-17 drop 後狀況：未追蹤
- Detmers：v3 Sum 23（xwOBA .266 / IP/GS 5.73 / K/9 9.73 / BB/9 2.51），真菁英
- Kelly：04-14 歸隊 2 場災難（ERA 9.31 / xwOBA .451 / v3 Sum 2），BBE 17 仍驗證期

**回測判定**：**✅ Whitlock drop 正確**（Detmers 填 slot 是明顯升級），⚠️ **Kelly 歸隊是賭博**（短期結果慘但樣本不足）

---

### 3. Hicks drop / Detmers add（2026-04-12）

**決策**：drop Liam Hicks（C/1B，batter）/ add Reid Detmers（SP/RP）
**執行方**：用戶執行
**框架依據**：v2 batter 框架 — Hicks 近 9 場 .185 / 0 HR / 1 RBI 走低 + 前 5 場 .467 全 BABIP 噪音 + HH% 兩年 <P25；Detmers xERA 2.47 >P90 buy-low
**當時數據**：Detmers $0 FAAB 免費取得

**回測問題**（SP 端）：
- Detmers xERA 2.47 是否維持？還是 breakout 未確認？
- BN 配置改 1bat+2SP（多收一個 SP slot）策略驗證：週 IP 提升？

**後續走勢（2026-04-23 更新）**：Detmers v3 Sum 23 三項全 >P80，2025 IP/K 未查但 2026 明顯菁英
**回測判定**：**✅ 大勝**（$0 取得的 SP 成為全隊第三強）

---

### 4. Nola 結構性 cut → hold（2026-04-20 啟動 → 04-23 降級）

**決策歷程**：
- 2026-04-20：CLAUDE.md 啟動「Nola 結構性 cut 候選」（v2 Sum 11 + 2025 Sum 15 判雙年弱）
- 2026-04-22：fa_scan #98 找到 Meyer/Griffin/Pfaadt 三候選，推薦 drop Nola / add Meyer FAAB $3-5
- 2026-04-23：三視角重評（進階/傳統/印象）發現 v3 框架盲點 → 降級為 **hold 2 場觀察**
- 2026-04-23（下午）：進一步三視角檢視 Nola/López/Holmes → 2/3 視角仍認為 Nola 該走但 v3 判最後；證實 v3 結構訊號缺失

**執行方**：用戶最終選擇 hold（選項 A，hold 2 場重評）
**框架依據**：v2 判 cut → v3 判 hold → 三視角分歧
**當時數據**：
- 5 場 1-4 / 5.06 ERA / xERA 4.70 / xwOBA .342 / xwOBACON **.424（關鍵）**
- FB 速度 90.8-91.7 mph（= 2025 災難年水準）
- K/9 9.79 / IP/GS 5.33 / BB/9 3.38 / 2 QS

**回測問題**：
- 速度是否回升到 92+ mph？（三視角最關注）
- xwOBACON 是否回落 <.370？
- 連 2 場 <5 IP 或 3+ ER 是否發生？
- 若 Nola 被任何一方視角判對（實際持續惡化）→ 為何 v3 漏了？
- 若 Nola 反彈（速度回來、xERA 改善）→ 為何三視角過度悲觀？
- 2026-05-01 前 2 場結果應給明確訊號

**後續走勢**：（2026-05-01 後回測填）
**回測判定**：（待定）

---

### 5. Meyer add recommended → pass（2026-04-22 推薦 → 04-23 撤回）

**決策歷程**：
- 2026-04-22：fa_scan 判 Meyer Sum 18 > Nola 11 三項全勝 → 推薦 FAAB $3-5 add
- 2026-04-23：三視角 Meyer/Griffin/Nola 評估 → Meyer 是「邊際升級」不是 slam dunk
- 2026-04-23：降級後決定 hold Nola → Meyer add 撤回

**執行方**：用戶未執行 FAAB（pass）
**框架依據**：v2 推薦 → 三視角重評後改判
**當時數據**：
- Meyer 2026：xERA 4.39 / xwOBA .332 / HH% 38.6 / K/9 10.08 / BB/9 3.96 / IP/GS 4.86 / 0 QS
- Meyer 2025：xERA 4.80 / xwOBA .337 / HH% 48.2 / 64.7 IP（post-TJ + 髖部盂唇手術後）
- 18% owned / 3 日 +5 窗口關閉中

**回測問題**：
- Meyer 是否被其他 GM FAAB 撿走？時間點？
- Meyer 後續 3-5 場 ERA / K / IP 走勢 — 是否像 Agent 3 預期「26 歲反彈年」，還是 Agent 1 擔心的「K 撐住但 contact 崩」？
- 若 Meyer 大噴 → pass 是賣低錯過；若崩 → pass 是避開地雷
- v3 推翻 v2 判斷的 Meyer case 最後誰對？

**後續走勢**：（2026-05-10 後回測填）
**回測判定**：（待定）

---

### 6. Ragans Slump hold（2026-04-20 啟動）

**決策**：不 drop Cole Ragans，按 Slump 框架等樣本回歸
**執行方**：用戶 hold（至今）
**框架依據**：v2 框架 — 2026 Sum 16 xERA 5.18 但 2025 Sum 27 xERA 2.67 菁英底（61.7 IP ≥50）→「當季低 + 前一年高 → Slump 候選」
**當時數據**：
- 2026：ERA 6+ / xERA 5.18 / xwOBA .358 / HH% 34.1% >P90 / BB/9 7.71（極端）
- 2025：xERA 2.67 / xwOBA .256 / 39.4% / 61.7 IP

**回測問題**：
- ERA 是否回歸 xERA 5.18 水準？（v2 判斷底）
- **BB/9 7.71 command 崩壞是否機制問題？**（v3 才揭露的隱憂，v2 沒特別標）
- 2025 菁英底（xERA 2.67）能否拉回 2026 到 P70+？
- 回歸時間：4 週？6 週？還是已經不是那個 Ragans？
- H2H 短期代價：hold 期間累積多少 ER 拖隊 ERA？

**後續走勢**：（每 2 週更新）
- 2026-04-13：DTD（4/8 平飛球打到左手拇指，挫傷無結構損傷）
- 2026-04-14：news check 確認無傷歸隊
- 2026-04-23：v3 Sum 5（xwOBA .395 / IP/GS 4.20 / K/9 9.43 / BB/9 7.71），command 崩壞持續

**回測判定**：（待定，預估 2026-05-15 前不該動手）

---

### 7. Kelly IL 歸隊驗證（2026-04-14 起）

**決策**：Kelly 從 IL 歸隊後 hold 於 BN slot，觀察 3-4 場驗證
**執行方**：用戶 hold（依計畫）
**框架依據**：無明確 framework 訊號（BBE <30 低信心排除），賭 2025 表現延續
**當時數據**：Kelly 2025 水準未查；2026 歸隊 2 場災難（ERA 9.31 / xwOBA .451）

**回測問題**：
- Kelly BBE 到 30+ 後（~Week 6 預估）Savant 是否對應 2025 水準？
- 若仍 xERA >4.5 → 是 IL 歸隊 ramp-up 還是真退化？
- AZ 輪值角色是否穩定？

**後續走勢**：（BBE 到 30 後回測）
**回測判定**：（待定）

---

### 8. Buehler 03-21 3d +13 被搶（2026-04-22 結案）

**決策**：未 add Walker Buehler（因 FAAB 優先序給 Meyer 考量 + IP/GS 4.1 短局硬傷）
**執行方**：被動（被其他 GM 搶走）
**框架依據**：v2 判 IP/GS 4.1 + 2025 極差 + %owned 3d+13 暴漲 → 窗口關閉前未做決策
**當時數據**：
- 2026：Sum 22 / xERA 3.99 / xwOBA .318 / 運氣 -1.76 買低 / IP/GS 4.1 短局
- 2025：xERA 5.41（極差）

**回測問題**：
- Buehler 被搶後 ERA / IP/GS 走勢：IP/GS 是否拉長到 5+？xwOBA 維持？
- SD 短局用法是否改變？
- 若 Buehler 後續爆發 → 我方錯過；若崩 → 避開地雷

**後續走勢**：（每 2 週更新）
**回測判定**：（待定）

---

### 9. Chad Patrick 04-20 被搶

**決策**：未 add Patrick（觀察中尚未決策時就被搶）
**執行方**：被動
**框架依據**：22% owned 窗口收窄，未及時執行
**當時數據**：v3 Sum 24（xERA 3.06 P90 / xwOBA .281 P80-90 / 2025 P60 有底 / MIL 強隊）

**回測問題**：
- Patrick 後續是否維持 P80-90 Savant 水準？
- MIL 強隊 W 加成兌現？
- 這是「我方反應太慢」的典型案例？是否該改「首推 → 24h 內 FAAB 不 wait」

**後續走勢**：04-23 仍 P80-90（fa_scan 觀察）
**回測判定**：**⚠️ 決策延遲錯過**（高機率他會持續表現，我方錯失）

---

## 持續追蹤項目（觀察中但未執行）

以下 SP 是目前 waiver-log 觀察中，每次 fa_scan 會自動更新狀態。若觸發決策，補 entry 到上方正式紀錄。

- Walbert Ureña — v3 Sum 23，最有潛力真正取代 Nola 的候選，等 BBE ≥30
- Ben Brown / J.T. Ginn / Tobias Myers — v2 高分但 v3 露餡（contact-quality 假菁英），回測這些人是否真的在接下來幾場被打回原形
- Brandon Pfaadt — 觀察「Sum 21 最高但 K/9 5.5 結構弱」的判斷是否正確（他會不會 K 起來變真取代候選）

---

## 框架版本演進 & 影響

| 時間 | 版本 | 關鍵改動 | 受影響決策 |
|------|------|---------|-----------|
| 2026-03-26 | v1 | 開季 Tier 制（Tier A/B/C）| Littell→Messick 開季換血 |
| 2026-04-20 | v2 | Sum scoring 連續分數（xERA + xwOBA + HH%）+ urgency 4 因子 + 14d Rolling | Whitlock drop / Nola 結構性 cut 啟動 |
| 2026-04-21 | v2（SP 版）| 對齊打者 v2 框架 + Pass 2 ✅/⚠️ tags | Meyer 推薦 add |
| 2026-04-23 | v3 design | Impact-weighted Sum（4 指標 10/7/7/5）+ Rotation active gate | Nola hold / Meyer pass |
| 待實作 | v3.1 planned | + xwOBACON / 速度 flag / 運氣 urgency | 等 v3 回測結果 |

## 元回測：框架本身的準確度

除了個別球員決策，也要追蹤**框架判斷模式**的成敗：

### v2 → v3 顯著分歧的案例

- **高估者（v2 Sum 高 → v3 Sum 低）**：J.T. Ginn (-16) / Tobias Myers (-14) / Cade Horton (-14) / Bernardino (-13) / Fedde (-10) / Pfaadt (-8)
- **低估者（v2 Sum 低 → v3 Sum 高）**：Nola (+4) / Paddack (+1)

回測問題：若這些人在接下來 2-4 週實際表現驗證了 v3 判斷（Ginn 崩、Nola 穩），則 v3 升級有效。若相反（Ginn 繼續 P80 Savant 維持、Nola 繼續衰退），v3 設計反而退步。

### v3 → 三視角分歧的案例

見文件 `docs/nola-lopez-holmes-triview-2026-04-23.md` — v3 判 López 最弱，但 2/3 視角判 Nola 最弱。這個案例直接決定 v3.1 是否啟動。

## 更新紀錄

- **2026-04-23 創建**：初版，涵蓋 9 筆歷史決策 + 元回測框架
- 後續每次 SP 重大決策 → 新增條目
- 每 2-4 週回測 session → 更新「後續走勢」欄位
