// PreToolUse hook（mlb-fantasy 專案專屬）：擋本機跑會 call Yahoo API 的腳本。
//
// 背景：Yahoo OAuth refresh_token 同時只有一份有效。本機跑會 refresh + rotate
// access_token，VPS 的舊 token 失效 → cron (fa_scan / daily_advisor / roster_sync
// / savant_rolling) 全部中斷直到手動同步。CLAUDE.md「執行環境」段已寫「所有腳本
// 跑在 VPS」「不要本機跑 Yahoo」，本 hook 把規則機械化執行。
//
// 攔截條件：
//   - tool_name 是 Bash 或 PowerShell
//   - command 內出現任一 Yahoo-touching .py basename（見 YAHOO_SCRIPTS）
//   - 且 sub-command **不**含放行訊號（vps-run.sh / ssh / scp / pytest / -m pytest）
//
// 放行條件（任一即可）：
//   - bash bin/vps-run.sh '<cmd>'（VPS 端跑，token 在 VPS）
//   - ssh root@... <cmd> / scp ...（純 SSH/SCP 工具）
//   - uv run pytest / uv run python -m pytest（測試走 mock fetchers）
//   - git 開頭的 sub-command（git add/log/diff -- <裸路徑> 只是版控操作，
//     不會執行腳本 — issue #407 item 5 誤擋修正）
//
// 跨平台：Bash 走 stripHeredocs + stripQuotes（沿用 block-bare-python 邏輯），
// PowerShell 走簡化版（PS 字面量規則不同但本 hook 不需精確 — Yahoo .py 名出現
// 在 PS commit message 內機率極低；偽陽性可接受，false negative 才致命）。

import { readFileSync } from "node:fs";

const YAHOO_SCRIPTS = new Set([
  "yahoo_query.py",
  "daily_advisor.py",
  "fa_scan.py",
  "emerging_batter_scan.py",
  "stream_sp_scan.py",
  "rp_svh_scan.py",
  "roster_sync.py",
  "roster_stats.py",
  "weekly_review.py",
  "_trade_lookup.py",
  "_trade_batter_rank.py",
]);

// Wrapper / VPS-bound tokens that mean the .py won't actually run locally.
const ALLOWLIST_TOKENS = new Set([
  "vps-run.sh",
  "ssh",
  "scp",
  "rsync",
  "pytest",
]);

let input;
try {
  input = JSON.parse(readFileSync(0, "utf8"));
} catch {
  process.exit(0);
}

const tool = input?.tool_name;
if (tool !== "Bash" && tool !== "PowerShell") process.exit(0);

const command = input?.tool_input?.command;
if (typeof command !== "string" || command.trim() === "") process.exit(0);

// ── Strip heredoc bodies + quoted strings so commit messages / file content
// containing "stream_sp_scan.py" don't trigger the block.
function stripHeredocs(text) {
  const lines = text.split("\n");
  const kept = [];
  for (let i = 0; i < lines.length; i++) {
    kept.push(lines[i]);
    const delims = [...lines[i].matchAll(/<<-?\s*(['"]?)(\w+)\1/g)].map((m) => m[2]);
    for (const delim of delims) {
      i++;
      while (i < lines.length && lines[i].trim() !== delim) i++;
    }
  }
  return kept.join("\n");
}

function stripQuotes(text) {
  return text
    .replace(/'[^']*'/g, " ")
    .replace(/"(?:[^"\\]|\\.)*"/g, " ");
}

const cleaned = stripQuotes(stripHeredocs(command));
const subCommands = cleaned.split(/&&|\|\||[;\n|]/);

function basename(token) {
  return token.replace(/^.*[/\\]/, "");
}

function hasAllowlistedToken(tokens) {
  for (const t of tokens) {
    const b = basename(t);
    if (ALLOWLIST_TOKENS.has(b)) return true;
    // `python -m pytest` shape — match the `-m pytest` pair
    if (t === "-m") continue;
  }
  // Detect `-m pytest` pair
  for (let i = 0; i < tokens.length - 1; i++) {
    if (tokens[i] === "-m" && tokens[i + 1] === "pytest") return true;
  }
  return false;
}

let offender = null;
for (const raw of subCommands) {
  const tokens = raw.trim().replace(/^[({\s]+/, "").split(/\s+/).filter(Boolean);
  if (tokens.length === 0) continue;
  if (basename(tokens[0]) === "git") continue; // git 不會執行腳本（#407 item 5）
  if (hasAllowlistedToken(tokens)) continue;
  for (const t of tokens) {
    if (YAHOO_SCRIPTS.has(basename(t))) {
      offender = basename(t);
      break;
    }
  }
  if (offender) break;
}

if (!offender) process.exit(0);

process.stderr.write(
  `[block-local-yahoo] 偵測到本機要跑 \`${offender}\` — 這支腳本會 call Yahoo API 並 refresh OAuth token，會讓 VPS 端 token 失效 → cron (fa_scan / daily_advisor / roster_sync) 全部中斷。\n\n` +
  `規範（CLAUDE.md「執行環境」段）：所有 Yahoo-touching 腳本只能在 VPS 跑。\n\n` +
  `改用：\n` +
  `  • VPS 跑：bash bin/vps-run.sh 'cd /opt/mlb-fantasy/daily-advisor && python3 ${offender} <args>'\n` +
  `  • 本機只在 Yahoo 邏輯 mock 過的 tests 跑：uv run python -m pytest tests/<test_file>.py\n\n` +
  `若真的要本機跑（debug / one-off），明確跟用戶確認後從 settings.json 暫時拿掉本 hook，跑完務必 scp token 回 VPS 同步。`
);
process.exit(2);
