# 技術債

> 快照日期：2026-07-04。依風險排序；多數項目在 repo `issues/` 有對應追蹤檔。

## 高風險（會誤導決策或斷 pipeline）

| 債 | 說明 | 償還策略 | 追蹤 |
|---|---|---|---|
| waiver-log NEW 入口 mlb_id 誤配 | `_update_waiver_log_locked` NEW 行走 `search_mlb_id(name)`，同名同姓可能取到錯的 mlb_id（auto-close 端已根治，入口端未做 Yahoo team/position 交叉驗證） | NEW 寫入前走 Yahoo API 交叉驗證 team / position，不符即標記人工確認 | CLAUDE.md 待辦 |
| 百分位表仍是 2025 基線 | 原訂 Week 6-8 更新 2026 當季分布，已逾期 — 全部 Sum 打分 / tag 門檻都建立在上季分布上，季中 drift 未量化 | 跑 `calc_percentiles_2026.py` 產 2026 分布 → 同步 CLAUDE.md 百分位表 + daily_advisor + prompt 檔 | `calc_percentiles_2026.py` 已備好 |
| batter backtest 尚無非空對帳 | SP 端 backtest 曾是空殼（regex 不匹配 + outcome stub，兩班 cron 全「no verdicts」）；修復已併入 C1 但 batter 第一筆可對帳需部署後 +21 天成熟期 | C1 共用引擎施工（修 SP parse regex + outcome fetch + 建 batter 端），部署後等 21 天資料成熟 | `docs/fa-scan-batter-judgment-quality.md` C1 |

## 中風險（已知缺口，有 workaround）

| 債 | 說明 | 償還策略 | 追蹤 |
|---|---|---|---|
| `docs/player-eval-sp.md` 4 處裸 SSH | 含 2 處 `python3 << EOF` here-doc，未走 `vps-run.sh` wrapper — `/player-eval` 是高頻 skill，會踩 SSH handshake 卡死。here-doc 需先轉 VPS 端腳本才能納入 | here-doc 轉 VPS 端腳本後，4 處全部改走 wrapper | `issues/player-eval-sp-ssh-wrapper.md` |
| 本機↔VPS 間歇丟包（環境債） | 根因在網路路徑，wrapper 只是止血；所有新增 SSH step 都必須記得走 wrapper，屬「約定防禦」而非結構性解 | 不追根治；維持 wrapper 約定 + 新增 SSH step 時檢查 | `issues/vps-ssh-handshake-hang.md` |
| 011 stream-sp-deep parity 未驗 | 010 refactor merge 半個月，未與 2026-05-16 手算基準比對 — deep 評估路徑正確性只有單元測試背書 | 重跑 refactored skill 對 2026-05-16 三 SP 手算數字，divergence 做 root cause 文件化 | `issues/011-stream-sp-deep-e2e-parity.md` |
| SP / Batter 框架不對稱 | SP 走完 B2（thin + 2-step LLM + anchor + backtest），batter 停在 v4 thin 無 anchor 機制 — 維持或升級需一次決定，避免規則漂移 | 排一次對稱性檢視定案：升 batter 或明文維持 thin | CLAUDE.md 待辦 |
| 042 payload 注入暫緩帳 | ledger 規則增益未證實 + drop 規則 blocked by B7 backfill — B7 完成前 042 處於「暫緩但未結案」狀態 | B7 backfill 完成後重啟 A/B 評估，屆時決議收或棄 | `docs/318b-injection-design.md` |

## 低風險（衛生 / 清理）

| 債 | 說明 |
|---|---|
| repo root 殘留診斷檔 | `bash.exe.stackdump`、`ssh_diag.sh`、`ssh_diag_analyze.sh` — SSH 診斷完的遺留物，應移除或歸檔 `archive/` |
| 歷史設計文件已 superseded 未歸檔 | `fa_scan-claude-decision-layer-design` / `v4-cutover-plan` 等仍在 `docs/`，靠 CLAUDE.md 檔案索引的「歷史」列標註區分 |
| handoff 過渡文件治理靠約定 | 規則是「active 進待辦、done 即刪」，無機械檢查，容易累積殭屍 handoff |

## 償還原則

- 高風險項優先於新功能切片（誤導決策的債 = 負產出）
- 環境債（SSH）不追根治，維持 wrapper 約定 + 新 code review 時檢查
- 衛生項搭車處理：碰到該區檔案時順手清，不單開工單

## 歷史償還紀錄

債務會被還的證據（詳情看 git log / 對應 issue）：

- `1a56c6f` — roster_sync 同步窗口拉到 30h：修掉「Daily-Tomorrow 次日生效 claim 被浮水印永久跳過」
- 2026-06-12 — watermark 第三次根修驗證完成（monotonic `compute_watermark` + 每日 `--reconcile` 全量對帳網）
- `d18207e` — fa_scan batter payload 歷史截斷（觀察中段 −59.7%，止住只進不出的複利成長）
- `fc55fae` — payload hygiene 小修（issue 033）
- 2026-06-05 — 退役 `fa_scan.py --rp` 全部殘留（v2 指標週掃 → `/rp-svh` 取代，連帶清死碼島）
- `bin/vps-run.sh` wrapper 落地 — SSH handshake 卡死止血，主要 skills 的 SSH step 全數納入
