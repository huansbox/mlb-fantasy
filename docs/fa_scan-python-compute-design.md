# fa_scan Python Compute Layer — Design + Plan

**狀態**：✅ 已實作完成（2026-04-21 merged master `a5d057a`）— smoke test 5:33 vs 重構前 40 分鐘
**Architect 審查結果**：通過（5 finding，A 已修，C/D/E 記入 CLAUDE.md 待辦未來處理）
**前置**：feat/sp-framework-v2 分支已完成 SP 框架 v2（Sum / urgency 四因子 / ✅⚠️ 標籤 / 升級判定 / Layer 1.5 RP filter / savant_rolling pitcher 21d 擴充）
**目標分支**：從 `feat/sp-framework-v2` 開新分支 `feat/phase5-python-compute`（已 merge 並刪除）
**架構模式**：architect-builder（本檔由 Architect 寫，user 另開 session 當 Builder 實作，再回 Architect 審查）
**完整實作記錄**：見 Obsidian worklog [[評估框架]] §「2026-04-21 更新」

---

## 1. Why（rationale）

### 1.1 現況問題（2026-04-21 SP 框架 v2 實測）

| 觀察 | 數據 |
|------|------|
| Pass 1/2 完全靠 Claude prompt 計算 Sum/urgency/標籤 | prompt 大小 61KB |
| Claude `claude -p` 內建 timeout 600s | batter Pass 2 attempt 1 超時 → retry 再 10 分鐘 |
| 實測單 group 跑時間 | **20 分鐘**（含 1 次 timeout retry）|
| batter + SP 依序跑（無並行）| 完整 fa_scan 預估 **40 分鐘** |
| Pass 1 JSON parse 偶發失敗 | 走 code fallback（已有 `_fallback_weakest`）|
| 機械化規則由 LLM 算 | 不可審計、不可單元測試、慢 |

### 1.2 重構目標

1. **計算機械化** — Sum / urgency / 標籤 / 升級判定 全部 Python 確定性實作 + 單元測試
2. **Claude 角色縮小** — 只做「文字化 reason + 邊界 case flag」(Q5 選 B)
3. **batter / SP 並行** — threading 讓兩 group 同時跑，總時間 ≈ max(batter, SP) 而非 sum
4. **timeout 不再是 blocker** — prompt 從 61KB → ~15KB，Claude call 從 5-20 分鐘 → 1-3 分鐘

### 1.3 為什麼現在重構

- 今天 SP 框架 v2 把 prompt 加大到 61KB（增 5 ✅ 6 ⚠️ 標籤 + 21d 因子 + IP/TG）
- Claude timeout 開始成為 daily blocker
- 框架規則已穩定（Q3 確認不改規則只搬實作），重構時機成熟
- 重構同時順便修 #1 timeout / #2 prior IP <50 邊界 bug

---

## 2. 範圍邊界（Q3 已對齊）

**✅ 包含**：
- `daily-advisor/fa_scan.py` 機械計算層抽出
- `daily-advisor/fa_compute.py` 新檔（Python 實作所有規則）
- batter / SP threading 並行（Q4 選 A）
- 順便修 #1 timeout 600→900（重構後可能不需要）
- 順便修 #2 prior IP <50 邊界（Python 規則加防呆，避免 López 5 IP 誤判結構性確認）
- 順便修 #3 waiver-log auto-commit push branch bug（hard-coded master → current branch）
- 單元測試：`daily-advisor/tests/test_fa_compute.py`

**❌ 不包含**：
- RP scan（用戶決定不動）
- daily_advisor.py / weekly_review.py（不在 fa_scan 範圍）
- Sum 表 / urgency 因子 / ✅⚠️ 標籤規則（規則不變，只搬實作）
- 21d Δ 門檻校準（Phase 2 後 2 週另案）

---

## 3. 架構

### 3.1 Layer 結構（重構後）

