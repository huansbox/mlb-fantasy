# 技術債

> 快照日期：2026-07-04。依風險排序；多數項目在 repo `issues/` 有對應追蹤檔。

## 高風險（會誤導決策或斷 pipeline）

| 債 | 說明 | 追蹤 |
|---|---|---|
| waiver-log NEW 入口 mlb_id 誤配 | `_update_waiver_log_locked` NEW 行走 `search_mlb_id(name)`，同名同姓可能取到錯的 mlb_id（auto-close 端已根治，入口端未做 Yahoo team/position 交叉驗證） | CLAUDE.md 待辦 |
| 百分位表仍是 2025 基線 | 原訂 Week 6-8 更新 2026 當季分布，已逾期 — 全部 Sum 打分 / tag 門檻都建立在上季分布上，季中 drift 未量化 | `calc_percentiles_2026.py` 已備好 |
| batter backtest 尚無非空對帳 | SP 端 backtest 曾是空殼（regex 不匹配 + outcome stub，兩班 cron 全「no verdicts」）；修復已併入 C1 但 batter 第一筆可對帳需部署後 +21 天成熟期 | `docs/fa-scan-batter-judgment-quality.md` C1 |

## 中風險（已知缺口，有 workaround）

| 債 | 說明 | 追蹤 |
|---|---|---|
| `docs/player-eval-sp.md` 4 處裸 SSH | 含 2 處 `python3 << EOF` here-doc，未走 `vps-run.sh` wrapper — `/player-eval` 是高頻 skill，會踩 SSH handshake 卡死。here-doc 需先轉 VPS 端腳本才能納入 | `issues/player-eval-sp-ssh-wrapper.md` |
| 本機↔VPS 間歇丟包（環境債） | 根因在網路路徑，wrapper 只是止血；所有新增 SSH step 都必須記得走 wrapper，屬「約定防禦」而非結構性解 | `issues/vps-ssh-handshake-hang.md` |
| 011 stream-sp-deep parity 未驗 | 010 refactor merge 半個月，未與 2026-05-16 手算基準比對 — deep 評估路徑正確性只有單元測試背書 | `issues/011-stream-sp-deep-e2e-parity.md` |
| SP / Batter 框架不對稱 | SP 走完 B2（thin + 2-step LLM + anchor + backtest），batter 停在 v4 thin 無 anchor 機制 — 維持或升級需一次決定，避免規則漂移 | CLAUDE.md 待辦 |
| 042 payload 注入暫緩帳 | ledger 規則增益未證實 + drop 規則 blocked by B7 backfill — B7 完成前 042 處於「暫緩但未結案」狀態 | `docs/318b-injection-design.md` |

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
