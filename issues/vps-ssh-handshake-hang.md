# Issue: VPS SSH 連線間歇性卡死（handshake 階段）

**狀態**：根因已確認（2026-05-19，雙端同步抓包定案）。**網路路徑間歇性雙向封包遺失**——非 sshd / ssh 設定層可修，需 MTR 定位後向 ISP（HiNet）或 VPS 供應商（RackNerd）申告;本機端只能用 timeout + retry 緩解。
**影響範圍**：所有 SSH 到 VPS 的 skill / 操作（`/rp-svh`、`/stream-sp`、`/weekly-review`、手動 `yahoo_query.py` 查詢等）。

## 問題

從本機（Windows）SSH 到 VPS（`root@107.175.30.172`）時，連線會**間歇性卡死在 SSH handshake 階段**：
前 1-2 次連線常卡 ~30s+ 無回應，重試後就連得上、且連上後路徑「熱」起來、後續連線都很快。

## 已確認的事實（2026-05-19 session）

### 重現

`timeout 35 ssh -o ConnectTimeout=25 -o BatchMode=yes root@107.175.30.172 "echo ok"` 連跑：

- 第一批 5 次：4s / **27s** / 2s / **卡滿 35s timeout** / 4s
- 第二批含 `-vvv`：2s / **卡滿 35s** / **14s（半卡，見下）** / 3s / **卡滿 35s** / 3s

單一 session 序列連線即可重現（但見「尚未確認 — 併發」一節，背景並不乾淨）。

### `ssh -vvv` 定位

卡點在 **KEX 完成後的 userauth 階段**。三個慢樣本：

- attempt 2（卡滿 35s）：最後一行 `debug3: send packet: type 50`（已簽名 pubkey auth 請求），卡在等 server 回 `type 52/51`。
- attempt 5（卡滿 35s）：最後一行 `debug3: send packet: type 5`（SERVICE_REQUEST），卡在等 server 回 `type 6`。
- attempt 3（14s「半卡」）：完整成功，但 `Transferred ... in 6.6 seconds`——`echo ok` 不該花 6.6s，是第三個慢樣本，卡點在 channel/exec 階段。

**一致形狀**：三個慢樣本最後一行都是 `send packet`——**每次都「client 送出封包後、卡在等 server 回應」**，沒有一次卡在「client 還沒送出」。

### VPS 端設定（注意：以下皆為「能連上之後」才取得，見 survivorship bias 警告）

- `sshd -T`：`usedns no`、`gssapiauthentication no`、`maxstartups 10:30:100`、`logingracetime 120`、`maxsessions 10`、`persourcemaxstartups none`。
- load average：`0.01, 0.03, 0.01`。
- auth.log：持續有暴力破解 bot 打 root（如 `191.241.76.128`，preauth disconnect）。
- `/etc/resolv.conf`：`8.8.8.8` / `8.8.4.4`。`systemd-resolved` active、`nscd` inactive。

### 本機 → VPS ICMP

`Test-Connection` 60 封包 0% loss。**注意**：此數據不可作為「網路路徑健康」的證據（見下「已撤回的推論」H4）。

## 已排除

- **不是 sshd reverse-DNS（issue 原始主假設，已證偽）**：`sshd -T` → `usedns no`。
- **不是 GSSAPI**：`gssapiauthentication no`。
- **不是腳本 bug**：`rp_svh_scan.py` 本機 422 tests pass；連上的那次 e2e 完整成功。
- **不是 SSH ControlMaster 多工**：本機無 `~/.ssh/config`，沒設 ControlMaster / ControlPath。
- **不是 TCP 連不上**：卡死的 attempt 跑滿 `timeout` 而非在 `ConnectTimeout` 觸發 → TCP 有通，卡的是 TCP 連上後的 SSH 協議交握 / 認證階段。

## 已撤回的推論（2026-05-19 3-agent 審查推翻）

初版診斷曾宣告「根因是路徑封包遺失、靠 TCP 重傳救回」。經審查，支撐它的推論全部站不住，**該結論撤回**：

- **「卡不同階段 → 排除 server 慢動作」** — 邏輯錯誤。三個慢樣本本質相同（都是「送出後等 server 回應」），不是不同階段；且 MaxStartups 隨機丟棄、PAM/NSS 阻塞本就會卡在浮動位置。
- **「~30s = TCP 重傳指數退避」** — 湊數。`ssh -vvv` log 無時間戳，`1+2+4+8+16` 純推測；實際 RTO 初值 ~200-300ms 非 1s;單封包遺失靠重傳救回不會卡滿 35s。30s 更像某個固定 timeout。
- **「ICMP 0% loss」** — 誤用（H4）。60 封包 1 分鐘取樣抓不到 burst loss;ICMP 小封包全通正是 **MTU 黑洞**典型表現（KEX 大封包 type 31/50 被靜默丟）。且「引用 0% loss」與「下封包遺失結論」自相矛盾。
- **「MaxStartups drop 發生在 fork 前、不會走到 KEX」** — 錯誤且未查證。sshd 是 accept→fork→子程序跑 KEX，MaxStartups 在 pre-auth 階段做機率性斷線，連線可能已在 KEX 中。
- **「併發與根因無關」** — 過度推論。序列測試期間 VPS 上一直有 bot 併發，背景從不乾淨（見下）。
- **survivorship bias**：所有 VPS 端數據都是「能連上之後」才取得，卡死當下 server 狀態完全無數據。

## 決定性測試結果（2026-05-19 — 根因確認）