```
Layer 1: Yahoo FA snapshot           (不變)
Layer 2: Savant CSV quality filter   (不變)
Layer 3: Enrich (MLB stats + derived) (不變)
Layer 4 [新]: 機械計算（fa_compute.py）
  ├─ pick_weakest()           — Sum 計分 + BBE <30 移出 + cant_cut 排除
  ├─ compute_urgency()        — 四因子加分 + Slump hold + prior IP 防呆
  ├─ compute_fa_tags()        — Sum 差 + ✅⚠️ 標籤 + 升級判定
  └─ evaluate_obs_changes()   — 觀察中 emoji 分類（指標惡化/即將觸發/%owned 升）
Layer 5 [改]: Claude 文字化 + 邊界 flag（取代 Pass 1/2 prompt-based 計算）
  ├─ 輸入：Layer 4 機械報告（已算分數 + 標籤 + 升級判定）
  ├─ Claude 任務：把 breakdown 翻成中文 reason 文字 + flag 規則沒覆蓋的 edge case + 整合 waiver-log 更新塊
  └─ Prompt 大小目標 < 15KB
Layer 6: Publish (Telegram + GitHub Issue) (不變)
```

### 3.2 Layer 4 模組設計（`fa_compute.py`）

純 Python 函式，無 IO（測試友善）：

```python
# fa_compute.py — Python compute layer for fa_scan.

from typing import TypedDict, Literal

PlayerType = Literal["batter", "sp"]


def compute_sum_score(metrics: dict, player_type: PlayerType) -> tuple[int, dict]:
    """3-metric Sum (xwOBA+BB%+Barrel% / xERA+xwOBA+HH%) → (score, breakdown).

    Args:
        metrics: {"xwoba": float, "bb_pct": float, "barrel_pct": float} (batter)
                 or {"xera": float, "xwoba": float, "hh_pct": float} (sp)
        player_type: "batter" or "sp"

    Returns:
        (sum_score, breakdown_dict)
        sum_score: 3-30
        breakdown: {"xwOBA": 5, "BB%": 3, ...} per metric
    """


def pick_weakest(
    roster: list[dict],
    savant_2026: dict,
    player_type: PlayerType,
    n: int = 4,
    cant_cut: set[str] = None,
) -> tuple[list[dict], list[dict]]:
    """Pick weakest N + low_confidence_excluded.

    Returns:
        (weakest, excluded)
        weakest: [{name, sum, breakdown, confidence, mlb_id, ...}]
        excluded: [{name, bbe, note}] (BBE <30)
    """


def compute_2025_sum(prior_stats: dict, player_type: PlayerType) -> tuple[int, dict]:
    """Same as compute_sum_score but for prior_stats schema (2025)."""


def compute_urgency(
    weakest_4: list[dict],
    prior_stats_lookup: dict[str, dict],  # name → prior_stats
    rolling_lookup: dict[str, dict],       # mlb_id_str → 21d/14d data
    season_savant_lookup: dict,
    derived_2026_lookup: dict[str, dict],  # name → {ip_per_tg, ip_per_gs, era_diff}
    player_type: PlayerType,
) -> dict:
    """Compute urgency 4-factor for each weakest player.

    Returns:
        {
            "weakest_ranked": [{name, urgency, factors: {...}, slump_hold: bool, ...}],
            "slump_hold": [{name, prior_sum, prior_ip}],
        }

    Factors per player:
        - 2026 Sum (already in weakest input)
        - 2025 Sum (computed, with IP ≥50 gate for Slump hold)
        - 21d Δ xwOBA (or 14d for batter, with BBE ≥20 gate)
        - 2026 IP/TG (or PA/TG for batter)

    Rule additions for #2 bug fix:
        - prior IP <50 → 2025 Sum scoring still happens but no Slump hold
        - prior IP <SOME_THRESHOLD (TBD, 20?) → treat as no prior (avoid 5 IP noise)
    """


def compute_fa_tags(
    fa_player: dict,
    anchor_player: dict,  # weakest with lowest urgency to compare
    player_type: PlayerType,
) -> dict:
    """Compute Sum diff + ✅⚠️ tags + 升級判定 for one FA candidate.

    Returns:
        {
            "sum_diff": int,
            "breakdown_diff": dict,
            "win_gate_passed": bool,  # Sum diff ≥3 + ≥2 positive
            "add_tags": list[str],  # ✅ 標籤
            "warn_tags": list[str], # ⚠️ 標籤
            "decision": Literal["立即取代", "取代", "觀察", "pass"],
        }

    Tag rules (SP):
        ✅ 雙年菁英  — 2025 Sum ≥24 且 IP ≥50
        ✅ 深投型   — IP/GS >5.7
        ✅ 球隊主力 — IP/Team_G ≥1.0
        ✅ 近況確認 — 21d Δ xwOBA ≤ -0.035
        ✅ 撿便宜運氣 — xERA-ERA ≤ -0.81
        ⚠️ 短局 (強)   — IP/GS <5.0
        ⚠️ 上場有限(強) — IP/TG <0.5
        ⚠️ 樣本小  — BBE <30 或 IP <20
        ⚠️ Breakout 待驗 — 2025 Sum <18 或無 prior
        ⚠️ 賣高運氣 — xERA-ERA ≥ +0.81
        ⚠️ 近況下滑 — 21d Δ xwOBA ≥ +0.035

    Decision:
        ≥2 ✅ + 無 ⚠️ → 立即取代
        1 ✅ + 無強警示(短局/上場有限) → 取代
        其他 → 觀察
        win_gate_passed=False → pass
    """


def evaluate_obs_changes(
    watch_player: dict,
    current_savant: dict,
    rolling: dict,
    history: dict,  # %owned history
    player_type: PlayerType,
) -> dict | None:
    """Evaluate one watch player for status changes.

    Returns:
        None if no significant change (常態追蹤省略)
        Or {"emoji": "⚠️", "type": "quality_decay", "change_text": "..."}

    Emoji types:
        ⚠️ 品質惡化 — 指標跌破 watch-log 觸發門檻
        ✅ 即將觸發 — BBE 或 IP 距觸發 ≤10
        ❌ %owned 急升 — 3 日 +5 以上
        🔄 角色變化 — IL/輪值/swingman 變化（手動 flag，自動偵測難）
    """
```

