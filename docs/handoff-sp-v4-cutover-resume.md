# Handoff: SP v4 Cutover Resume (2026-05-06)

> **狀態**：⏳ P1-P5 已 ship，VPS dry-run + P2 門檻校準待做。前一個 session 因 worktree 切換中斷，這個 handoff 給新 session 接手。
>
> **branch**：`fix/sp-v4-cutover-completion`（追蹤 `origin/fix/sp-v4-cutover-completion`）
>
> **worktree**：`D:\mywork\mynote\mlb-fantasy-sp-v4`（sibling，主 repo `D:\mywork\mynote\mlb-fantasy` 是 master，給其他 session 用）

---

## 背景

執行 `docs/handoff-sp-v4-cutover-completion.md` 的 P1-P5（v4 cutover 7 項殘留中前 5 項）。前一個 session 完成 6 commits 推上 origin，但 SSH 環境問題沒跑 VPS dry-run。另一個 session 把主目錄 working tree 切回 master，所以開 worktree 隔離續做。

## 已完成（HEAD = `90041d4`）

| Commit | 範圍 | Tests |
|---|---|---|
| `fedece1` | refactor: extract `_savant_v4_fetch.py` 共享 helper | 225 ✓ + smoke (Skubal/Machado/Ashcraft) |
| `000c445` | **P1** daily_advisor.py 每日戰報 SP v4 5-slot 資料層 + format | 225 ✓ |
| `d86c415` | **P2** fa_scan.py SP_THRESHOLDS → v4 4-slot Sum gate | 225 ✓ + smoke (Sum 計算) |
| `457c41b` | **P3** fa_scan.py build_roster_summary SP v4 lens | 225 ✓ + smoke (Sum-asc 排序) |
| `6329d2f` | **P4** fa_scan.py FA prior_stats v4 寫入 | 225 ✓ + smoke (Skubal 2025) |
| `90041d4` | **P5** weekly_review.py SP v4 5-slot pctiles | 225 ✓ |

**所有 commits 跑過 `python -m pytest daily-advisor/tests/ -q` 225 全綠**。已 push 到 origin。

## 關鍵設計決策（已 ship，不該回頭改）

1. **`_savant_v4_fetch.py` 自帶 helper**（`_fetch_savant_csv` / `_safe_float` / `_ip_str_to_real` / `MLB_API_BASE`）— yahoo_query.py 內保留同名 helper 沒抽走，stateless 純函式重複成本 ≈ 0，避免 cross-module 依賴連鎖。
2. **Layer 2 SP gate 用 4-slot Sum（不含 IP/GS）**：IP/GS 要 per-pid game log call，量起來貴；Layer 3 enrichment 對通過 gate 的子集才補 IP/GS。Phase 6 看到的 5-slot Sum 是 enrichment 後的完整版。
3. **`SP_V4_SUM_THRESHOLD = 16`** 是 **placeholder**（4-slot 平均 P40），等 dry-run 比對舊 v2 池 vs 新 v4 池後校準。
4. **v4 + v2 `prior_stats` 並存**：RP path / fallback display / `_normalize_fa_for_compute` 都還讀 `xera` / `xwoba_allowed` / `hh_pct_allowed` / `barrel_pct_allowed`。**不要刪 v2 keys**。
5. **過去年 batted-ball `gb_pct` 標 `None`**：Savant batted-ball endpoint 忽略 `year` 參數，會回 current-year 數據誤導。`_extract_v4_sp_data` 的 `year` kwarg 用來 suppress。
6. **HH% / Barrel% allowed 從 SP display 完全移除**（CLAUDE.md L124 框架原則）— 但 RP display 保留。

## 待辦（按優先序）

### 1. VPS dry-run（必做，全 commit 一起驗）

前一個 session 卡在 SSH：本機 Windows OpenSSH 沒接 1password agent，`SSH_AUTH_SOCK` 三層 env var 都空，密碼 auth 在 non-interactive shell 讀不到 tty。**狀況描述見 git log + 對話**。

選一個跑：

**選項 A（agent 已修好）**：
```bash
ssh root@107.175.30.172 "cd /opt/mlb-fantasy && git fetch origin && git checkout fix/sp-v4-cutover-completion && git pull --ff-only && cd daily-advisor && python3 daily_advisor.py --no-send 2>&1 | tail -150"
```

**選項 B（使用者手跑）**：請使用者在自己的 PowerShell 跑上面那條，把 stdout 貼回對話。

驗收點：

- [ ] **每日戰報「我的先發投手」段** v4 5-slot 渲染正常（IP/GS / Whiff% / BB/9 / GB% / xwOBACON / luck Δ / BBE）
- [ ] **「我的打者」對手 SP** 一行 v4 5-slot 顯示
- [ ] 無 `KeyError` / `AttributeError`（重點注意 None prior_stats、v2/v4 dict shape 過渡）
- [ ] 沒 timeout（per-pid `fetch_pitcher_v4` × ~12 SP × 2 year ≈ 96 endpoint calls 預期 30-60s）
- [ ] 接著跑 fa_scan dry-run（看 P2 池組成）：
  ```bash
  ssh root@107.175.30.172 "cd /opt/mlb-fantasy/daily-advisor && python3 fa_scan.py --dry-run 2>&1 | tail -80"
  ```

