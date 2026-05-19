# Issue: player-eval-sp.md 的 4 處 SSH 改走 vps-run.sh wrapper

**狀態**：待處理（2026-05-20 建立）。
**父 issue**：`issues/vps-ssh-handshake-hang.md`（本機↔VPS 路徑間歇封包遺失，F2 = `bin/vps-run.sh` timeout+retry wrapper）。

## 問題

F2 把 `rp-svh` / `stream-sp` / `stream-sp-deep` / `weekly-review` 共 6 處 SSH 改走 `bin/vps-run.sh`，但 **`docs/player-eval-sp.md` 的 4 處裸 `ssh root@107.175.30.172`** 未納入。`/player-eval` 是高頻 skill，這 4 處會中同一個 SSH handshake 間歇卡死。

F2 未一起處理的原因：① 超出當時議定的 4-skill scope；② 其中 2 處是 `python3 << EOF` here-doc，多行內容塞進 wrapper 單一字串參數，經「git-bash 解析 → wrapper `"$1"` → ssh → 遠端 shell」多層，quoting / 換行存活率低（review M2 點名的風險）。

## 4 處 SSH 清單

| 行 | 形式 | 內容 | placeholder |
|----|------|------|-------------|
| ~58 | `ssh ... "cd ... && python3 -c '<多行>'"` | `fetch_savant_rolling` 取 21d xwOBACON | `{mlb_id}`、`{今天}` |
| ~83 | `ssh ... "python3 -c '<多行>'"` | MLB Stats API 取球隊 gamesPlayed（算 IP/Team_G） | `{team_id}` |
| ~127 | `ssh ... 'python3 << EOF ... EOF'` | Savant CSV 抓 3 年 pitch arsenal（usage / velocity） | `{mlb_id}` |
| ~168 | `ssh ... 'python3 << EOF ... EOF'` | MLB Stats API 取 vs L/R platoon splits | `{mlb_id}` |

## 建議做法

**不要**硬把 here-doc 塞進 wrapper 單參數。改成 VPS 端有真正的腳本 / 函式，skill 只呼叫 `bash bin/vps-run.sh 'python3 <script> <args>'`：

- 行 58（`fetch_savant_rolling`）：已 import 既有模組 `savant_rolling.py`，可加一個薄 CLI（`python3 savant_rolling.py --pitcher --mlb-id N --window 21`）或併入 `mlb_query.py`。
- 行 83（球隊 gamesPlayed）、行 168（vs L/R splits）：邏輯小，適合做成 `mlb_query.py` 的函式 + CLI 子命令（`mlb_query.py` 已是 `/stream-sp-deep` 的 helper 模組）。
- 行 127（3 年 pitch arsenal）：~30 行，獨立性高，做成 `daily-advisor/` 下一個小腳本或 `mlb_query.py` 函式。
- 全部改完後，4 處 skill 指令都是單行 `python3 ... 參數`，套 wrapper 無 quoting 風險。

落地後同步：① `docs/player-eval-sp.md` 4 處改 `bash bin/vps-run.sh '...'`（純讀 → 免 `--no-retry`）；② CLAUDE.md「執行環境」段移除「`docs/player-eval-sp.md` 4 處待轉」的但書；③ 父 issue「已知限制」段標記本項完成。

## 驗收

- `docs/player-eval-sp.md` 無裸 `ssh root@`，4 處全走 wrapper。
- 新腳本 / 函式有 TDD test（對齊 `mlb_query.py` / `rp_svh_scan.py` 慣例：pure function 單測、production fetcher e2e 驗）。
- VPS e2e：4 個指令各跑一次經 wrapper，輸出與改寫前一致。

## 參考

- 父 issue：`issues/vps-ssh-handshake-hang.md`
- wrapper：`bin/vps-run.sh`
- 相關模組：`daily-advisor/savant_rolling.py`、`daily-advisor/mlb_query.py`