### 3.3 Layer 5 Claude prompt 重寫

**舊 Pass 2 prompt（61KB）內容**：
- 完整評估框架（從 CLAUDE.md 拉）
- Sum 計算規則表（P25-P90）
- urgency 四因子加分表
- ✅⚠️ 標籤條件表
- 升級判定表
- 我方最弱 4 人原始資料（Savant + prior + 21d）
- 14 FA 原始資料（Savant + prior + 21d + IP/GS）
- waiver-log 觀察中
- 命令 Claude **「按表打分 + 算 urgency + 判標籤 + 決定升級」**

**新 Pass 2 prompt（目標 < 15KB）內容**：
- 簡短任務說明（你是 fantasy 顧問，把以下機械報告翻成 reason 文字）
- 機械報告（Layer 4 產出）
  - 我方最弱 4 人 + urgency 已排序
  - FA 候選 + ✅⚠️ 已標好 + 升級已判定
  - 觀察中變化 emoji 已分類
- 命令 Claude：
  1. 對每位 weakest 寫 1-2 句定性 reason（基於 breakdown）
  2. 對每位 FA 寫 1-2 句說明（為什麼這個決定）
  3. 對觀察中變化寫變化內容
  4. flag 機械規則沒覆蓋的 edge case（例如 López 2025 5 IP）
  5. 組 waiver-log 更新區塊（NEW/UPDATE 行）

### 3.4 並行（Q4 選 A：threading）

```python
# 取代 _run_daily_scan 的 sequential calls
import threading

class GroupResult:
    def __init__(self):
        self.advice_display = None
        self.advice_issue = None
        self.full_raw = None
        self.error = None

batter_result = GroupResult()
sp_result = GroupResult()

def _run_group(group_type, result_obj):
    try:
        # 整個 _process_group_v2 的工作
        result_obj.advice_display, result_obj.advice_issue, result_obj.full_raw = \
            process_group_v2(group_type, ...)
    except Exception as e:
        result_obj.error = e

t_batter = threading.Thread(target=_run_group, args=("batter", batter_result))
t_sp = threading.Thread(target=_run_group, args=("sp", sp_result))
t_batter.start()
t_sp.start()
t_batter.join()
t_sp.join()

# 依序 publish（Telegram 順序固定）
if batter_result.error:
    _handle_error("batter", batter_result.error, env, args)
else:
    _publish(today_str, "打者", batter_result.advice_display, ...)

if sp_result.error:
    _handle_error("SP", sp_result.error, env, args)
else:
    _publish(today_str, "SP", sp_result.advice_display, ...)
```

**注意**：`subprocess.run(claude -p)` 是 IO-bound（等 API），threading 不受 GIL 影響。

