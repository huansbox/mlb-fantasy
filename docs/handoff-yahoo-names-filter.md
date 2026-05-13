# Handoff — Yahoo `--names` filter（CLI 層）

> **✅ 完成（2026-05-13 commit `f688f48`）**：CLI `--names` / `--auto-page` flag 上線，抽出 `yahoo_query.query_fa()` importable helper，`stream_sp_scan.fetch_yahoo_fa_sp_pool` 改 import。VPS 4 case 驗證通過（hits / nonexistent / single-page / auto-page 300 行），stream_sp_scan e2e 維持 ~5.0s。8 個新 unit tests 全綠（test_yahoo_query.py），305 全 regression 通過。下面內容保留作歷史脈絡。
>
> 寫於 2026-05-13。前置工作 commits：`b672713` (function 層短路) / `5c7a71e` (skill 接 stream_sp_scan)。

## 上下文：兩個層級的「names filter」

stream_sp_scan 流程是「拿到當天 probable starter 名單 → 查這些名字是否為 FA」。Yahoo FA pool 一次只能查 25 row、最多 12 頁 ~300 row。若直接拉全部，多數 row 都不是我們要的（probable starter 通常 8-16 人，剩下 ~280 row 浪費）。

「`--names` filter」可以發生在兩個層：

| 層 | 已完成？ | 實作位置 | 效果 |
|---|---|---|---|
| **Function 層**（in-process） | ✅ commit `b672713` | `daily-advisor/stream_sp_scan.py::fetch_yahoo_fa_sp_pool(starter_names)` | 內部分頁時邊抓邊比對 `starter_names`，全部 hits 找到後 early-stop。e2e 5.2s（從 ~10-15s）。 |
| **CLI 層**（yahoo_query.py） | ❌ **本 handoff 待做** | `daily-advisor/yahoo_query.py` `cmd_fa` 沒 `--names` flag | 手動 debug 仍要 `for s in 0 25 50 ... do python3 yahoo_query.py fa -p SP --start $s; done` 拉滿 12 頁 |

## 為什麼還要做 CLI 層

1. **手動 debug**：「我想看 Sean Burke 在 Yahoo 看到的狀態」目前要 grep 12 頁 output。`python3 yahoo_query.py fa -p SP --names "Sean Burke"` 一行解決。
2. **DRY**：function 層的 paging+filter+early-stop 邏輯目前在 `stream_sp_scan.fetch_yahoo_fa_sp_pool` 重複實作了一份。CLI 提供 `--names` 後可以集中。
3. **未來其他 script 復用**：cron / 其他 skill 想查特定球員 FA 狀態時不必各自重寫 paging loop。

## 現況：cmd_fa 是「單頁」

`yahoo_query.py:209 cmd_fa` 本身**不分頁**，每次只查 `--start N --count 25` 一頁。分頁是 caller 的責任（外層 shell loop 或 stream_sp_scan 內部 loop）。

這代表 `--names` filter 在 CLI 層有兩種設計：

### Plan A — `--names` 純客戶端 filter（最小改動）

只過濾**單頁** output 不影響分頁。
- argparse 加 `--names "a,b,c"`
- cmd_fa 末段印行時，若球員名不在 names set 就 skip
- caller 仍負責 loop 12 頁
- 好處：~10 行改動，與既有 `--start` 模型一致
- 缺點：無法 early-stop 分頁，CLI 層省不了 API call；只省 stdout 噪音

### Plan B — `--names` + 內建分頁 + early-stop（與 function 層對齊）

- 加 `--auto-page` 或讓 `--names` 隱含 auto-page
- cmd_fa 內部 loop 12 頁，每頁過濾，全 hits 找到後 break
- 好處：CLI 也享受 ~5s 而非 ~15s；function 層可改成 subprocess call CLI（DRY）
- 缺點：~40 行改動、改變 cmd_fa 行為模型、需要決定 `--start` 與 `--auto-page` 互斥語意

**推薦 Plan B**，因為 DRY 收益大且 function 層之後可以變 thin wrapper。但 Plan A 是合理的逐步演進起點。

## 實作骨架（Plan B）