### 2. P2 SP_V4_SUM_THRESHOLD 校準

placeholder 16 是 4-slot 平均 P40，**先觀察才能校準**。

跑兩次比對：
1. **新池**：`fix/sp-v4-cutover-completion` head（Sum ≥ 16）的 fa_scan dry-run SP 池 size + names
2. **舊池**：checkout `cbff26a`（master 的 v2 gate）跑同樣 dry-run

對比指標：
- SP 候選池 count Δ（< -50% → gate 太嚴；> +50% → 太鬆）
- 雙年強的 SP 沒被誤砍（Skubal 等級 must pass）
- 借此抓 borderline edge cases（Sum 14-18 的人都有誰）

校準完加 **fix-up commit**（不 amend `d86c415`，新 commit 標明 "tune SP_V4_SUM_THRESHOLD from 16 to N based on VPS dry-run"）。落點建議：
- 太嚴 → 14（4-slot 平均 P25-40）
- 太鬆 → 18-20（4-slot 平均 P40-P50）

### 3. P6 / P7（建議做，用戶這次只 ack P1-P5 但 P6 對 P1 有依賴）

| 項 | 範圍 | 依賴 |
|---|---|---|
| P6 | `prompt_template.txt` L15-16, L27-28 + `prompt_template_morning.txt` L19-20 SP matchup 文字（`HH% allowed > 40.8%` / `Barrel% allowed > 8.5%` 等 v2 門檻）→ 改 v4 描述 | **P1 已完成**，可直接做 |
| P7 | `roster_stats.py` L180-208 SP 顯示 v2 → v4 5-slot | 獨立 |

**P6 實作風險**：prompt 文字改 v4 但若 daily_advisor.py 跑時 v4 fetch 失敗（網路/CSV 不可用），LLM 看到的資料層為空但 prompt 仍 reference v4 指標，會出現 prompt-data 不對齊。dry-run 確認 P1 fetch 穩定後再動 P6。

**估時**：P6 0.5 hr / P7 0.5 hr。

### 4. PR / merge（最後）

dry-run 過 + 校準完成後：

```bash
# worktree 內
gh pr create --title "SP v4 cutover completion (P1-P5)" --base master \
  --body "$(cat <<'EOF'
## Summary
- 6 commits closing handoff-sp-v4-cutover-completion P1-P5
- Replaces last v2 SP residuals in daily_advisor / fa_scan / weekly_review
- New shared module _savant_v4_fetch.py for SP v4 league-bulk fetching

## Test plan
- [x] 225 unit tests green for every commit
- [x] yahoo_query savant smoke (Skubal/Machado/Ashcraft)
- [x] VPS dry-run daily_advisor + fa_scan (TODO: paste output)
- [x] P2 SP_V4_SUM_THRESHOLD calibrated to N (TODO: fix-up commit)
EOF
)"
```

或 master session 直接 merge：`git merge fix/sp-v4-cutover-completion`（不建議 fast-forward，因為 6 commits 是 logical group）。

merge 後清 worktree：
```bash
git worktree remove ../mlb-fantasy-sp-v4
```

## 環境

- **worktree path**：`D:\mywork\mynote\mlb-fantasy-sp-v4`
- **branch**：`fix/sp-v4-cutover-completion`（已 push 上 origin）
- **本機 tests**：`python -m pytest daily-advisor/tests/ -q` 必須 225 全綠
- **本機可跑 yahoo_query savant**（不需 Yahoo token，純 Savant CSV + MLB API）：
  ```bash
  python daily-advisor/yahoo_query.py savant Skubal
  ```
- **VPS**：`root@107.175.30.172` `/opt/mlb-fantasy`，需 SSH agent / 1password agent 接好

## 不要做的事

- ❌ 不要 `git commit --amend` 已 ship 的 6 commits（用戶 git protocol：`Always create NEW commits rather than amending`）
- ❌ VPS dry-run 沒過前不要 merge 到 master
- ❌ 不要刪 `prior_stats` 的 v2 keys（`xera` / `xwoba_allowed` / `hh_pct_allowed` / `barrel_pct_allowed`）— 並存是 by design
- ❌ 不要動 `_phase6_sp.py`（已是 v4 純粹）
- ❌ 不要動 RP 路徑（`_fmt_roster_pitcher_rp` / RP 部分的 fa_scan / weekly_review RP pctile）— RP 框架 v4 升級是另一個 TODO

## 相關文件

- `docs/handoff-sp-v4-cutover-completion.md` — 原 7 項 handoff
- `CLAUDE.md` — SP 評估 v4 框架定義 + 5-slot 百分位表
- `docs/sp-framework-v4-balanced.md` — v4 設計定稿
- `docs/v4-cutover-plan.md` — Stage A-F 歷史脈絡