### 3.5 資料流（重構後）

```
roster_config + savant_2026 + savant_2025 + savant_rolling + standings
  ↓ (Layer 1-3, 不變)
enriched + watchlist
  ↓ (Layer 4: fa_compute)
機械報告 = {
  weakest: [
    {name, sum_2026, breakdown, urgency, factors_breakdown, slump_hold,
     prior_sum, prior_ip, ip_per_gs, ip_per_tg, era_diff, rolling_delta}
  ],
  low_confidence_excluded: [{name, bbe}],
  fa_decisions: [
    {name, team, position, pct, sum, sum_diff, breakdown_diff,
     add_tags, warn_tags, decision, anchor_name}
  ],
  observation_changes: [{name, emoji, type, change_text}],
}
  ↓ (Layer 5: Claude 文字化)
最終 advice text（同舊版格式輸出）
  ↓ (Layer 6: Publish)
Telegram + GitHub Issue
```

---

## 4. 程式骨架

### 4.1 新 / 改檔案

```
daily-advisor/
  fa_compute.py              ← 新檔，Layer 4 純 Python 計算
  fa_scan.py                 ← 改：抽出計算邏輯，加 threading 並行
  prompt_fa_scan_pass1_*.txt ← 移除（Layer 4 取代）
  prompt_fa_scan_pass2_*.txt ← 大幅縮減為「文字化任務」
  tests/
    __init__.py              ← 新
    test_fa_compute.py       ← 新檔，Layer 4 單元測試
    fixtures/
      sample_roster.json
      sample_savant.json
      sample_rolling.json
```

### 4.2 fa_compute.py 完整函式簽章

見 §3.2。

### 4.3 fa_scan.py 改動點

| 函式 | 動作 |
|------|------|
| `_process_group()` | **拆掉** — 改為 `process_group_v2(group_type, enriched, watch_enriched, ...)` 內部呼叫 fa_compute + Claude 文字化 |
| `_call_claude()` | **保留** + timeout 從 600 → 900 |
| `build_roster_for_pass1()` | **移除**（Layer 4 取代）|
| `_build_pass2_data()` | **改寫** — 接收 fa_compute 機械報告，組成 Claude 文字化 prompt input |
| `_run_daily_scan()` | **改 threading 並行**（§3.4）|
| `_update_waiver_log()` | **修 #3 bug** — git push 改用 current branch（`git rev-parse --abbrev-ref HEAD`），不 hard-code master |

---

## 5. 任務拆解（Phase 5.1 ~ 5.7）

每個 Phase 一個 commit。標 ⚡ 表示可並行（純 Python，無依賴）。

### Phase 5.1 ⚡：Sum 計分純 Python 實作 + 單元測試

**任務**：
- 新建 `fa_compute.py`
- 實作 `compute_sum_score(metrics, player_type)` for batter + SP（複用 fa_scan.py 既有 `_calc_batter_sum`，加 SP 反向版）
- 實作 `compute_2025_sum(prior_stats, player_type)`（從 prior_stats schema 算）
- 新建 `tests/test_fa_compute.py`，覆蓋 8 個百分位區間 × 2 player_type

**Acceptance**：
- 跑 `pytest tests/test_fa_compute.py::test_sum_score` 通過
- 對今天隊上 11 batter + 10 SP 實際數據算 Sum，跟今天 SP-only fa_scan 輸出的 Sum **完全一致**（regression test）

**估時**：1-1.5 hr

### Phase 5.2 ⚡：pick_weakest + low_confidence 邏輯

**任務**：
- 實作 `pick_weakest(roster, savant_2026, player_type, n=4, cant_cut=...)`
- 處理 BBE <30 移出 + cant_cut 排除 + IL/NA 排除
- 排序按 Sum 升冪取 N

**Acceptance**：
- SP 跑出最弱 4 = [Nola, Cantillo, López, ...?]，與今天 fa_scan 一致
- low_confidence_excluded = [Kelly]，與今天一致

**估時**：1 hr

### Phase 5.3 ⚡：urgency 四因子計算（含 #2 bug 修復）

**任務**：
- 實作 `compute_urgency()` with 四因子（2026 Sum / 2025 Sum / 21d Δ / IP/TG）
- Slump hold 判定（2025 Sum ≥24 + IP ≥50）
- **#2 bug 修復**：prior IP <20 → 視為無 prior 數據（避免 López 5 IP 誤判結構性確認 +2 分）
- 新增 `tests/test_urgency.py`

