# 分析 2：跨守位替代價值（VOR）

> 基於 `分析1-格式類別貢獻評分.md` 的淨分，計算每位球員相對於守位替代水平的超額價值
> VOR = 該球員格式淨分 - 同守位替代水平球員的格式淨分
> VOR 越高 = 越值得提前選

---

## Step 9：各守位替代水平定義

12 隊聯賽，每隊需求如下。替代水平 = 該守位第 N 名球員（N = 聯賽需求 + 2~3 名板凳深度）。

| 守位 | 每隊先發需求 | 12 隊總需求 | 替代水平（第 N 名） | 替代球員 | 替代淨分 |
|------|------------|-----------|-------------------|---------|---------|
| **C** | 1 | 12 | 第 14 名 C | Gabriel Moreno 級 | **0** |
| **1B** | 1 (+UTIL 分攤) | 15 | 第 16 名 1B | Alec Burleson / Torkelson 級 | **+1** |
| **2B** | 1 | 12 | 第 13 名 2B | Matt McLain / Brandon Lowe 級 | **0** |
| **SS** | 1 | 12 | 第 13 名 SS | Dansby Swanson 級 | **+2** |
| **3B** | 1 (+UTIL 分攤) | 15 | 第 16 名 3B | Isaac Paredes / Caleb Durbin 級 | **0** |
| **OF** | 3 (+UTIL 分攤) | 40 | 第 42 名 OF | Chandler Simpson / Mike Trout 級 | **+2** |
| **SP** | 4 (+P 欄分攤) | 55-60 | 第 55 名 SP | 串流級先發 | **0** |
| **RP** | 2 (+P 欄分攤) | 30-36 | 第 30 名 RP | 中階 SU/邊緣 CL | **+1** |

### 替代水平解讀

- **SS 和 OF 替代水平最高（+2）**：即使選不到頂級，替代品仍有格式正貢獻（如 Swanson +2, Kwan +4）
- **2B 和 C 替代水平最低（0）**：替代品幾乎無格式貢獻，頂級球員的 VOR 最大
- **這就是為什麼 2B 稀缺性最致命**：不是頂級 2B 有多好，而是替代品有多差

---

## Step 10：全員 VOR 計算

### 打者 VOR 排名（Top 30）

