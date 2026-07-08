"""One-off paired A/B runner for 318b B6 SP payload injection (段③).

Methodology per docs/318b-injection-design.md 三段 A/B 量測契約 + lever-2 lesson:
same candidates, same model, neutral cwd; judge by output_tokens + input delta,
never by visible text alone. Mirrors _ab_028_runner (段①) for SP's 2-step path.

B (injected) = the 2026-07-08 production capture fixture (first injected SP
payload after B6 deploy). A (clean) = the SAME candidates with the B6 fields
stripped (de-injection), so candidate-pool noise is zero. Both run through the
UNCHANGED Step A / Step B prompts.

De-injection strips exactly what payload_slimmer._inject_318b + _rolling_payload
add: ledger_note / next_week_starts / velo / kbb_small_sample / swap_vs_incumbent
fields, rolling_21d.csw_pct + .pitches, and velo-prefix tags (⚠️ 球速下滑 / ✅
球速上升, whitelisted only by B6). Step B keeps its embedded (injected) step_a
result unchanged — a constant across inj/clean, so the pool-injection delta stays
isolated.

Usage (VPS only — claude runs there):
    cd /opt/mlb-fantasy/daily-advisor && REPS=2 python3 _tools/_ab_318b_sp_runner.py
Prompt goes via stdin (Windows argv caps at ~32K; VPS Linux is fine either way).
Raw claude JSON dumped to $TMPDIR/ab_318b_sp/ for audit; summary to stdout.
Throwaway tool — the A/B result lands in the design doc's 段③ section.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent        # daily-advisor/_tools/
DA = HERE.parent                              # daily-advisor/
FIX = HERE / "fixtures" / "b1_baseline"
DATE = "2026-07-08"
SEP = "\n\n---\n\n"
REPS = int(os.environ.get("REPS", "2"))

_VELO_PREFIX = ("⚠️ 球速下滑", "✅ 球速上升")
_INJ_KEYS = ["ledger_note", "next_week_starts", "velo",
             "kbb_small_sample", "swap_vs_incumbent"]


def deinject(payload: dict) -> dict:
    """Return a deep copy with every B6 injection field removed."""
    d = copy.deepcopy(payload)
    for pool in ("candidates", "fa_candidates"):
        for e in d.get(pool, []) or []:
            for k in _INJ_KEYS:
                e.pop(k, None)
            r = e.get("rolling_21d")
            if isinstance(r, dict):
                r.pop("csw_pct", None)
                r.pop("pitches", None)
            for tk in ("add_tags", "warn_tags"):
                if isinstance(e.get(tk), list):
                    e[tk] = [t for t in e[tk] if not t.startswith(_VELO_PREFIX)]
    return d


def build_full(step: str, payload: dict) -> str:
    prompt = (DA / f"prompt_sp_b2_{step}.txt").read_text(encoding="utf-8")
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return prompt + SEP + body


def run_claude(full: str, neutral: str) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found in PATH")
    result = subprocess.run(
        [exe, "-p", "--output-format", "json"],
        input=full, capture_output=True, text=True, encoding="utf-8",
        cwd=neutral, timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr[:500]}")
    return json.loads(result.stdout)


def total_input(usage: dict) -> int:
    return ((usage.get("input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0))


def main() -> int:
    out_dir = Path(tempfile.gettempdir()) / "ab_318b_sp"
    out_dir.mkdir(exist_ok=True)

    variants: dict[tuple[str, str], str] = {}
    char_len: dict[tuple[str, str], int] = {}
    for step in ("step_a", "step_b"):
        inj = json.loads((FIX / f"{DATE}_sp_b2_{step}.json").read_text(encoding="utf-8"))
        for kind, pay in (("clean", deinject(inj)), ("inj", inj)):
            full = build_full(step, pay)
            variants[(step, kind)] = full
            char_len[(step, kind)] = len(full)

    results: dict[tuple[str, str], list[dict]] = {}
    with tempfile.TemporaryDirectory() as neutral:
        for (step, kind), full in variants.items():
            for rep in range(REPS):
                print(f"[{step}/{kind} rep{rep}] claude -p ({len(full)} chars)...",
                      file=sys.stderr, flush=True)
                data = run_claude(full, neutral)
                (out_dir / f"{step}_{kind}_rep{rep}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                results.setdefault((step, kind), []).append(data)

    def usage(d):
        return d.get("usage") or {}

    print("\n================ 318b SP 段③ A/B ================")
    print(f"REPS={REPS}  fixture={DATE}  model="
          f"{results[('step_a','inj')][0].get('model', '?')}")
    print(f"\n{'variant':14} {'full_chars':>10} {'in_tok':>8} "
          f"{'out_tok (per rep)':>22} {'cost_usd (rep0)':>16}")
    for step in ("step_a", "step_b"):
        for kind in ("clean", "inj"):
            rs = results[(step, kind)]
            ins = [total_input(usage(d)) for d in rs]
            outs = [usage(d).get("output_tokens") for d in rs]
            cost0 = rs[0].get("total_cost_usd")
            in_show = ins[0] if len(set(ins)) == 1 else f"{min(ins)}-{max(ins)}"
            print(f"{step}/{kind:9} {char_len[(step, kind)]:>10} "
                  f"{str(in_show):>8} {str(outs):>22} {cost0}")

    print("\n---- injection delta (inj − clean) ----")
    tot_in_d = tot_out_d = 0
    for step in ("step_a", "step_b"):
        ci = total_input(usage(results[(step, "clean")][0]))
        ii = total_input(usage(results[(step, "inj")][0]))
        co = sum(usage(d).get("output_tokens") or 0 for d in results[(step, "clean")]) / REPS
        io = sum(usage(d).get("output_tokens") or 0 for d in results[(step, "inj")]) / REPS
        tot_in_d += ii - ci
        tot_out_d += io - co
        print(f"{step}: input {ci}->{ii} ({ii-ci:+d}, {100*(ii-ci)/ci:+.1f}%)  "
              f"output avg {co:.0f}->{io:.0f} ({io-co:+.0f}, {100*(io-co)/co:+.1f}%)")
    print(f"TOTAL A+B: input {tot_in_d:+d} tok   output avg {tot_out_d:+.0f} tok")
    print(f"\nraw responses: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