**Acceptance**：
- 對今天 SP-only：Nola urgency=6, Cantillo=4, López=**?**（重點：5 IP 噪音不應給 +2，預期 López urgency 從 3 降到 1 或 0）
- Ragans 標 Slump hold（不參與排序）
- Kelly 標低信心排除

**估時**：2 hr

### Phase 5.4 ⚡：FA 標籤 + 升級判定

**任務**：
- 實作 `compute_fa_tags(fa_player, anchor)` 含 5 ✅ + 6 ⚠️ + win gate + 升級判定
- 新增 `tests/test_fa_tags.py`

**Acceptance**：
- 對今天 SP-only FA 7 候選：
  - Pfaadt: 1 ✅(球隊主力) + 0 ⚠️ → 取代 ✓
  - Povich: 2 ✅(深投+球隊主力) + 2 ⚠️(賣高+breakout 非強) → 取代 ✓
  - Ginn: 0 ✅ + 強警示(短局) → 觀察 ✓
  - Myers/Brown/Winn: 觀察 ✓
- Sum diff 計算與 Claude 輸出一致

**估時**：2 hr

### Phase 5.5：Claude 文字化 prompt 重寫

**任務**：
- 改寫 `prompt_fa_scan_pass2_sp.txt` 為「文字化 + edge flag」格式
- 改寫 `prompt_fa_scan_pass2_batter.txt` 同樣
- 移除 `prompt_fa_scan_pass1_*.txt`（Layer 4 取代）
- 改 `_build_pass2_data()` 接收 fa_compute 機械報告
- 改 `_process_group()` → `process_group_v2()` 移除 Pass 1 Claude call

**Acceptance**：
- Prompt 大小 < 15KB（量 `len(full_prompt.encode())`）
- Claude call < 3 分鐘（單次）
- 輸出格式跟 SP 框架 v2 對齊（reason 文字 + ✅⚠️ 標籤 + waiver-log 區塊）

**估時**：1.5 hr

### Phase 5.6：batter / SP threading 並行 + #3 bug 修

**任務**：
- 改 `_run_daily_scan()` 用 threading.Thread 跑兩 group（§3.4 範本）
- Publish 順序固定（先 batter 後 SP，與現狀一致）
- 修 `_update_waiver_log()` git push 改用 current branch
- 順便 timeout 600 → 900（保險，雖然重構後可能不需要）

**Acceptance**：
- 完整 fa_scan 跑時間 ≈ max(batter, SP) ≈ 5-8 分鐘（今天 40 分鐘）
- VPS 在 feature branch 跑 fa_scan，waiver-log auto-commit push 到 current branch 不再 push 失敗

**估時**：1 hr

### Phase 5.7：整合測試 + cleanup

**任務**：
- 完整 fa_scan VPS smoke test（`--no-send` 模式）
- 移除 fa_scan.py 內舊 Pass 1 邏輯（`build_roster_for_pass1`, `_fallback_weakest` 等）
- 確認 batter / SP 輸出跟今天 SP 框架 v2 對齊（regression）
- 更新 CLAUDE.md 待辦：清掉 #1 timeout / #2 prior IP / #3 waiver push 三個 TODO

**Acceptance**：
- VPS `python3 fa_scan.py --no-send` 完整跑 < 10 分鐘
- 輸出格式跟 SP 框架 v2 對齊（人工 diff 檢查）
- 所有單元測試通過

**估時**：1.5 hr

**總工時估計**：約 10 hr（單人）

---

## 6. Acceptance Criteria（整體驗收）

1. ✅ **完整 fa_scan 跑時間 < 10 分鐘**（今天 40 分鐘）
2. ✅ **Pass 1 不再 JSON parse fail**（純 Python 不會 fail）
3. ✅ **Sum / urgency / 標籤 / 升級判定 對齊 SP 框架 v2 今天輸出**（regression diff）
4. ✅ **Claude call timeout 不再觸發**（每 call < 3 分鐘）
5. ✅ **單元測試覆蓋 fa_compute.py ≥ 80%**
6. ✅ **#1 timeout / #2 prior IP / #3 waiver push 三個 bug 全修**

