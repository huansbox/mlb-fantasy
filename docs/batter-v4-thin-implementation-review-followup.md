# Batter v4 Thin Review — Follow-up（C1/D1 fix 驗證 + 新 Finding R1）

> **Status**: 2026-04-28 follow-up
> **驗證對象**: commits `d5c0bd5` (C1 fix) + `dd64fb9` (D1 doc fix)
> **指示**: 「double check，有問題一樣不直接改」— 此 doc 為新 finding log, 不含 fix
> **前一份 review**: `docs/batter-v4-thin-implementation-review.md`

---

## C1 Fix（commit d5c0bd5）驗證

### ✅ Implementation 部分 OK

| 修改點 | 檢核 |
|---|---|
| `_fmt_anchor_block_batter_v4` 移除 `positions` 變數 + header 字串 | ✓ 確認 line 2617 改為 `({team})` |
| `_fmt_fa_block_batter_v4` 移除 `pos` 變數 + header 字串 | ✓ 確認 line 2705 改為 `({team})` |
| 兩函式加 docstring/comment 引用 design §1.2 + §3.4 | ✓ |
| 241 pytest 全綠 | ✓ 本機驗證 241 passed |

### 🟠 但 — C1 fix 不完整：prompt template 仍引用 positions（**新 Finding R1**）

詳見下面 §R1。

---

## D1 Fix（commit dd64fb9）驗證

### ✅ 完整 OK

| 修改點 | 檢核 |
|---|---|
| §3.4「明確不出現的欄位」拆分 — `tags` 變 `data-based tags（14d / xwOBA / luck / sample-size 相關）` | ✓ |
| 新增「保留的欄位」subsection — 列 ✅ 球隊主力 / ⚠️ 上場有限 為 PA-based gate tags | ✓ |
| 加 rationale（「純 PA 計算非 data 判斷」）+ 交叉引用 §7.1 | ✓ |

D1 修正乾淨且文件邏輯一致。**Closed**.

---

## 🟠 新 Finding R1 — prompt template 跟 LLM input 不一致

### 問題本質

C1 fix 只改了 **fa_scan.py 的 LLM input 字串**（`_fmt_*_block_batter_v4` headers），**沒改 prompt template `prompt_fa_scan_pass2_batter.txt`**。導致：
- LLM 看不到 positions（input 已清掉）
- 但 prompt template 要求 LLM 輸出 positions（output 仍含 `{守位}` / `{位置}`）

LLM 的兩個可能行為：
1. **留空**：`**P1 Albies**（ATL, ）` — 報告格式破損
2. **幻想 / 從訓練資料推**：`**P1 Albies**（ATL, 2B）` — LLM 用先驗知識補，等於繞過 design 原則
3. **整個欄位省略**：`**P1 Albies**（ATL）` — 自行修正 template

無論哪種，**design 原則「LLM 不該看 / 不該用 positions」沒完整落實**。

### 具體位置

**檔案**: `daily-advisor/prompt_fa_scan_pass2_batter.txt`

**Line 24**（anchor 輸出 template）：
```
- **P1 {球員名}**（{隊伍}, {守位}）
```

**Line 40**（FA 輸出 template）：
```
{序號}. **{球員名}**（{隊伍}, {位置}）{%owned}% [{shape}] — {立即取代 / 取代 / 觀察}
```

**Line 53**（pass 判斷 hint）：
```
- 高 %owned FA (≥20%) 但我方過濾（策略不符 / 守位重疊等）
```
這條更嚴重 — 直接要 LLM 用「守位重疊」做 pass 判斷，跟 line 16「守位 / IL/BN/DTD 不影響評價」**自相矛盾**。

**Line 64**（waiver-log 格式）：
```
NEW|球員名|隊伍|位置|觸發條件|本日觀察摘要
```
waiver-log 自動寫入需要 position 欄位。LLM 沒看到 position 就無法填，會留空或幻想。

### Design 衝突點

| 內容 | Line | 跟 design 對應 |
|---|---|---|
| 「守位 / IL/BN/DTD 不影響評價」 | 16 | ✓ 跟 §1.2 一致 |
| `**P1 {球員名}**（{隊伍}, {守位}）` | 24 | ✗ 要 LLM 輸出守位但 LLM 沒此 input |
| `**{球員名}**（{隊伍}, {位置}）` | 40 | ✗ 同上 |
| 「守位重疊」做 pass 判斷 | 53 | ✗ 跟 line 16 + §1.2 自相矛盾 |
| `NEW\|...\|位置\|...` waiver-log 格式 | 64 | ✗ 自動寫入需 position 但 LLM 沒此資料 |

### 修法選項

**Option A（strict design 對齊，推薦）**：