| VOR 排名 | 球員 | 守位 | ADP | 格式淨分 | 替代淨分 | **VOR** | 套利標記 |
|---------|------|------|-----|---------|---------|---------|---------|
| 1 | Juan Soto | OF | 4 | +11 | +2 | **+9** | 公平定價 |
| 2 | José Ramírez | 3B | 6 | +9 | 0 | **+9** | 公平定價 |
| 3 | Vlad Guerrero Jr. | 1B | 18 | +10 | +1 | **+9** | 🟢 ADP 偏低 |
| 4 | Aaron Judge | OF | 2 | +10 | +2 | **+8** | 公平定價 |
| 5 | Bobby Witt Jr. | SS | 3 | +8 | +2 | **+6** | 公平定價 |
| 6 | Gunnar Henderson | SS | 12 | +8 | +2 | **+6** | 公平定價 |
| 7 | Ketel Marte | 2B | 33 | +6 | 0 | **+6** | 🟢 2B 稀缺加成 |
| 8 | Ronald Acuña Jr. | OF | 6 | +8 | +2 | **+6** | 公平（傷病折扣） |
| 9 | Freddie Freeman | 1B | 68 | +7 | +1 | **+6** | 🟢🟢 巨大套利 |
| 10 | Yordan Alvarez | OF | 35 | +7 | +2 | **+5** | 🟢 稍被低估 |
| 11 | Kyle Tucker | OF | 14 | +7 | +2 | **+5** | 公平定價 |
| 12 | Corbin Carroll | OF | 12 | +7 | +2 | **+5** | 公平定價 |
| 13 | Fernando Tatis Jr. | OF | 15 | +7 | +2 | **+5** | 公平（傷病折扣） |
| 14 | Bryce Harper | 1B | 47 | +6 | +1 | **+5** | 🟢 稍被低估 |
| 15 | Jazz Chisholm Jr. | 2B | 20 | +5 | 0 | **+5** | 🟢 2B 稀缺加成 |
| 16 | José Altuve | 2B | 116 | +5 | 0 | **+5** | 🟢🟢 巨大套利 |
| 17 | Ozzie Albies | 2B | 158 | +5 | 0 | **+5** | 🟢🟢 巨大套利 |
| 18 | Manny Machado | 3B | 39 | +5 | 0 | **+5** | 公平定價 |
| 19 | Mookie Betts | SS | 58 | +6 | +2 | **+4** | 🟢 稍被低估 |
| 20 | Riley Greene | OF | 79 | +6 | +2 | **+4** | 🟢 稍被低估 |
| 21 | Nico Hoerner | 2B | 105 | +4 | 0 | **+4** | 🟢 2B 稀缺加成 |
| 22 | Matt Olson | 1B | 49 | +4 | +1 | **+3** | 公平定價 |
| 23 | Eugenio Suárez | 3B | 100 | +4 | 0 | **+4** | 🟢 稍被低估 |
| 24 | Austin Riley | 3B | 65 | +3 | 0 | **+3** | 公平定價 |
| 25 | Cal Raleigh | C | 18 | +3 | 0 | **+3** | 🔴 ADP 18 只值 +3 VOR |
| 26 | Brent Rooker | OF | 52 | +4 | +2 | **+2** | 🔴 OF 深度壓低 VOR |
| 27 | Kyle Schwarber | OF | 24 | +3 | +2 | **+1** | 🔴🔴 ADP 24 但 VOR 僅 +1 |
| 28 | Elly De La Cruz | SS | 9 | +4 | +2 | **+2** | 🔴 ADP 9 但 VOR 僅 +2 |
| 29 | Steven Kwan | OF | 167 | +4 | +2 | **+2** | 🟢 ADP 167 免費拿 +2 |
| 30 | Trea Turner | SS | 26 | +2 | +2 | **0** | 🔴🔴 ADP 26 但 VOR = 0 |

### 關鍵洞察：守位稀缺放大效應

同樣格式淨分 +5 的球員，因守位不同 VOR 差異巨大：

| 球員 | 守位 | 格式淨分 | 替代水平 | VOR | 原因 |
|------|------|---------|---------|-----|------|
| Ozzie Albies | 2B | +5 | 0 | **+5** | 2B 替代品極差 |
| José Altuve | 2B | +5 | 0 | **+5** | 同上 |
| Manny Machado | 3B | +5 | 0 | **+5** | 3B 替代品也差 |
| Julio Rodríguez | OF | +5 | +2 | **+3** | OF 深度好，替代品不差 |

**Albies（ADP 158）和 Altuve（ADP 116）的 VOR 與 Machado（ADP 39）相同，但 ADP 晚了 80-120 順位。這是守位稀缺性創造的最大套利空間。**

---

### 投手 VOR 排名（Top 20）

