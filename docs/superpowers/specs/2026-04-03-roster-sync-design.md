# roster_sync.py Design Spec

## Goal

Automatically sync Yahoo Fantasy roster to `roster_config.json` after daily waiver processing (TW 15:10). Eliminates manual config editing after add/drop, preventing mlb_id=None and stale data bugs.

## Execution Modes

### `--init` (manual, one-time)

Pull full roster from Yahoo API, build config from scratch for all players:
- Query Yahoo roster → extract name, team, positions, yahoo_player_key
- For each player: query mlb_id (MLB API) + prior_stats (2025 Savant CSV + MLB Stats API)
- Write to roster_config.json (preserves `teams` and `league` sections)

### Daily cron (TW 15:10 = UTC 07:10)

1. `GET /league/{league_key}/transactions;team_key={my_key}` — our team's transactions
2. Filter: any transaction with `timestamp > last_sync_timestamp`
3. No new transactions → log "No changes" → exit
4. Has new transactions → `GET /team/{team_key}/roster` (full roster)
5. Compare Yahoo roster vs config using `yahoo_player_key` → identify added/dropped players
6. Dropped players: remove from config
7. Added players:
   - `yahoo_player_key`: from Yahoo roster data (each player has `player_key`)
   - `mlb_id`: MLB API `people/search?names={name}` (verify: Jr., accents)
   - `prior_stats`: 2025 Savant CSV + MLB Stats API (one-time, computed and stored)
   - `positions`: Yahoo `display_position`, split to array
   - `team`: Yahoo `editorial_team_abbr`
8. Write updated roster_config.json + update `last_sync_timestamp`
9. `git commit -m "roster: +{added} -{dropped}" && git push`
10. Telegram notification: `[Roster Sync] +Walker(STL) -Kwan(CLE)`

### `--dry-run` (optional flag)

Same as daily mode but: prints diff without writing config, no git commit, no Telegram.

## Yahoo Transactions API — Verified Behavior

Tested 2026-04-03 against live API:

```
GET /league/{league_key}/transactions;team_key={my_key}
```

| Capability | Status |
|------------|--------|
| `;team_key=` filter | ✅ Returns only our team's transactions |
| `;type=add,drop` filter | ❌ Changes response format (list vs dict), unreliable |
| Date filter | ❌ Not supported, returns all history |
| Response structure | ✅ Clear: `timestamp`, `type`, `status`, players with `transaction_data` |

**Key finding**: Transaction player list only shows the `add` side, not the `drop` side. Therefore the actual roster diff must come from comparing full roster vs config. Transactions API is only used as a **gate** (any new activity? yes/no) to avoid unnecessary full roster fetch.

### Response structure (verified)

```
transaction[0] = {transaction_key, transaction_id, type, status, timestamp}
transaction[1] = {players: {0: {player: [[{player_key}, {name}, ...], {transaction_data}]}, count: N}}
transaction_data = [{type: "add", source_type: "freeagents", destination_type: "team", destination_team_key: "..."}]
```

### Change detection logic

Store `last_sync_timestamp` in a local file (`daily-advisor/.last_sync`). Compare against transaction timestamps to detect new activity. This avoids needing date filter support.

## Config Schema Changes

### New fields per player

```json
{
  "name": "Jordan Walker",
  "mlb_id": 691023,
  "yahoo_player_key": "469.p.12345",
  "team": "STL",
  "positions": ["LF", "RF"],
  "prior_stats": {
    "season": 2025,
    "xwoba": 0.297,
    "bb_pct": 7.8,
    "barrel_pct": 7.8,
    "hh_pct": 40.4,
    "ops": 0.750,
    "pa_per_team_g": 3.2,
    "pa": 520,
    "g": 140
  }
}
```

### prior_stats by player type

**Batters:**
- `season`, `xwoba`, `bb_pct`, `barrel_pct`, `hh_pct`, `ops` (quality)
- `pa_per_team_g` (volume: PA ÷ team games played)
- `pa`, `g` (sample size)

Note: `pa_per_team_g` requires team games played, fetched from MLB Stats API `/teams/{team_id}/stats?stats=season&season=2025&group=hitting` or calculated from schedule. Not currently in codebase — new code needed.

**SP:**
- `season`, `xera`, `xwoba_allowed`, `hh_pct_allowed`, `barrel_pct_allowed`, `era` (quality)
- `ip_per_gs` (volume: IP ÷ GS, from MLB Stats API season stats — `gamesStarted` field needs new parsing)
- `ip`, `bbe` (sample size)

**RP:**
- `season`, `xera`, `xwoba_allowed`, `hh_pct_allowed`, `barrel_pct_allowed`, `era` (quality)
- `k_per_9`, `ip_per_team_g` (volume — `strikeOuts` and `inningsPitched` need new parsing)
- `ip`, `bbe` (sample size)

### Unchanged sections

