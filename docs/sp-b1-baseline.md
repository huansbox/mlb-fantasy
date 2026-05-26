# SP B1 Cutover — Baseline Spike Results

> Issue: `issues/008-spike-fixture-baseline.md` · PRD: `issues/prd.md` · Design: `docs/sp-b1-cutover-design.md`

## Status

✅ **Spike + HITL complete (2026-05-26)** — baseline numbers populated, M4 redefined to M4' (top-position pair only), thresholds set, emitter/reader extended for M4'. Issue 009 unblocked.

| Phase | Status | Notes |
|-------|--------|-------|
| Spike runner extended (SP step1 + step2 + FA classify + rank) | ✅ | `daily-advisor/_tools/spike_b1_baseline.py` |
| `fa_scan --capture-payload` flag | ✅ | commit `7603433` |
| Cron wrapper + auto git push | ✅ | `daily-advisor/cron_capture_payload.sh`, PR #165 |
| Case 1 fixture (#149 / 2026-05-04) | ✅ | hand-composed; gaps marked `_estimated` / null |
| Cases 2-21 fixture | ✅ | VPS daily cron 2026-05-07 → 2026-05-25 (21 days total) |
| Spike run (M1/M4 measurement) | ✅ | 7 cases (5-04 + 5-20~5-25), 56 calls, run 2026-05-26 13:45-14:08 |
| Baseline numbers + thresholds | ✅ | M1 -1σ = 0.036; M4 (any-pair) retired → M4' (top-pair) 42.9% with 75% trigger |
| HITL review | ✅ | 2026-05-26: chose Option A (M4 → M4' top-pair only; extend issue 003 + 007) |
| Issue 003 emitter extended | ✅ | `sp_p1_pair_borderline` + `fa_top1_pair_borderline` boolean fields |
| Issue 007 reader extended | ✅ | `p1_pair_borderline_rate` per breakdown + backward-compat for legacy bodies |

Raw spike output archived at `daily-advisor/_tools/fixtures/b1_baseline/spike_run_2026-05-26.json`.

## Pipeline overview

Per case (from one `<date>_sp_step1.json` + `<date>_fa_classify.json` fixture pair):

```
SP path:
  SP step1 (3 agents in parallel)  →  M1 SP = all 3 agree on P1
  SP step2 master (1 call)          →  M4 SP = master.borderline_pairs non-empty

FA path:
  FA classify (3 agents in parallel) →  per-FA verdicts (worth/borderline/not_worth)
  FA rank master (1 call)             →  M4 FA = master.borderline_pairs non-empty
                                         M1 FA = all 3 step1 classify master.top1 as 'worth'
```

Per-case cost: **8 claude -p calls** (4 SP + 4 FA). 7-case run ≈ **56 calls** against subscription rate limit.

### M1 / M4 metric definitions

| Metric | Definition | Source |
|--------|------------|--------|
| **M1 SP** | Boolean: 3 step1 agents return identical `ranking[0]` (P1 candidate). | `consensus_check_key(step1_results, ["ranking", 0])` |
| **M4 SP** | Boolean: master step2 emits non-empty `borderline_pairs` (master self-judges raw signal conflict per H3). | `master.parsed["borderline_pairs"]` |
| **M1 FA** | Boolean: all 3 step1 classify agents independently assigned master's `ranked_top[0]` candidate the verdict `"worth"` (= consensus on the eventual winner). | Cross-reference master output against per-agent classifications. |
| **M4 FA** | Boolean: master step2 (`fa_step2_rank`) emits non-empty `borderline_pairs`. | `fa_master.parsed["borderline_pairs"]` |

## Fixture inventory

| Date | SP fixture | FA fixture | Provenance | Notes |
|------|-----------|-----------|------------|-------|
| 2026-05-04 | ✅ `2026-05-04_sp_step1.json` | ✅ `2026-05-04_fa_classify.json` | Hand-composed from #149 issue body | Sparse (5-slot raw mostly null for non-cited fields); `_estimated` flagged |
| 2026-05-07 | ✅ `2026-05-07_sp_step1.json` | ✅ `2026-05-07_fa_classify.json` | VPS manual trigger via wrapper | Full real capture; 4 SP candidates / 8 FA / anchor "Cole Ragans" |
| 2026-05-08 | ⏳ | ⏳ | VPS daily cron | First scheduled capture |
| 2026-05-09 | ⏳ | ⏳ | VPS daily cron | |
| 2026-05-10 | ⏳ | ⏳ | VPS daily cron | |
| 2026-05-11 | ⏳ | ⏳ | VPS daily cron | |
| 2026-05-12 | ⏳ | ⏳ | VPS daily cron | (target 7 cases total) |

> #149 reconstruction is the only "known anchor failure" anchor case. Other 6 are random daily snapshots — natural distribution should mix high-consensus and dispute cases.

## Baseline results

### Per-case raw (2026-05-26 spike)

| Date | M1 SP | SP master P1 | M4 SP | SP borderline pairs | FA master top1 | M1 FA | M4 FA | FA borderline pairs |
|------|:---:|---|:---:|---|---|:---:|:---:|---|
| 2026-05-04 | ✅ | Cole Ragans | ✅ | P2-P3 | Casey Mize | ✅ | ✅ | top2-top3 |
| 2026-05-20 | ✅ | Keider Montero | ✅ | P2-P3 | Ben Brown | ❌ | ✅ | top1-top2 |
| 2026-05-21 | ✅ | Luis Severino | ✅ | P3-P4 | Ben Brown | ❌ | ✅ | top2-top3 |
| 2026-05-22 | ❌ | Keider Montero | ✅ | P1-P2, P3-P4 | Janson Junk | ✅ | ✅ | top1-top2, top2-top3 |
| 2026-05-23 | ❌ | Keider Montero | ✅ | P1-P2 | Janson Junk | ❌ | ✅ | top2-top3 |
| 2026-05-24 | ✅ | Keider Montero | ✅ | P2-P3 | Grant Holmes | ✅ | ✅ | top2-top3 |
| 2026-05-25 | ❌ | Luis Severino | ✅ | P1-P2 | Grant Holmes | ❌ | ✅ | top1-top2 |

### Aggregate (N=7)

| Path | Metric | Mean | Std | -1σ threshold | Notes |
|------|--------|:---:|:---:|:---:|---|
| SP | M1 P1 match | **0.571** | 0.535 | 0.036 | 4/7 cases — three-agent P1 agreement |
| SP | M4 master borderline (any pair) | **1.000** | 0.000 | – | 7/7 — original definition saturated, see below |
| **SP** | **M4' top1-pair borderline** | **0.429** | 0.535 | -0.106 | **3/7 — refined: master flags P1-P2 specifically** |
| FA | M1 top1 unanimous worth | **0.429** | 0.535 | -0.106 | 3/7 — three agents all rated master's top1 as `worth` |
| FA | M4 master borderline (any pair) | **1.000** | 0.000 | – | 7/7 — same saturation as SP |
| **FA** | **M4' top1-pair borderline** | **0.429** | 0.535 | -0.106 | **3/7 — refined: master flags top1-top2 specifically** |

### Interpretation

- **M1 SP 57.1%** — three step1 agents agree on P1 (the drop candidate) in 4 of 7 cases. The 3 mismatches were 5/22, 5/23, 5/25 — all involve the Severino-vs-Montero borderline (both are weak SP my-team candidates that swap depending on whether each agent weights season Sum vs 21d trend vs recent IP).
- **M4 SP 100% saturated** — master always surfaces ≥1 borderline pair, but in 5/7 cases the flagged pair is on P2-P3 or P3-P4 (not the actionable P1-P2). This means the "M4 >75% → 撤退" rule from PRD is unusable — baseline already exceeds it.
- **M4' SP top1-pair borderline 42.9%** — refined to count only borderline_pairs that include P1-P2. This is the *actionable* dissent signal (master uncertain about who to drop). 3/7 = 42.9% matches M1 SP mismatch rate (57.1% match ≈ 42.9% disagreement), confirming consistent surfacing.
- **M1 FA 42.9%** — three classify agents unanimously call master's top1 `worth` in 3 of 7 cases. The 4 dissents reflect "master picks top1 but ≥1 agent had it borderline/not_worth" — design-intent dissent surfacing.
- **M4 FA 100% saturated** — same pattern as SP; refined M4' = 42.9% on top1-top2 borderline.

**Key finding**: M4 as originally defined (`borderline_pairs non-empty`) is too coarse — master flags some borderline almost every run. The *meaningful* M4 metric is **M4' = top1-pair borderline triggered**, which lands at ~43%.

## Retreat thresholds (2026-05-26 revised after baseline)

Per `docs/sp-b1-cutover-design.md` §4 + PRD §"Further Notes". Numeric thresholds revised after spike showed M4 (any-pair) baseline saturated at 100%.

| Trigger | Condition | Action |
|---------|-----------|--------|
| **G1 — M1 collapse** | M1 SP weekly rate < **0.036** (baseline -1σ) for **2 consecutive weeks** | Switch to single-LLM SP path (G-pre2 fallback). Ranking + final action condensed into one `prompt_phase6_sp_single.txt` call. |
| **G1 alt — M4' top1-pair over-trigger** | M4' SP weekly rate > **75%** (top1-pair borderline) for **2 consecutive weeks** | Same as above — master flagging P1-P2 specifically >75% of weeks indicates raw payload itself is ambiguous on the actionable pair. |

> **Original M4 (any-pair) rule retired**: baseline saturated at 100% (master flags ≥1 pair every run, usually P2-P3 / P3-P4). Replaced by M4' (top1-pair only). Implementation note: metrics emitter still records both `sp_review_triggered` (any) and a new `sp_p1_pair_borderline` boolean (specifically P1-P2 flagged) — issue 003 emit_metric_block + issue 007 reader CLI need a small extension to surface M4' separately.
>
> **M1 -1σ threshold = 0.036**: this is mathematically a very low floor (3.6%). It means M1 has to essentially collapse to near-zero to trigger. The high std (0.535) on n=7 binary outcomes produces this wide CI. Acceptable for initial cutover; revisit after observation period accumulates more samples (consider switching to bootstrap CI or fixed-floor rule like "M1 < 20% for 2 weeks").
>
> **Do not deploy `prompt_phase6_sp_single.txt` until trigger fires** (per F1: lazy fallback authoring — observation period 1-3 weeks may not need it).

### G-pre2 fallback startup SOP (when triggered)

1. Confirm trigger condition met (2 consecutive weeks data via `gh api` metric reader once issue 007 lands; manually until then).
2. Open new branch `fix/g-pre2-sp-fallback`.
3. Author `prompt_phase6_sp_single.txt` (single-call: input = anchor + FA pool + raw + percentile + 14d trad + %owned; output = `drop_X_add_Y` / `watch` / `pass` directly).
4. Add `fallback_mode` flag to `_phase6_sp.process_sp_v4`; when true, dispatcher skips 8-step pipeline and runs single prompt.
5. Switch the flag (config or env). Cron unchanged.
6. Continue measuring M1/M4 dummy values (= 1.0/0.0, since single-call has no multi-agent dynamics) so dashboard still emits records.
7. After 2 stable weeks on fallback, evaluate whether to keep multi-agent pipeline at all or remove permanently.

## Known limitations

- **Sparse #149 fixture**: rationale-derived raw values only; many 5-slot percentiles null. Spike P1 match on this case may overstate consensus (LLMs may converge on Ragans regardless because his cited weakness signals are stark — but also may diverge if missing fields produce hedging). Treat #149 result as anchor reference, not aggregate-defining.
- **FA fixture pool size mismatch**: #149 production had 12 FA; reconstruction kept 4 (Mize/McCullers/Lambert/Fedde). Smaller pool may inflate consensus if borderline candidates dropped from reconstruction were the disagreement source.
- **Subscription rate limit**: 56 calls in one run. Spread spike across 2-3 sessions if rate-limit guards trip.
- **Spike vs production disagreement (2026-05-26 observed)**: production daily issues 5/20-5/26 report SP `p1_match` rate 7/7 = 100%, but the spike (same date range, captured payload) shows only 3/6 ≈ 50%. B1 prompts (issues 005/006) were committed 2026-05-07 so both should run on B1 layer. Possible causes to investigate post-cutover: (a) captured payload subtly differs from what production actually sent to `claude -p` (e.g., date interpolation, ordering); (b) production cron LLM seeded differently than spike's parallel runs. Not blocking cutover — flag for week-1 observation period.

## Reproducing the spike

```bash
cd daily-advisor
python3 _tools/spike_b1_baseline.py \
    --fixture-dir _tools/fixtures/b1_baseline \
    --dry-run                                  # preview cases + call count
python3 _tools/spike_b1_baseline.py \
    --fixture-dir _tools/fixtures/b1_baseline > spike_b1_baseline_results.json 2> spike_b1_baseline_stats.txt
```

Per-case JSON in stdout; aggregate stats to stderr (also at top of `--baseline` key in stdout JSON).

## Decision log

- **2026-05-07** Issue 008 kicked off. Fixture source = `--capture-payload` flag (not hand-compose all 7). #149 hand-compose with marked gaps as required spike anchor.
- **2026-05-07** M4 measured (extended spike beyond multi_agent_spike step1-only). Both SP and FA paths included per acceptance.
- **2026-05-07** Cases = 7 (issue 008 acceptance: 5-10 case + #149).
- **2026-05-08 → 2026-05-25** VPS daily cron auto-captured 19 additional fixture days (21 total available).
- **2026-05-26** Spike run executed on 7 selected cases (5-04 + 5-20~5-25). 56 calls, ~23 min wall time.
- **2026-05-26** M4 (any-pair) baseline = 100% saturated → original "M4 >75% → 撤退" rule retired. Refined to M4' (top1-pair borderline) = 42.9% baseline. M1 SP baseline = 57.1%, -1σ = 0.036.
- **2026-05-26** Pending HITL: user reviews revised threshold rules + signs off before issue 009 cutover. Issue 003 + 007 need minor extension to emit/read M4' (top1-pair) separately from M4 (any-pair).