| VOR 排名 | 球員 | 類型 | ADP | 格式淨分 | 替代淨分 | **VOR** | 套利標記 |
|---------|------|------|-----|---------|---------|---------|---------|
| 1 | Tarik Skubal | SP | 7 | +12 | 0 | **+12** | 公平定價（值得 R1） |
| 2 | Cade Smith | SU | 41 | +10 | +1 | **+9** | 🟢 SU 界的 Soto |
| 3 | Paul Skenes | SP | 10 | +8 | 0 | **+8** | 公平定價 |
| 4 | Garrett Crochet | SP | 12 | +8 | 0 | **+8** | 公平定價 |
| 5 | Mason Miller | CL | 30 | +8 | +1 | **+7** | 公平定價 |
| 6 | Garrett Whitlock | SU | — | +8 | +1 | **+7** | 🟢🟢 免費 |
| 7 | Logan Gilbert | SP | 34 | +7 | 0 | **+7** | 🟢 稍被低估 |
| 8 | Cristopher Sánchez | SP | 26 | +6 | 0 | **+6** | 公平定價 |
| 9 | Bryan Woo | SP | 37 | +6 | 0 | **+6** | 公平定價 |
| 10 | Logan Webb | SP | 61 | +6 | 0 | **+6** | 🟢🟢 超值 |
| 11 | Hunter Gaddis | SU | — | +6 | +1 | **+5** | 🟢🟢 免費 |
| 12 | Edwin Díaz | CL | 34 | +6 | +1 | **+5** | 公平定價 |
| 13 | Chris Sale | SP | 39 | +5 | 0 | **+5** | 公平定價 |
| 14 | Devin Williams | CL | 63 | +6 | +1 | **+5** | 🟢 稍被低估 |
| 15 | George Kirby | SP | 67 | +5 | 0 | **+5** | 🟢🟢 菁英控球超值 |
| 16 | Zack Wheeler | SP | 116 | +5 | 0 | **+5** | 🟢🟢 巨大套利 |
| 17 | Jacob deGrom | SP | 49 | +5 | 0 | **+5** | 🟢 傷病折扣 |
| 18 | Griffin Jax | SU | 162 | +5 | +1 | **+4** | 🟢🟢 超值 |
| 19 | Sonny Gray | SP | 134 | +4 | 0 | **+4** | 🟢🟢 超值 |
| 20 | Robert Garcia | SU | 242 | +5 | +1 | **+4** | 🟢🟢 免費 |

---

## Step 11：跨守位統一排名（打者 + 投手混合 Top 40）

將打者和投手的 VOR 放在同一張表排序。這就是「不考慮 ADP 的理想選秀順序」。

| 統一排名 | 球員 | 守位/類型 | ADP | VOR | 套利空間 |
|---------|------|---------|-----|-----|---------|
| 1 | Tarik Skubal | SP | 7 | +12 | 公平 |
| 2 | Juan Soto | OF | 4 | +9 | 公平 |
| 3 | José Ramírez | 3B | 6 | +9 | 公平 |
| 4 | Vlad Guerrero Jr. | 1B | 18 | +9 | 🟢 |
| 5 | Cade Smith | SU | 41 | +9 | 🟢 |
| 6 | Aaron Judge | OF | 2 | +8 | 公平 |
| 7 | Paul Skenes | SP | 10 | +8 | 公平 |
| 8 | Garrett Crochet | SP | 12 | +8 | 公平 |
| 9 | Mason Miller | CL | 30 | +7 | 公平 |
| 10 | Garrett Whitlock | SU | — | +7 | 🟢🟢 免費 |
| 11 | Logan Gilbert | SP | 34 | +7 | 🟢 |
| 12 | Bobby Witt Jr. | SS | 3 | +6 | 公平 |
| 13 | Gunnar Henderson | SS | 12 | +6 | 公平 |
| 14 | Ketel Marte | 2B | 33 | +6 | 🟢 |
| 15 | Freddie Freeman | 1B | 68 | +6 | 🟢🟢 |
| 16 | Ronald Acuña Jr. | OF | 6 | +6 | 公平 |
| 17 | Cristopher Sánchez | SP | 26 | +6 | 公平 |
| 18 | Bryan Woo | SP | 37 | +6 | 公平 |
| 19 | Logan Webb | SP | 61 | +6 | 🟢🟢 |
| 20 | Yordan Alvarez | OF | 35 | +5 | 🟢 |
| 21 | Kyle Tucker | OF | 14 | +5 | 公平 |
| 22 | Corbin Carroll | OF | 12 | +5 | 公平 |
| 23 | Fernando Tatis Jr. | OF | 15 | +5 | 公平 |
| 24 | Bryce Harper | 1B | 47 | +5 | 🟢 |
| 25 | Jazz Chisholm Jr. | 2B | 20 | +5 | 🟢 |
| 26 | José Altuve | 2B | 116 | +5 | 🟢🟢 |
| 27 | Ozzie Albies | 2B | 158 | +5 | 🟢🟢 |
| 28 | Manny Machado | 3B | 39 | +5 | 公平 |
| 29 | Chris Sale | SP | 39 | +5 | 公平 |
| 30 | Devin Williams | CL | 63 | +5 | 🟢 |
| 31 | George Kirby | SP | 67 | +5 | 🟢🟢 |
| 32 | Zack Wheeler | SP | 116 | +5 | 🟢🟢 |
| 33 | Hunter Gaddis | SU | — | +5 | 🟢🟢 |
| 34 | Edwin Díaz | CL | 34 | +5 | 公平 |
| 35 | Jacob deGrom | SP | 49 | +5 | 🟢 |
| 36 | Mookie Betts | SS | 58 | +4 | 🟢 |
| 37 | Riley Greene | OF | 79 | +4 | 🟢 |
| 38 | Nico Hoerner | 2B | 105 | +4 | 🟢 |
| 39 | Griffin Jax | SU | 162 | +4 | 🟢🟢 |
| 40 | Sonny Gray | SP | 134 | +4 | 🟢🟢 |

