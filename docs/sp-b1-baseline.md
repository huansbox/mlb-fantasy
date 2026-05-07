# SP B1 Cutover — Baseline Spike Results

> Issue: `issues/008-spike-fixture-baseline.md` · PRD: `issues/prd.md` · Design: `docs/sp-b1-cutover-design.md`

## Status

🟡 **In progress (2026-05-07)** — infra + #149 fixture ready; capture cron pending; awaiting 6-day fixture accumulation before final spike run.

| Phase | Status | Notes |
|-------|--------|-------|
| Spike runner extended (SP step1 + step2 + FA classify + rank) | ✅ | `daily-advisor/_tools/spike_b1_baseline.py` |
| `fa_scan --capture-payload` flag | ✅ | commit `7603433` |
| Case 1 fixture (#149 / 2026-05-04) | ✅ | hand-composed; gaps marked `_estimated` / null |
| Cases 2-7 fixture | ⏳ | VPS daily capture from 2026-05-08 onwards |
| Spike run (M1/M4 measurement) | ⏳ | Trigger after 7 cases |
| Baseline numbers + thresholds | ⏳ | Mean / std / -1σ |
| HITL review | ⏳ | User confirms baseline reasonable before issue 009 cutover |

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
| 2026-05-08 | ⏳ | ⏳ | VPS capture | First daily fixture after VPS deploy |
| 2026-05-09 | ⏳ | ⏳ | VPS capture | |
| 2026-05-10 | ⏳ | ⏳ | VPS capture | |
| 2026-05-11 | ⏳ | ⏳ | VPS capture | |
| 2026-05-12 | ⏳ | ⏳ | VPS capture | |
| 2026-05-13 | ⏳ | ⏳ | VPS capture | (target 7 cases total) |

> #149 reconstruction is the only "known anchor failure" anchor case. Other 6 are random daily snapshots — natural distribution should mix high-consensus and dispute cases.

## Baseline results

### Per-case raw

⏳ Will populate after spike run. Format:

| Date | M1 SP | SP master P1 | M4 SP | FA master top1 | M1 FA | M4 FA |
|------|:---:|---|:---:|---|:---:|:---:|
| 2026-05-04 | – | – | – | – | – | – |
| ... | | | | | | |

### Aggregate

⏳ Mean / std across N=7. Format:

| Path | Metric | Mean | Std | -1σ threshold |
|------|--------|:---:|:---:|:---:|
| SP | M1 P1 match | – | – | – |
| SP | M4 master borderline | – | – | – |
| FA | M1 top1 unanimous worth | – | – | – |
| FA | M4 master borderline | – | – | – |

## Retreat thresholds (set after baseline)

Per `docs/sp-b1-cutover-design.md` §4 + PRD §"Further Notes":

| Trigger | Condition | Action |
|---------|-----------|--------|
| **G1 — M1 collapse** | M1 SP weekly rate < (baseline -1σ) for **2 consecutive weeks** | Switch to single-LLM SP path (G-pre2 fallback). Ranking + final action condensed into one `prompt_phase6_sp_single.txt` call. |
| **G1 alt — M4 over-trigger** | M4 SP weekly rate > **75%** for **2 consecutive weeks** | Same as above — master self-marking borderline >75% of weeks indicates raw payload itself is ambiguous. |

> Numeric -1σ thresholds will be filled in after spike run. **Do not deploy `prompt_phase6_sp_single.txt` until trigger fires** (per F1: lazy fallback authoring — observation period 1-3 weeks may not need it).

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
