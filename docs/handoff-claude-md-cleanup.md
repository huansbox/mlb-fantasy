# CLAUDE.md Cleanup Handoff (2026-05-04)

## 背景

2026-05-04 session 執行了 CLAUDE.md 部分 cleanup：

| commit | 變更 |
|---|---|
| `a491d75` | 加 v4 framework lens rule（L168）+ 刪 SP v2 百分位表 + 加 TODO「Phase 6 prompt 拿掉 Sum」|
| `772accc` | 刪 `daily-advisor/prompt_fa_scan_pass2_sp.v2.txt` |
| `3523bf5` | 抽出串流 SP 到 `docs/streaming-sp-playbook.md`，CLAUDE.md -57 行 |

剩 2 個 task 推遲下次 session 處理。

---

## Task 1：v2 SP code 完整移除（Stage F.2 主體）

### Scope

v4 production 已跑 6 天健康（4/28 cutover），清除 v2 SP 殘留 code/tests。

### 目標檔案 + 函式

從 CLAUDE.md 原 Stage F.2 待辦條目擷取：

| 檔案 | 移除項 |
|---|---|
| `fa_compute.py` | `compute_urgency` SP 分支 / `compute_fa_tags` SP 分支 / `pick_weakest` SP 分支（`_sp_bbe_excluded`）/ `_compute_sp_*tags` 函式群 / `_factor_sp_*` 函式群 |
| `tests/test_fa_compute.py` | v2 SP unit tests |
| `prompt_fa_scan_pass2_sp.v2.txt` | ✅ 已刪（commit `772accc`）|
| `fa_scan.py` `SP_FRAMEWORK_VERSION` env flag | **待決**：保留作緊急 rollback 通道？或一併刪？ |

### 待決問題

- `SP_FRAMEWORK_VERSION=v2` rollback 通道保留 vs 移除：
  - 保留：v4 出問題可瞬切 v2，但需保留 v2 code → cleanup 不徹底
  - 移除：cleanup 徹底，但 rollback 只能走 git revert（v4 已穩定 6 天，概率極低）
  - 建議下次 session 評估：v4 production 已連跑幾天 + 是否有任何 anomaly

### Deliverable

- 1-2 commits 移除 v2 SP code
- All tests pass（v4 path 不變）
- VPS production 無影響

### 預估工時

~1-2 hour（cleanup + 跑 tests）

### 風險

- Rollback 通道若一併移除：v4 出問題只能 git revert
- v4 已穩定 6 天，rollback 概率極低

---

## Task 2：抽出其他「不常用 + 多行」段成 playbook

### 判斷標準（同串流 SP 模式）

候選段需同時滿足：
1. **每次 LLM session 不一定需要**（不像「執行中策略」每次都讀）
2. **行數 ≥ 30**（拉出去才有 context 節省效益）
3. **可獨立成 self-contained playbook**（拉出去後讀者能單獨理解）

### 候選清單（建議檢查）

| 候選段 | 行數估算 | 拉出評估 | 建議路徑 |
|---|---|---|---|
| 「系統架構」資料流圖（CLAUDE.md `## 賽季運營 SOP > 系統架構`）| ~35 | **高機率拉**（reference 型，每日不用）| `docs/architecture.md` |
| 「檔案索引」表 | ~30 | 中（建議查時用，非每日讀）| `docs/file-index.md` 或保留 |
| 「執行環境」VPS 連線指令 | ~15 | 低（行數不夠 + 開發時常用）| 留 |
| 待辦段「v4 cutover + Phase 6 同波」歷史 sub-bullets（已 ✅ 完成的 Stage A-D）| ~20 | **高**（已完成 archive）| `docs/v4-cutover-completed.md` 或刪（git log 已留）|
| Phase 6 §7.1-7.7 內部設計鎖定（在待辦條目中）| ~10 | 中（已鎖定不會變）| 跟上面同案 |

### 拉出流程（同串流 SP）

1. 識別候選段 + 行數
2. 新建 `docs/<topic>.md` 包含完整內容
3. CLAUDE.md 留 stub link（1-2 行）
4. 加到「檔案索引」表
5. 一個候選一個 commit

### 不該拉的（保留 in CLAUDE.md）

- 球員評估框架（v4 thin batter / v4 SP — 每次評估都用）
- 2025 MLB 百分位分布表（每次評估都用）
- 執行中策略 strategy bullets（每次決策都用）
- waiver-log / week-reviews / roster_config 系統介紹（每次都用）
- Week 中 H2H 決策框架（5/4 加，常用）
- 球員追蹤 references（指向 waiver-log）

### 預估工時

~30 min - 1 hour per 候選段（識別 + 抽出 + 寫 stub + commit）

---

## 順帶可考慮（不在本 handoff 範圍）

1. **RP 框架是否升級 v4**：目前 RP 評估仍用 xERA / xwOBA / HH% allowed（v2 風格指標），因為 fa_scan_v4 / Phase 6 只做 SP。SP v4 cutover 完成後 RP 是否同樣升級？這是「框架對稱性」議題，下次可考慮。
2. **待辦段歷史條目 archive**：已完成的 commit 條目（如「~~Stage A 資料層~~ ✅」）git log 已留，CLAUDE.md 待辦段可考慮全部刪 ✅ 條目（已存在 git log 的 commit hash）。

---

## 本 session 已完成決策（給下次 session 的 anchor）

| 決策 | Commit / 位置 |
|---|---|
| v4 framework lens 規則進 CLAUDE.md（L168 通用規則段）| `a491d75` |
| HH% / xERA / xwOBA 是 v2 已退役指標，不可作 SP drop 判斷 | CLAUDE.md L168 |
| v2 SP percentile table 刪除（RP 表共用同樣分布）| `a491d75` |
| 串流 SP 抽出 playbook 模式驗證（CLAUDE.md -57 行）| `3523bf5` |
| 同一天 fa-scan SP-v4 GitHub Issue 是 anchor（不該逆向 freestyle）| CLAUDE.md L168 |