---

## 統一排名的策略解讀

### 1. Skubal 是全選秀 VOR 第一名

+12 VOR 遙遙領先。第二名是 Soto/Ramírez/Vlad 的 +9。如果你的順位在第 5-8 順，前面的人拿了 Judge/Witt/Soto/Ramírez，**Skubal 是最佳選擇**而非 Acuña 或 Henderson。

### 2. 三個守位的 VOR 溢價最明顯

| 守位 | 頂級球員 VOR | 替代品 VOR | 落差 | 策略含義 |
|------|------------|-----------|------|---------|
| **2B** | Marte +6, Chisholm +5 | McLain 0 | **5-6** | 必須在前 5 輪鎖定 |
| **3B** | Ramírez +9, Machado +5 | Paredes 0 | **5-9** | Ramírez 是 3B 界的 Skubal |
| **1B** | Vlad +9, Freeman +6 | Burleson +1 | **5-8** | Vlad 和 Freeman 是格式菁英 |

相比之下，SS 和 OF 的 VOR 落差較小（頂級 +6 vs 替代 +2 = 落差 4），可以稍微延後。

### 3. 投手的時機點比打者更明確

| ADP 區間 | 最佳投手目標 | VOR |
|---------|------------|-----|
| 7-12 | Skubal (+12) | 值得第一輪 |
| 26-45 | Sánchez, Gilbert, Woo, Sale, Cade Smith | +5 ~ +7 |
| 61-67 | Webb, Kirby | +5 ~ +6，超值 |
| 116-134 | Wheeler, Sonny Gray | +4 ~ +5，巨大套利 |
| 162+ | Jax, Garcia, Whitlock, Gaddis | +4 ~ +7，免費 |

**中段 SP（ADP 44-60 的 Hunter Greene +2、Cole Ragans +3）是價值陷阱——不如等到 Webb/Kirby 的 ADP 區間拿到更好的格式貢獻。**

### 4. De La Cruz 和 Turner 的 VOR 警告

| 球員 | ADP | VOR | 問題 |
|------|-----|-----|------|
| Elly De La Cruz | 9 | +2 | ADP 前 10 但 VOR 僅 +2，因 SS 替代水平高且 K% 25% |
| Trea Turner | 26 | 0 | ADP 第三輪但 VOR = 0，格式下完全不值這個價 |
| Kyle Schwarber | 24 | +1 | ADP 第二輪但 VOR 僅 +1，OF 深度壓低+K 拖累 |

這三位是「名氣 >> 格式價值」的典型案例。讓對手選他們。
