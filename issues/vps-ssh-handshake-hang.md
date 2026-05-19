# Issue: VPS SSH 連線間歇性卡死（handshake 階段）

**狀態**：待處理（2026-05-19 建立）。根本原因部分確認、深層成因待查。
**影響範圍**：所有 SSH 到 VPS 的 skill / 操作（`/rp-svh`、`/stream-sp`、`/weekly-review`、手動 `yahoo_query.py` 查詢等）。

## 問題

從本機 SSH 到 VPS（`root@107.175.30.172`）時，連線會**間歇性卡死在 SSH handshake 階段**：
前 1-2 次連線常卡 ~30s+ 無回應，重試後就連得上、且連上後路徑「熱」起來、後續連線都很快。

## 證據（2026-05-19 session 觀測）

連線測試 — `timeout 30 ssh -o ConnectTimeout=20 -o BatchMode=yes root@107.175.30.172 "echo ok"` 連跑 5 次：

```
attempt 1  → exit 124（卡滿 30s 被 timeout 砍）
attempt 2  → exit 124（卡滿 30s）
attempt 3  → ok（~2s）
attempt 4  → ok（~3s）
attempt 5  → ok（~2s）
```

同 session 共 6 次 SSH 操作：4 次短指令（git status / git log / git config / pgrep）成功、2 次（含一次長指令 e2e）卡死。

一次失敗的 e2e 指令含 `python3 rp_svh_scan.py --pretty > /tmp/rpsvh.json 2>/tmp/rpsvh.err`，
事後檢查 VPS：`/tmp/rpsvh.json` / `/tmp/rpsvh.err` **完全不存在**。shell 的 `>` 重導向在指令一執行就建立檔案 → 檔案不存在 = 遠端 shell 從未執行 = 卡在連線建立、不是腳本卡住。

## 已排除

- **不是腳本 bug**：`rp_svh_scan.py` 本機 422 tests pass；連上的那次 e2e 完整成功。
- **不是 SSH ControlMaster 多工**：本機無 `~/.ssh/config`，沒設 ControlMaster / ControlPath。
- **不是 TCP 連不上**：卡死的 attempt 跑滿 `timeout 30` 而非在 `ConnectTimeout=20` 觸發 → TCP 有通，卡的是 TCP 連上後的 SSH 協議交握 / 認證階段。
- **不是 git 認證問題**（另一條獨立線）：第一次 `git pull` 卡死是因互動 SSH 非 login shell → `$GH_TOKEN` 沒帶到 → git credential helper（`!f() { echo username=x-access-token; echo password=$GH_TOKEN; }`）回空密碼 → git 阻塞等輸入。這與 handshake 卡死是兩回事，且已被「`GIT_TERMINAL_PROMPT=0` + 帶 token 的環境」繞過。

## 尚未確認（深層成因）

SSH handshake 為何間歇性卡 ~30s 後才通。候選假設：

1. **VPS sshd `UseDNS` reverse-DNS timeout**：sshd 對連入 IP 做反解，DNS 查詢超時 → 第一次連線等 DNS timeout（典型 ~30s），之後熱。最符合「前 1-2 次卡、之後快」的形狀。
2. 網路路徑 conntrack / 防火牆 state 暖機。
3. 本機端網路 flaky。

## 建議調查路徑（只讀 / 低風險優先）

1. `ssh -vvv root@107.175.30.172 echo ok`（卡死那次的 verbose log）— 看交握停在哪一行（`expecting SSH2_MSG_KEX...` / `Authenticating...` 等），直接定位階段。
2. VPS 端 `sshd_config` 查 `UseDNS`（預設多為 `no`，但若 `yes` 高度可疑）+ `/etc/resolv.conf` 的 DNS server 是否可達。
3. 若確認 reverse-DNS：VPS `sshd_config` 設 `UseDNS no` → `systemctl reload sshd`（單行設定變更，需謹慎、先確認）。
4. 旁證：VPS cron 排程的 git/腳本同步是否也偶發慢 — 查 cron log 時間戳。

## 待決定（修好根因前的權宜）

VPS skill 的 SSH 指令是否要統一加保險，二選一（**應全體一致，不單獨補某個 skill**）：

- **A**：SSH 指令包 `timeout N ssh ...` → 卡死 N 秒後失敗收場、不無限掛住，agent 看到非 0 exit 重試。
- **B**：skill md 加 operational note：「SSH handshake 間歇性卡死，無輸出即重試」。

> 若根因（假設 1）修好，A/B 都不需要。建議先走「調查路徑」釘死根因，再決定要不要權宜。

## 參考

- VPS 連線資訊：`~/.claude/projects/.../memory/reference_vps.md`
- 受影響 skill：`.claude/commands/rp-svh.md`、`stream-sp.md`、`weekly-review.md` 等的 Step「SSH 跑機械層」
