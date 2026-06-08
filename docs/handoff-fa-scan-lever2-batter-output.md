# Handoff — fa_scan prompt 簡化「槓桿 2」：batter output 收斂

> 2026-06-08 建。接手者目標：降低 fa_scan **batter** claude call 的 **output token**，不傷決策品質。
> 過渡文件，做完即刪（`glob docs/handoff-*`）。完整脈絡：`issues/prd-claude-p-cost-simplification.md` Phase 1.5。

## 一句話

fa_scan 每天 batter call 的 LLM **輸出** 9–11K tokens（opus output $25/1M = **$0.23–0.27/call，是這個 call 最大的單一成本項**）。槓桿 2 = 改 `prompt_fa_scan_pass2_batter.txt` 的輸出格式段，收斂冗長度，省 output token。SP 走 JSON 輸出、不受影響，本槓桿只動 batter。

## 前因（精簡）

- 背景：6/15 起 `claude -p` 改吃獨立 $100/月 credit pool（見記憶 `project_claude_p_credit_pool`），要壓 headless 成本。
- Phase 1.5 量測（VPS，真實 payload）已完成。**槓桿 1a（CLAUDE.md cwd cut）已實作 + 部署**（master `9c5c517`，每 call 省 22.5K input）。
- 量測順帶發現：batter call cost $0.49–0.67，其中 **output 9–11K tokens 是最大塊**，比 CLAUDE.md 那 22.5K input 還貴 → 收斂 output 的省幅 ≥ 槓桿 1a，且字面上就是「prompt 簡化」。
- 成本結構通則見記憶 `feedback_claude_p_cwd_cut`（output 是 opus input 的 5× 價）。

## 起點 / 現況

- branch `refactor/fa-scan-prompt-slim`（已 merge master，保留待本槓桿續用；可在它上面續 commit，或從 master 新開 `refactor/fa-scan-batter-output`）。
- 槓桿 1a 部署後**首班 cron（2026-06-09 TW 12:30）被動觀察**：確認 batter/SP issue 正常產出 + 無 `fa-scan-error`。**本槓桿動工前先確認 1a 首班沒翻車**。
- 改的檔：`daily-advisor/prompt_fa_scan_pass2_batter.txt`（純 prompt，無 code 邏輯改動最理想）。

## 目標數字 + OPEN（砍哪些）

本 session 觀察到的真實 batter output（issue #300 payload 的兩次跑）：**91–102 行**，疑似大頭：
- **drop 排序列了 P1–P7（7 人）**，每人 3 行（Season 重點 / 14d / 判斷）= ~21 行敘述。
- **waiver-log 區塊 UPDATE 行 11–19 條**（每個觀察中球員 emit 一條摘要）。

→ **第一步：先量 output 各段 token/行數分布**（drop 排序 vs ACTION vs PASS vs waiver-log UPDATE），鎖定最肥段再砍，別憑感覺。

候選砍法（OPEN，需對齊）：
1. **drop 排序只詳列前 N**（如前 3–4 人三行式，其餘一行簡列名+一句）。7 人全詳列是疑似最大浪費。
2. **drop 三行 → 兩行**：Season + 14d 合併一行 raw，「判斷」保留一行（判斷是 LLM 核心價值，別砍）。
3. **PASS 段預設空**：prompt 已說「例行 pass 不輸出」，但實測仍長 → 強化指令。
4. **waiver-log UPDATE 摘要精簡**：每條限字數 / 只 emit 有實質變化的。注意這是 trade-off — UPDATE 餵進 `waiver-log.md` 的觀察記錄，砍太多會失去脈絡。

我（前一 session）的初判：**1 + 2 省最多且最安全**（drop 排序是純展示、砍了不影響任何下游）；4 要謹慎（影響 waiver-log 資訊量）。

## Hard contract — 收斂時這些字面錨點不可動

輸出被 `fa_scan._process_group`（fa_scan.py:2906-2928）三路消費，靠以下字面 marker：

| 錨點 | 用途 | 來源 |
|------|------|------|
| `--- ACTION ---` / `--- END_ACTION ---` | Telegram/Issue strip | prompt 41/52 |
| `--- PASS ---` … `--- END_PASS ---` | Telegram strip（regex 配對，DOTALL）| prompt 54/65 |
| ` ```waiver-log ` … ` ``` ` fence | strip + 解析 | prompt 67-72 |
| `NEW\|名\|隊\|\|觸發\|摘要` / `UPDATE\|名\|摘要` | `_update_waiver_log` 機器解析（位置欄留空，程式補）| prompt 69-85 |

砍的是「敘述冗長度」，**不是結構**。改完務必確認這些 marker + NEW/UPDATE 管線符號格式原封不動，否則 Telegram strip / waiver-log 自動更新會壞。

## 驗證方法（不能本機跑 fa_scan）

`fa_scan.py` 會 refresh Yahoo OAuth token，**本機跑被 hook 擋、連 VPS worktree 真跑都會 rotate token 打斷 cron** → 不可真跑整支。改用：

1. 取真實 batter payload：近期 issue raw dump 的 `=== Layer 4 Mechanical Report (打者) ===` 到 `=== Layer 5 Claude Output ===` 之間就是注入的 `{data}`（本 session 用 issue #300，流程：`gh issue view N -R huansbox/mlb-fantasy --json body`）。
2. 組完整 prompt = `prompt_fa_scan_pass2_batter.txt` 去最後一行（`{data}`）+ 接 data。
3. VPS worktree（`git worktree add`）跑對照：舊 prompt vs 新 prompt，各 `claude -p "$(cat payload)" --output-format json`，比 `usage.output_tokens` + 確認結構錨點完整 + 決策不變。**注意 opus 跑 68KB payload 每次 60–150s**，vps-run 預設 timeout 90s 不夠 → `VPS_RUN_TIMEOUT=300 ... --no-retry`，且 claude 在 local ssh 斷線後 remote 仍會跑完（去 VPS 撈 output 檔，別重跑多燒 credit）。
4. 部署後首班 issue 仍含必要區塊（drop 排序 / ACTION / waiver-log fence）。

⚠️ production claude call **非 json mode、不記 usage** → 部署後無法從 cron 量 output 省幅；要數字只能 worktree + 真實 payload 手動對照新舊 prompt。

## Gotchas

- **hook `block-local-yahoo`**：bash 指令含裸 `fa_scan.py` token 被擋 → 路徑加引號 / 用 `git log` 確認，別在指令裡裸寫腳本名。
- **hook `block-bare-python`**：本機無 pyproject，跑 test 用 `uv run --with pytest python -m pytest tests/<f>.py`；VPS remote `python3` 經 vps-run 放行。
- **VPS 部署**：merge master → `bash bin/vps-run.sh --no-retry 'cd /opt/mlb-fantasy/daily-advisor && python3 git_sync.py /opt/mlb-fantasy'`（非手動 git pull，避 roster cron 每 15 分 git push 的 race）。
- **commit message** 別出現裸 `fa_scan.py`（hook 會擋整個 commit 指令）。
- 改純 prompt 不需動 code、不需碰 `_process_group` 的 strip 邏輯（除非你改了 marker，那就要同步改 regex — 不建議）。

## 第一步建議

1. 確認 1a 首班（6/9 12:30）正常。
2. 取一筆真實 batter payload，量 output 各段 token 分布，貼數字。
3. 用數字對齊 OPEN（砍哪些）→ 改 prompt → worktree A/B（output token ↓ + 結構錨點完整 + 決策不變）→ commit → 部署 → 首班觀察。
