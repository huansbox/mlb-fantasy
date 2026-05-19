# Issue: VPS SSH 連線間歇性卡死（handshake 階段）

**狀態**：根因已確認 + 緩解已落地（2026-05-19）。**網路路徑間歇性雙向封包遺失**——非 sshd / ssh 設定層可修。pathping 已排除本機端前 4 跳（0% loss），loss 在不可控的國際 transit 段，不申告。緩解 F2（`bin/vps-run.sh` timeout + retry wrapper）已落地於 branch `feat/vps-ssh-retry-wrapper`，待 merge。
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

## loss 定位（pathping 2026-05-19）+ 「停止深挖」判斷

`pathping -q 50 -p 250 107.175.30.172` 結果：

```
hop 1  RT-N18U-F378  192.168.50.1               0% loss   家用路由器
hop 2  192.168.11.254                            0% loss   第二層 NAT / 數據機
hop 3  61-220-64-254.hinet-ip.hinet.net          0% loss   HiNet 邊緣
hop 4  168-95-211-14.tpdt-3310.hinet.net         0% loss   HiNet 骨幹
hop 5+ * * *                                     無法測量（路由器不回 ICMP TTL-exceeded）
```

判讀與決策：

- **本機端 + HiNet 入口前 4 跳全 0% loss** → 唯一本機可修的分支（路由器 / 線材 / Wi-Fi）**排除**。附帶發現家中雙層 NAT（192.168.50.x → 192.168.11.x），非 loss 來源。
- loss 在 hop 5+ 不可測段（國際 transit → ColoCrossing 機房），ICMP 量不到、也非本機可控。
- **判斷：停止深挖。** 再往下（VPS 端反向 mtr 等）只會得到「loss 在某個改不了的 transit AS」。F0 申告期望報酬低（消費級 ISP + 廉價 VPS、間歇 burst loss 常以「查無異常」結案），不主動做。緩解交給 F2，路徑爛不爛在操作層面就不重要了。

## 修正計畫

> 根因在網路路徑，**不是 sshd / ssh 設定層能修的**。本機端只能緩解。

- **F0（治本，不做）**：路徑申告期望報酬低（見上），擱置。若日後 loss 顯著惡化再帶 pcap 開 ticket。
- **F2（緩解，已落地 2026-05-19）**：見下「F2 落地紀錄」。
- **~~F1 ControlMaster~~ — 砍掉**：Windows OpenSSH multiplexing 不可靠；且在**會丟封包的路徑**上，長壽的多工連線本身會 stall，反而把單次卡死放大成全 session 連鎖卡。
- **~~F3 ~/.ssh/config~~ — 併入 F2**：`ConnectTimeout` 等 ssh 選項直接寫進 wrapper 的 `ssh` 呼叫（self-contained、跨機器 git pull 即生效），不另建機器本地的 `~/.ssh/config`。
- **~~F4 fail2ban~~ — 不做**：bot flood 已證偽（`established ≤2`），與本 issue 無因果。

## F2 落地紀錄（2026-05-19，branch `feat/vps-ssh-retry-wrapper`）

- **新增 `bin/vps-run.sh`**：`bash bin/vps-run.sh [--no-retry] '<remote command>'`。每次嘗試 `timeout -k 5 90 ssh -o ConnectTimeout=15 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3 ...`，預設 3 次嘗試。
  - **只對 retryable exit 重試**：124（timeout）/ 137（SIGKILL）/ 255（ssh 連線錯誤）。0 或 1-254 的真實 remote exit **不重試**（重試救不了真失敗）。
  - `--no-retry`：單次嘗試。寫檔 / git 指令用——避免「指令已在 VPS 跑、本機 timeout 砍掉 ssh 後 retry 跑第二份」。
  - timeout 預設 90s（高於任何 legit 指令 runtime，只砍真 hang）；`VPS_RUN_TIMEOUT` / `VPS_RUN_TRIES` 可覆寫。
  - retry 訊息走 stderr，stdout 維持純 remote 輸出（skill 當 JSON parse）。
- **改 4 個 skill md（共 6 處 SSH）走 wrapper**：`rp-svh`（1，retry）/ `stream-sp`（1，retry）/ `stream-sp-deep`（3，retry）/ `weekly-review`（1，`--no-retry` — `weekly_review.py --prepare` 會寫檔）。
- **e2e 驗證**：success 透傳 exit 0 / 真失敗 `exit 7` 不重試直接透傳 / 用法錯誤 exit 2 / `--no-retry` 單次。測試當下實地撞到一次 ssh 連線逾時（exit 255）→ 自動 retry → 第 2 次成功，wrapper 行為符合預期。
- CLAUDE.md「執行環境」+「檔案索引」同步更新。

## 參考

- VPS 連線資訊：`~/.claude/projects/.../memory/reference_vps.md`
- 受影響 skill：`.claude/commands/rp-svh.md`、`stream-sp.md`、`stream-sp-deep.md`、`weekly-review.md`