`teams` and `league` are not touched by roster_sync.

## Diff Logic

Compare using `yahoo_player_key` (not player name) to avoid Jr./accent mismatches:
- Build set of yahoo_player_keys from Yahoo roster response
- Build set of yahoo_player_keys from current config
- Added = in Yahoo but not in config
- Dropped = in config but not in Yahoo

For `--init` mode (config has no yahoo_player_key yet): match by player name as bootstrap, then store yahoo_player_key for future diffs.

## Data Sources

| Data | Source | When |
|------|--------|------|
| Roster (names, positions, team) | Yahoo API `/team/{key}/roster` | Each sync |
| Transactions gate | Yahoo API `/league/{key}/transactions;team_key={my_key}` | Each daily run |
| yahoo_player_key | Yahoo API roster response (`player_key` field) | Each sync |
| mlb_id | MLB API `/people/search?names={name}` | New player only |
| prior_stats (Statcast) | Baseball Savant CSV (`type=batter` / `type=pitcher`, year=2025) | New player only |
| prior_stats (traditional) | MLB Stats API `/people/{id}/stats?stats=season&season=2025` | New player only |
| Team games played (for pa_per_team_g) | MLB Stats API `/teams/{id}?season=2025` or schedule | New batter only |

## Code Architecture

### Imports from existing modules

From `yahoo_query.py`:
- `refresh_token(env)` → Yahoo OAuth token refresh
- `api_get(path, access_token)` → Yahoo API calls (**Yahoo only**, base URL = `YAHOO_API`)
- `load_env()` → env loading
- `is_pitcher(player)`, `pitcher_type(player)` → position classification

**Not imported from main.py** — MLB Stats API and Savant CSV functions in main.py have different signatures and are coupled to the report generation context. roster_sync defines its own:

### New functions in roster_sync.py

| Function | Purpose |
|----------|---------|
| `mlb_api_get(path)` | MLB Stats API GET (no auth needed), separate from Yahoo `api_get` |
| `find_my_team_key(league_key, token)` | Find our team_key from `/league/{key}/teams` |
| `fetch_transactions(league_key, my_key, token)` | Get our team's transactions, return list of `{timestamp, type, players}` |
| `has_new_transactions(transactions, last_sync_ts)` | Check if any transaction is newer than last sync |
| `fetch_full_roster(team_key, token)` | Parse Yahoo roster → list of `{name, yahoo_player_key, team, positions}` |
| `diff_roster(yahoo_roster, config)` | Compare by yahoo_player_key → `{added: [], dropped: []}` |
| `search_mlb_id(name)` | MLB API people search, handle Jr./accents |
| `fetch_prior_stats_batter(mlb_id)` | 2025 Savant CSV + MLB Stats API → prior_stats dict |
| `fetch_prior_stats_pitcher(mlb_id, p_type)` | Same for SP/RP |
| `fetch_savant_player(mlb_id, year, player_type)` | Single-player Savant CSV lookup |
| `update_config(config, added, dropped)` | Merge changes into config dict |
| `save_config(config)` | Write JSON with consistent formatting |
| `git_commit_and_push(added, dropped)` | git add + commit + pull --rebase + push |
| `send_telegram(message, env)` | Notification |

### State file

`daily-advisor/.last_sync` — single line containing Unix timestamp of last successful sync. Created by `--init`, updated after each successful daily sync. `.gitignore`d (VPS-local state).

## Error Handling

| Error | Action |
|-------|--------|
| Yahoo API failure | Log error, exit without changing config. Retry next day. |
| MLB API can't find mlb_id | Set `"mlb_id": null`, Telegram warning. Manual fix needed for Statcast. |
| Savant has no 2025 data for player | Set `"prior_stats": null`. Common for rookies. |
| Transaction API format unexpected | Log full response, exit without changing config. |
| Git push fails | Log error, config is updated locally. Manual push needed. |
| Name matching edge cases (Jr., accents) | `search_mlb_id` strips suffixes, normalizes Unicode before search. If no match, try last-name-only search as fallback. |

## Cron Setup

Add to `/etc/cron.d/daily-advisor`:
```
# Roster Sync — TW 15:10 = UTC 07:10
10 7 * * * root export $(cat /etc/calorie-bot/op-token.env) && GH_TOKEN=$(op item get "GitHub PAT - Claude Code" --vault Developer --fields credential --reveal) PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin bash -c "cd /opt/mlb-fantasy && python3 daily-advisor/roster_sync.py >> /var/log/roster-sync.log 2>&1"
```

## Pre-implementation Verification

Before implementing `search_mlb_id()`, manually test MLB API with edge cases:
- `Jazz Chisholm Jr.` (Jr. suffix)
- `José Altuve` or similar (accent characters)
- A recently called-up player (may not be in search index immediately)

## File

`daily-advisor/roster_sync.py` — standalone script, estimated ~250-350 lines.
