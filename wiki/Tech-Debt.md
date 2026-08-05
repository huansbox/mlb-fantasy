# 技術債

> 快照日期：2026-08-05。依**利息**排序——利息高 = 平常就在付出成本；利息低 = 特定情境才痛。技術債 = 已知的權衡，記錄成本與償還條件，**不代表馬上要處理**。多數項目在 repo `issues/` 有對應追蹤檔。

## 高利息（每天都在付成本）

| 債 | 成本（利息） | 償還策略／條件 | 追蹤 |
|---|---|---|---|
| **單一封閉平台依賴（Yahoo API）**【已實現，非假設】 | 2026-07-28 起系統約 90% 功能停擺且**無恢復時程可控** — FA 掃描、週中戰術、roster 同步、對帳回路全斷。write scope 更早在 2025-10 就被移除，「AI 全自動代打理」的長期方向直接失效 | **無法根治**：換平台已否決（聯盟夥伴都在 Yahoo）。已做的減損是把不依賴 Yahoo 的能力（日報、球員評估）隔離出來獨立運作。下一個決策點 2026-08-19 | [Plan](Plan) 決策點；memory `project_yahoo_api_revoked` |
| `roster_config.json` 凍結於 2026-07-22 | 陣容唯一來源不再自動同步，人工異動後若忘記編輯，**日報建議會靜默偏差**（建議一個已不在隊上的球員） | Yahoo 恢復即自動解決；期間靠人工編輯 + 看日報時目視對帳 | CLAUDE.md 頂端狀態區塊 |

## 中利息（特定操作就會痛）

| 債 | 成本（利息） | 償還策略／條件 | 追蹤 |
|---|---|---|---|
| waiver-log NEW 入口 mlb_id 誤配 | 同名球員新增時才觸發，但一旦寫錯會**長期靜默誤導**該球員的所有後續追蹤（auto-close 端已根治，入口端未驗證） | NEW 寫入前走 Yahoo API 交叉驗證 team / position，不符即標記人工確認 | CLAUDE.md 待辦 |
| `docs/player-eval-sp.md` 4 處裸 SSH | 每次 `/player-eval` SP 子流程有機率撞 30-40s handshake 卡死（含 2 處 here-doc） | here-doc 轉 VPS 端腳本後，4 處全部改走 `vps-run.sh` wrapper | `issues/player-eval-sp-ssh-wrapper.md` |
| 本機↔VPS 間歇丟包（環境債）【接受現狀】 | 新增任何 SSH step 都要記得走 wrapper 的心智負擔；漏了就偶發卡死 | **明文接受現狀**：不追根治（根因在網路路徑）；維持 wrapper 約定 + 新增 SSH step 時檢查 | `issues/vps-ssh-handshake-hang.md` |

## 低利息（記錄在案）

| 債 | 成本（利息） | 償還策略／條件 |
|---|---|---|
| SP / Batter 框架不對稱 | 規則漂移風險 + 每次框架討論的認知負擔 | 條件：batter Phase 6 升級決策時一併定案——升 batter 或明文維持 thin |
| 042 payload 注入暫緩帳 | 「暫緩但未結案」的追蹤負擔 | B7 backfill 已於 2026-07-07 完成（原重啟條件達成），但重評需要真實翻供／drop 回溯案例，而 fa_scan 停擺期間不會產生 — 實質延後至平台恢復 |
| 殘留診斷檔 | repo root 的 `bash.exe.stackdump` / `ssh_diag.sh` / `ssh_diag_analyze.sh`，加上 `daily-advisor/bash.exe.stackdump` 造成的雜訊 | 搭車處理：碰到該區時順手移除或歸檔 `archive/` |
| 歷史設計文件已 superseded 未歸檔 | 誤讀舊設計的低機率風險 | 已靠 CLAUDE.md 檔案索引「歷史」列標註；不另動 |
| handoff 過渡文件治理靠約定 | 殭屍 handoff 累積 | 維持「active 進待辦、done 即刪」約定；`glob docs/handoff-*` 可稽核 |

## 利息暫停（債還在，但當前不收利息）

Yahoo API 中斷期間這些債不再造成日常成本 —— **不是還完了，是暫時碰不到**。平台恢復即回到原本的利息水準。

| 債 | 原本的利息 | 恢復後的償還條件 |
|---|---|---|
| 百分位表仍是 2025 基線 | 每日 FA scan 的 Sum 打分 / tag 門檻全建立在上季分布上，每次掃描都付一點判斷偏差 | 跑 `calc_percentiles_2026.py` 產 2026 分布 → 同步 CLAUDE.md 百分位表 + daily_advisor + prompt 檔。**注意：2026 賽季結束後這條會變成「2027 前必還」** |
| stream-sp registry 的 true_starter 盲邊 | 機械層判 `true_starter` 時不查角色 registry，role-capped SP 會以 true_starter 進主表，靠 pending row 的 deep verdict 兜底 | 條件：再實戰出現一次 → skill 過濾規則加一行「主表候選也對照 registry」 |

## 記帳原則

- **入場資格**：新債必須寫明「成本（利息）→ 償還策略或條件」——沒有成本描述的不收，防止清單變垃圾場
- **接受現狀要明文標註**（如【接受現狀】），避免每次盤點重新吵一遍
- **修完即刪**：償還後同步刪除本頁條目，摘要移入下方歷史償還紀錄
- **停用 ≠ 償還**：功能停擺期間債務移入「利息暫停」而非刪除，避免恢復時被當成新問題重新發現
- 高利息項優先於新功能切片（誤導決策的債 = 負產出）

## 歷史償還紀錄

債務會被還的證據（詳情看 git log / 對應 issue）：

- 2026-08-05 — **日報靜默停擺**：`claude -p` token 於 2026-07-22 過期（`refreshToken` 是空字串，續期鏈斷），日報停發兩週無人察覺。以獨立 cron 的 heartbeat 檢查償還（`heartbeat_check.py`，48h 門檻 + Telegram 警告，22 tests）；刻意與 `daily_advisor` 雙向不 import，確保被監控者掛掉時監控仍活著
- 2026-07-08 — **batter backtest 無非空對帳**：C1 共用引擎完工並 production 驗證，SP 端自 06-21、batter 端自 07-05 產出真帳，裁判抽查 PASS。「無回饋迴路下運行」的高利息債結清
- 2026-07-07 — `issues/011` deep parity 以 OBE 結案：deep_batch 上線 6 週 ~20 次實戰無數值異常 + #406 e2e 雙模式輸出全等 + #408 對照官方端點
- `1a56c6f` — roster_sync 同步窗口拉到 30h：修掉「Daily-Tomorrow 次日生效 claim 被浮水印永久跳過」
- 2026-06-12 — watermark 第三次根修驗證完成（monotonic `compute_watermark` + 每日 `--reconcile` 全量對帳網）
- `d18207e` — fa_scan batter payload 歷史截斷（觀察中段 −59.7%，止住只進不出的複利成長）
- `fc55fae` — payload hygiene 小修（issue 033）
- 2026-06-05 — 退役 `fa_scan.py --rp` 全部殘留（v2 指標週掃 → `/rp-svh` 取代，連帶清死碼島）
- `bin/vps-run.sh` wrapper 落地 — SSH handshake 卡死止血，主要 skills 的 SSH step 全數納入