---

## 7. 待決細節（Builder 階段或下次討論）

1. **prior IP 防呆門檻**：建議 `<20 IP → 視為無 prior`，但 `<50 IP → no Slump hold`（已定）。20 是猜的，Builder 可以拉 2025 SP IP 分布看 P10 / P25 決定
2. **並行錯誤處理**：batter thread crash 是否影響 SP？建議用 try/except 包裝（§3.4 範本已含）
3. **Claude 文字化失敗 fallback**：若 Claude call 失敗，是否回退純 Python 文字模板？建議**有**（保險）
4. **fa_compute.py 是否拆檔**：batter / SP 規則差異不大，建議單檔，內部用 player_type 分支
5. **waiver-log 觀察中變化偵測**：emoji 分類有些手動（🔄 角色變化），純 Python 偵測難，建議 Builder 評估後決定（可能保留 Claude 判斷這部分）
6. **既有 fa_scan.py code 處理**：Phase 5.7 cleanup 階段移除 deprecated code，還是保留？建議移除（避免技術債堆積）
7. **不在範圍但相關**：21d Δ 門檻校準（Phase 2 後 2 週）— 與 Phase 5 解耦，獨立另案

---

## 8. 實作策略（給 Builder）

### 8.1 開分支
```bash
git checkout feat/sp-framework-v2
git pull
git checkout -b feat/phase5-python-compute
```

### 8.2 Test-Driven Development（強烈建議）
- Phase 5.1 ~ 5.4 是純 Python 計算層，**先寫單元測試再寫實作**
- 用今天 SP-only fa_scan 實際輸出當 fixture（例：Nola urgency=6, Pfaadt 取代）
- pytest 跑通才寫 Layer 5

### 8.3 Smoke test 工具
- 重用今天加的 `--sp-only` / `--batter-only` flags 獨立驗證
- `--no-send` 跳 Telegram + Issue

### 8.4 commit 策略
- 每個 Phase 5.X 一個 commit
- Phase 5.1 ~ 5.4 commit 順序可彈性（純 Python 無依賴）
- Phase 5.5 ~ 5.7 必須在 5.1-5.4 完成後做（依賴 fa_compute）

### 8.5 完成後 PR
- PR 從 `feat/phase5-python-compute` → `feat/sp-framework-v2`
- 兩個分支一起 merge `master`（SP 框架 v2 + Phase 5 一次上線）

### 8.6 環境
- 本機開發 + 單元測試（不需 VPS）
- 整合測試在 VPS 跑（要 Yahoo token + Claude CLI）
- 移植到 VPS 走 git push + ssh checkout

---

## 9. Architect 審查重點（Builder 完成後）

回到 Architect session 時要檢查：

1. **規則對齊**：fa_compute.py 計算結果與 CLAUDE.md SP 評估段落 100% 對應（不是憑印象寫）
2. **單元測試覆蓋率**：所有百分位區間 + 邊界 case（BBE 29/30, IP 49/50, Sum 23/24）
3. **Regression test**：跑今天 SP-only 的 input → 輸出 Nola=6 / Cantillo=4 等核心數字必須一致
4. **prompt 大小**：實測 < 15KB
5. **整體跑時間**：實測 < 10 分鐘
6. **三 bug 修補確認**：#1 timeout / #2 prior IP / #3 waiver push
7. **無技術債**：deprecated code 已清除，無「TODO 改天再做」

---

## 10. 參考資料

- 今天 SP-only fa_scan 輸出（VPS `/tmp/fa_scan_sp_only.log`）— 137 行，含完整 Pass 2 advice
- CLAUDE.md `### SP 評估` section（規則來源）
- CLAUDE.md `### 2025 MLB 百分位分布` section（打分對照表）
- `daily-advisor/prompt_fa_scan_pass1_sp.txt`（v2 規則參考）
- `daily-advisor/prompt_fa_scan_pass2_sp.txt`（v2 規則參考）
- 今天 fa_compute 內可重用的函式：
  - `_calc_batter_sum()` — batter Sum 已有 Python 版
  - `_metric_to_score()` — 百分位 → 分數已有
  - `_ip_per_gs_from_gamelog()` — IP/GS 計算已有
  - `_compute_derived_pitcher()` — IP/TG / era_diff 計算已有