雙端同步觀測：VPS 掛 `tcpdump`（`tcp port 22 and host 61.220.64.106`）+ 每秒 `/proc/PID/{wchan,syscall,stack}` 被動快照（不需 strace）；本機 175s 內狂連 10 次。重現 3 次完整卡死（41/40/40s）+ 2 次半卡（14/17s），全在觀測窗內。

### server 端：sshd 全程閒在 poll()，無任何慢動作

卡死連線的 sshd（pid 1670672/1670673）30+ 秒每個快照都是 `stat=Ss/S`（**非** `D` 不可中斷睡眠）、`wchan=do_poll`、`syscall=poll/ppoll`，全程等 fd 可讀，從未進到 `read`，沒有 PAM / DNS / `futex` / `D` state。→ **server 不是在做慢動作，是閒著等一個永遠不到的封包。** 徹底排除 server stall。

### MaxStartups / bot flood：被數據證偽

`conns.log` 全程 `established ≤2`、`syn-recv ≤1`——unauth 連線數從未接近 MaxStartups 門檻 10。

### pcap：路徑雙向封包遺失 = 根因

決定性證據——port 3684 卡死連線：

```
13:52:34.124538  VPS→client  送 52-byte SSH 封包
13:52:34.748814  VPS→client  重傳 (RTO ~0.6s)
13:52:37.244820  VPS→client  重傳 (~2.5s)
13:52:42.556822  VPS→client  重傳 (~5.3s)
13:52:52.796951  VPS→client  重傳 (~10s)
13:53:07.313816  client→VPS  FIN（本機 timeout 40 砍掉 ssh）
```

**VPS 送出一個 52-byte 封包、指數退避重傳 5 次橫跨 33 秒，client 一個 ACK 都沒回**——每份都在路徑上遺失。client 在等這個封包（= `-vvv` 看到的「送出後卡住等 server 回應」），VPS 在 `poll()` 等 client 的 ACK，兩邊互鎖到 timeout。旁證——port 3648 連線：SYN 重傳 2 次、SYN-ACK 重傳 3 次、SSH banner 送 3 次、資料段雙向都重傳。

### 連帶結論

- **不是 MTU / MSS 黑洞**：遺失與封包大小無關（60-byte SYN、21-byte banner 等小封包照丟）。
- **不是 client MSYS `select()` bug**：pcap 在 VPS 網卡上就看到實體封包遺失與雙向重傳。
- **ICMP 0% loss（先前 60 封包）不具代表性**——遺失是間歇 burst。
- **「前 1-2 次卡、之後快」**：loss 是 burst 性，連線只要熬過 lossy 窗口就完成，隔幾秒的新連線常落在乾淨窗口。非真「熱起來」。
- 初版「~30s = TCP 指數退避」方向對、但當時零證據且搞錯方向（是 server→client 退避重傳）。pcap 實測退避序列 0.6→2.5→5.3→10s 坐實。

## 剩餘調查（定位 loss 在路徑哪一段）

根因已定，尚需定位以決定向誰申告：

- 本機跑 `mtr --tcp -P 22 -c 1000 107.175.30.172`（或 `winmtr`），看逐 hop 遺失率。
- loss 集中在前 1-2 hop → 本機 ISP（HiNet，`61.220.64.106`）；集中在接近 VPS → 供應商（RackNerd，`107.175.30.172`）上游。
- 帶 pcap + mtr 證據開 ticket。

## 修正計畫

> 根因在網路路徑，**不是 sshd / ssh 設定層能修的**。本機端只能緩解。

- **F0（治本，非本機可控）**：MTR 定位 loss 段 → 向 HiNet 或 RackNerd 申告。能否真的修好取決於對方。
- **F2（緩解，主要措施）**：建版控 wrapper `bin/vps-run.sh`（`timeout 45 ssh ...` + retry 2-3 次 + retry 記 log）。4 個 skill md（`rp-svh` / `stream-sp` / `stream-sp-deep` / `weekly-review`，共 5 處 ssh）改成呼叫 wrapper。**理由已被數據坐實**：卡死的連線不會自己好（互鎖到 timeout），但隔幾秒的新連線常落在乾淨窗口 → 砍掉重連有效。**retry 只對純讀腳本**（`rp_svh_scan.py` / `stream_sp_scan.py` 冪等）；寫檔 / git 指令走 `--no-retry`，避免「指令已在 VPS 跑、本機 timeout 砍掉後 retry 跑第二份」撞車。timeout 設 45s 區分「卡 handshake」與「指令正常 e2e ~5s」。
- **~~F1 ControlMaster~~ — 砍掉**：Windows OpenSSH multiplexing 不可靠；且在**會丟封包的路徑**上，長壽的多工連線本身會 stall，反而把單次卡死放大成全 session 連鎖卡。
- **F3（邊際保險）**：本機 `~/.ssh/config` 加 `ConnectTimeout 15` + `Host vps` 別名。注意 `ServerAliveInterval` 對 **handshake 階段**卡死無效（連線還沒建立、沒有 session keepalive）——handshake 階段只有外層 `timeout`（F2）能救。
- **~~F4 fail2ban~~ — 不做**：bot flood 已證偽（`established ≤2`），與本 issue 無因果。

## 參考

- VPS 連線資訊：`~/.claude/projects/.../memory/reference_vps.md`
- 受影響 skill：`.claude/commands/rp-svh.md`、`stream-sp.md`、`stream-sp-deep.md`、`weekly-review.md` 的 Step「SSH 跑機械層」
