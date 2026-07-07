# 技術債

> 快照日期：2026-07-07。依**利息**排序——利息高 = 平常就在付出成本；利息低 = 特定情境才痛。技術債 = 已知的權衡，記錄成本與償還條件，**不代表馬上要處理**。多數項目在 repo `issues/` 有對應追蹤檔。

## 高利息（每天都在付成本）

| 債 | 成本（利息） | 償還策略／條件 | 追蹤 |
|---|---|---|---|
| 百分位表仍是 2025 基線 | 每日 FA scan 的 Sum 打分 / tag 門檻全建立在上季分布上，季中 drift 未量化——**每一次掃描都付一點判斷偏差** | 跑 `calc_percentiles_2026.py` 產 2026 分布 → 同步 CLAUDE.md 百分位表 + daily_advisor + prompt 檔 | `calc_percentiles_2026.py` 已備好 |
| batter backtest 尚無非空對帳 | 每天的 batter add/drop 決策都在**無回饋迴路**下運行（SP 端曾靜默空殼近月未察覺） | C1 共用引擎施工（修 SP parse regex + outcome fetch + 建 batter 端）；條件：部署後 +21 天資料成熟才有第一筆帳 | `docs/fa-scan-batter-judgment-quality.md` C1 |

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
| 042 payload 注入暫緩帳 | 「暫緩但未結案」的追蹤負擔 | 條件：B7 backfill 完成後重啟 A/B 評估，屆時收或棄 |
| repo root 殘留診斷檔 | `bash.exe.stackdump`、`ssh_diag*.sh` 造成的雜訊 | 搭車處理：碰到該區時順手移除或歸檔 `archive/` |
| stream-sp registry 的 true_starter 盲邊 | 機械層判 `true_starter` 時不查角色 registry — role-capped SP（混 GS 且 avg IP >4，如 Alvarez 型）會以 true_starter 進主表，registry 記載的 workload cap 未被對照；現靠 pending row 的 deep verdict 兜底（2026-07-07 首航實測） | 條件：再實戰出現一次 → skill 過濾規則加一行「主表候選也對照 registry」 |
| 歷史設計文件已 superseded 未歸檔 | 誤讀舊設計的低機率風險 | 已靠 CLAUDE.md 檔案索引「歷史」列標註；不另動 |
| handoff 過渡文件治理靠約定 | 殭屍 handoff 累積 | 維持「active 進待辦、done 即刪」約定；`glob docs/handoff-*` 可稽核 |

## 記帳原則

- **入場資格**：新債必須寫明「成本（利息）→ 償還策略或條件」——沒有成本描述的不收，防止清單變垃圾場
- **接受現狀要明文標註**（如【接受現狀】），避免每次盤點重新吵一遍
- **修完即刪**：償還後同步刪除本頁條目，摘要移入下方歷史償還紀錄
- 高利息項優先於新功能切片（誤導決策的債 = 負產出）

## 歷史償還紀錄

債務會被還的證據（詳情看 git log / 對應 issue）：

- 2026-07-07 — `issues/011` deep parity 以 OBE 結案：deep_batch 上線 6 週 ~20 次實戰無數值異常 + #406 e2e 雙模式輸出全等 + #408 對照官方端點，原 regression 疑慮已被覆蓋（檔已刪，紀錄見 #409 關閉留言）

- `1a56c6f` — roster_sync 同步窗口拉到 30h：修掉「Daily-Tomorrow 次日生效 claim 被浮水印永久跳過」
- 2026-06-12 — watermark 第三次根修驗證完成（monotonic `compute_watermark` + 每日 `--reconcile` 全量對帳網）
- `d18207e` — fa_scan batter payload 歷史截斷（觀察中段 −59.7%，止住只進不出的複利成長）
- `fc55fae` — payload hygiene 小修（issue 033）
- 2026-06-05 — 退役 `fa_scan.py --rp` 全部殘留（v2 指標週掃 → `/rp-svh` 取代，連帶清死碼島）
- `bin/vps-run.sh` wrapper 落地 — SSH handshake 卡死止血，主要 skills 的 SSH step 全數納入
