## Problem

今天 `/stream-sp-deep` 跑 3 位 SP 深評時遇到三個痛點：

1. 手動目視判斷 24 場 game log 是否 Quality Start — MLB API 不附 QS 欄位，且 IP 字串 "5.2" 表示 5⅔ 局（不是 5.2），邊界值容易看走眼，QS rate 計算可能出錯。
2. 拉對手 vs 慣用手 split 時要先記得 SP 是右投或左投才能填對 API 參數。今天 3 位都是 RHP 我靠記憶填，遇到不熟的 SP 會多一次 lookup。
3. Game log 跟 opponent trend 是兩次獨立 SSH call，加上一次 inline Python heredoc 寫法踩到 shell quoting bug — 雖然 30 秒復原，但這個失敗模式只要繼續用 inline heredoc 就會再發生。

## Solution

新增一個 `daily-advisor/mlb_query.py` helper，**只暴露兩個函式**：

- `gamelog_with_qs(mlb_id, season)` — 回 game log，每場附 `ip_decimal` (float) 跟 `qs` (bool)
- `opponent_context(team_id, end_date, sp_id)` — 一次回 7d/14d/30d 三窗口趨勢 + vs SP 慣用手 season split。SP 慣用手在函式內部從 sp_id 查 pitchHand，caller 不必傳

`/stream-sp-deep` Step 1+2 改成呼叫這兩個函式，inline Python heredoc 整段移除。

## User Stories

1. As an AI session running deep streaming-SP evaluation, I want gamelog entries to include a Quality Start boolean, so that I can count QS rate via boolean count instead of visually inspecting 20+ rows per evaluation.

2. As an AI session computing innings-per-start averages, I want each gamelog entry to include innings as a true decimal value, so that "5.2" is treated as 5.667 and downstream arithmetic does not silently misread the format.

3. As an AI session evaluating an SP against a specific opponent, I want opponent batting trends across 7-day, 14-day, and 30-day windows returned in one call, so that I can detect trend direction without authoring three separate range queries.

4. As an AI session, I want the opponent context call to resolve SP handedness internally and select the correct vs-RHP or vs-LHP split, so that I do not need to know or pass the pitcher's hand.

5. As a Fantasy Baseball manager, I want Quality Start counts in deep evaluation reports to be computed mechanically, so that decisions based on QS rate patterns are not compromised by misreading "5.2" innings as if it were a Quality Start qualifier.

## Implementation Decisions

- The helper is a single Python file added under the daily-advisor directory, following the conventions of the existing scripts in that directory.

- The innings-string parser is a pure function. It maps the "I.frac" MLB format to a float by treating the fractional part as thirds.

- The Quality Start derivation is a pure function over decimal innings and earned runs. It returns true when innings is at least 6 and earned runs is at most 3.

- The gamelog helper fetches the player's pitching gameLog for the given season, enriches each appearance with the decimal innings and Quality Start fields, and returns a list. All other API fields pass through unchanged.

- The opponent context helper first fetches player metadata to determine pitching handedness. It then fetches three rolling windows ending at the given date plus the season split versus that handedness. The response is a single dict containing each window's stats plus the split, keyed by labels.

- The /stream-sp-deep skill markdown is rewritten so that the previous Step 1 inline Python and Step 2 inline Python are replaced by two helper invocations. The skill no longer contains heredoc Python.

## Testing Decisions

- Innings parsing and Quality Start derivation are unit-tested as pure functions. Boundary cases include "0.0", "5.0", "5.2", "6.0", "7.1" for innings parsing, and (innings 6.0 with earned runs 3) plus (innings 5.2 with earned runs 0) for the Quality Start boundary.

- Network-dependent helpers are not unit-tested. They are validated by a single end-to-end run on the VPS against today's three SP candidates (the ones used in the prior session's deep evaluation), comparing the new helper output to the numerical findings already produced. A divergence is a regression signal.

- Prior art: the existing test suite for the stream-sp scan CLI in the same project uses dependency injection for fetchers and unit-tests the pure helpers plus orchestrator shape, while leaving live API paths to end-to-end validation. The new helper follows the same pattern.

## Out of Scope

- Batch mode that bundles multiple (SP, opponent) tuples into one call. Deferred — current daily volume (3 candidates) does not justify the abstraction, and serial calls cost on the order of seconds.

- A standalone player-search subcommand. Deferred — upstream skills already resolve names to MLB identifiers, so no current caller needs name-to-id lookup.

- An argparse-driven multi-subcommand CLI with JSON stdout and pretty-print modes. Deferred — the two helpers are imported as Python functions, which is sufficient for current callers. CLI surface is added only when a non-Python caller appears.

- Retry and backoff framework for transient API failures. Deferred — the MLB Stats API has been reliable for current workload, and adding retry logic without an observed failure is premature.

- Refactoring other skills (the main streaming-SP scan, waiver scan, player evaluation) to consume these helpers. The new code is available to them but not mandated.

- Caching of MLB Stats API responses.

- Documentation warnings (in skill markdown or project memory) about the SSH heredoc quoting failure mode. Reviewed and rejected — the failure mode is eliminated at the tool level by removing inline heredoc from the skill; additional warnings are redundant.

## Further Notes

- An earlier version of this PRD scoped a five-subcommand CLI with batch mode, player search, retry framework, pretty-print output, and 22 user stories. Three independent reviews flagged the expanded scope as speculative: three of five subcommands had no current caller, the latency target (60 seconds down to 20-30 seconds) was tooling vanity for a once-daily workflow, and the in-flight B1 cutover and emerging-batter skill work has higher priority. The PRD was rewritten to target only the actual pain points observed today.

- If a second caller genuinely needs batch behavior, name-to-id lookup, or a CLI surface, revisit the scope at that point. The deferred items above are not rejected on principle, only on current evidence.