1. Line 24 改為 `**P1 {球員名}**（{隊伍}）`
2. Line 40 改為 `{序號}. **{球員名}**（{隊伍}）{%owned}%...`
3. Line 53 改為「策略不符等」（移除「守位重疊」）
4. Line 64 waiver-log 格式：兩種子選項
   - **A.1**: `NEW|球員名|隊伍||觸發條件|...`（位置欄留空，downstream postprocessor 從 roster_config 補）
   - **A.2**: `NEW|球員名|隊伍|觸發條件|...`（去掉位置欄；改 `_update_waiver_log_locked` parse 規則）

A.1 對 waiver-log 既有資料破壞最小（保留欄位順序），推薦走 A.1。

**Option B（pragmatic — 重新允許 LLM 看 position）**：

把 C1 fix 部分回退，**input 重新顯示 position**，但 prompt 強調「position 只用於輸出 / waiver-log 識別，不可用於評估推論」。

優：操作簡單，waiver-log 自然能填位置。
劣：違反 strict design 原則 + 用 prompt instruction 約束 LLM 不可靠（容易 leak 進 reasoning）。

### 推薦 Option A.1

理由：
1. C1 commit 已是 strict design 路線，A.1 是邏輯延伸
2. waiver-log 自動寫入由程式 postprocess 補位置（從 `roster_config.json` lookup），比 LLM 填可靠
3. 後續 multi-agent 上線時 architecture 一致（agent 不看 position 全程）

### 預估改動

**檔案**：
- `daily-advisor/prompt_fa_scan_pass2_batter.txt` — line 24, 40, 53, 64 修改（4 處）
- `daily-advisor/fa_scan.py` — `_update_waiver_log_locked` 或對應 parser 函式：當 LLM 留空 `位置` 欄位時，從 roster_config.json + Yahoo FA list 反查補上

**工作量**：1-2 小時

**測試**：
- 跑 pytest 不應變化（prompt 改動不影響 unit test）
- VPS smoke test：跑一次 batter scan，看 waiver-log 寫入的 `位置` 欄是否正確自動填補

---

## 結構性 Compliance Audit 更新版

跟前一份 review 比，C1/D1 已 closed，新增 R1：

| Design § | 規定 | Implementation | 狀態 |
|---|---|---|---|
| §1.2 拋棄 守位顯示給 LLM input | input 不含 position | C1 fix d5c0bd5 移除 input | ✓ Closed |
| §1.2 拋棄 守位 進 evaluation | LLM 不該用 position 推論 | prompt line 16 instruction OK，但 line 53「守位重疊」要 LLM 用 | **✗ R1** |
| §3.4 clarify tags | data-based 排除 / PA-based 保留 | D1 fix dd64fb9 文件補正 | ✓ Closed |
| Output template 跟 input 一致 | LLM output 應只用 input 提供的資料 | template 要求 `{守位}` / `{位置}` 但 input 已無 | **✗ R1** |
| waiver-log 自動寫入 | 需要 position 欄 | LLM 沒 position 資料無法填 | **✗ R1** |

---

## Action Items

### 🟠 R1 — prompt template 跟 input 一致化（推薦走 A.1）

1. `prompt_fa_scan_pass2_batter.txt`：
   - Line 24: `（{隊伍}, {守位}）` → `（{隊伍}）`
   - Line 40: `（{隊伍}, {位置}）` → `（{隊伍}）`
   - Line 53: 「策略不符 / 守位重疊等」→「策略不符等」
   - Line 64: `NEW|球員名|隊伍|位置|...` → 維持格式但允許位置欄空白
2. `fa_scan.py`：
   - `_update_waiver_log_locked` 或對應 parser：位置欄空白時從 `roster_config` / Yahoo FA list 自動補
3. Commit message：`fix(prompt+fa_scan): align batter v4 thin output with no-position design (R1 follow-up)`

預估 1-2 小時。

### 🟢 不需 action — 之前 review 的 F1 / F2 / M1-M3

- F1（multi-agent enrich rolling_block 缺 14d trad）：仍 deferred，多 agent 層上線前處理
- F2（sum_diff sort）：仍 deferred，多 agent 上線時拿掉
- M1-M3：不動

---

## Sign-off

- C1 fix（input 移除 positions）：✅ 完整
- D1 fix（design doc 補正）：✅ 完整
- 新發現 R1（prompt template / waiver-log 仍引用 positions）：**🟠 待修**

整體實作品質仍高（C1/D1 修法乾淨），R1 是 C1 fix 路徑上的延伸 — 把 strict design 路線在 prompt 層也走完。

Reviewer 結論：**建議下一個 commit 處理 R1**，再來才是 multi-agent 層相關工作（F1/F2）。