```python
# yahoo_query.py main() 內加：
fa_parser.add_argument(
    "--names",
    help="Filter to specific player names (comma-separated). "
         "Implies --auto-page (loops through pages until all hits found).",
)
fa_parser.add_argument(
    "--auto-page",
    action="store_true",
    help="Loop pages until empty (default: single page from --start).",
)

# cmd_fa 重構為：
def cmd_fa(args, access_token, config):
    target_names = (
        {n.strip() for n in args.names.split(",") if n.strip()}
        if args.names else None
    )
    auto_page = bool(args.auto_page or target_names)
    start = args.start

    all_players = []
    while True:
        page = _fetch_fa_page(start, args, access_token, config)  # 抽既有邏輯
        if not page:
            break
        if target_names:
            hits = [p for p in page if p["name"] in target_names]
            all_players.extend(hits)
            found = {p["name"] for p in all_players}
            if target_names.issubset(found):
                break
        else:
            all_players.extend(page)
        if not auto_page or len(page) < args.count:
            break
        start += args.count

    _print_fa_results(all_players, args)  # 抽既有 print 邏輯
```

`_fetch_fa_page` / `_print_fa_results` 是抽出來的 helper。

之後 `stream_sp_scan.fetch_yahoo_fa_sp_pool` 可以簡化成：
```python
def fetch_yahoo_fa_sp_pool(starter_names=None):
    cmd = ["python3", "yahoo_query.py", "fa", "-p", "SP", "--status", "A"]
    if starter_names:
        cmd += ["--names", ",".join(starter_names)]
    else:
        cmd += ["--auto-page"]
    # subprocess + parse output
    ...
```

但 subprocess overhead 反而比 direct API 慢。另一個方向：把 `_fetch_fa_page` / 分頁邏輯包成 importable function `query_fa(names=, status=, position=, ...)` → list[dict]，CLI 跟 stream_sp_scan 都 import 它。**推薦這個方向**。

## 測試計畫

`yahoo_query.py` 目前**沒 pytest 測試**（system-boundary code，手動驗證）。新增 `--names` 後考慮：

1. **手動驗證**（與現況一致）：
   - `python3 yahoo_query.py fa -p SP --names "Sean Burke,Dustin May"` → 只印兩行
   - `python3 yahoo_query.py fa -p SP --names "Nonexistent Pitcher"` → 空結果（含 header），無 error
   - `python3 yahoo_query.py fa -p SP`（無 --names） → 行為不變（單頁 25 row from start=0）
   - `python3 yahoo_query.py fa -p SP --auto-page` → 印完整 ~300 row

2. **若抽 helper function**（推薦）：對 `query_fa()` helper 加 unit test
   - Mock `api_get` 回固定 page 資料
   - 驗證 names filter 邏輯 / early-stop 邏輯 / pagination

3. **回歸**：stream_sp_scan e2e 仍跑通（VPS 5.2s 不變）

## 尚待決定

1. **Plan A vs B**：見上。推薦 B + 抽 importable helper。
2. **CLI 輸出格式**：filter 後是否要加 `(N hits / pulled X pages)` 之類 summary？或保持完全靜默？
3. **`--names` 與 `--position` 互動**：若 `--names "X,Y"` + `--position SP`，X 是 RP 怎麼辦？目前 Yahoo API filter 是 server-side `position=SP`，X 若不是 SP 不會出現。要不要記錄 missing names？
4. **大小寫 / 撇號**：Yahoo 球員名可能 `José Buttó` 含 accent，stream_sp_scan 傳 names 是否要 normalize？看 `yahoo_query._normalize`（line 408）已有但 cmd_fa 沒用。

## 完成定義

- [ ] `python3 yahoo_query.py fa --help` 顯示 `--names` 跟 `--auto-page`
- [ ] 上述 4 個手動驗證 case 行為正確
- [ ] `stream_sp_scan` 改用 import 共用 helper（不再自己 loop API），test e2e 仍 5-6 秒
- [ ] commit message 註明此 handoff 完結

## 預估工作量

Plan B + 抽 helper：~60 分鐘
- argparse + cmd_fa 重構：20 分鐘
- 抽 `query_fa()` helper + stream_sp_scan 切換 import：20 分鐘
- 手動驗證 4 個 case + e2e：20 分鐘

## 相關 commits

- `96830ba` add stream_sp_scan.py via TDD
- `5c7a71e` wire stream_sp_scan into /stream-sp skill
- `b672713` fix review C1-C3 + function 層短路（本 handoff 的 function 層工作）
- `3cfd97e` review cleanup W1/W3/T2/T3

## 入手點

下次 session 動之前先：
1. `git log --oneline -10` 確認沒 conflict 中的並行工作
2. `python -m pytest daily-advisor/tests/test_stream_sp_scan.py` baseline 32 pass
3. 讀本檔 + `daily-advisor/stream_sp_scan.py::fetch_yahoo_fa_sp_pool` 對照 function 層邏輯
4. 開 branch `feat/yahoo-names-cli`（功能開發）動手
