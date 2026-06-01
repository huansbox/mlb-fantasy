// Build the scout page — every team's per-week opponent pitching+batting totals,
// each cell annotated with that week's league rank (#1 = best). Reads
// _scout_all.json, writes scout-site/index.html.
//
// Style: professional data-table (light paper bg, thin grey lines, black text,
// tabular-nums). Ranks shown as plain "#n" with only the top-3 lightly tinted
// blue (eye-friendly, colorblind-safe — no red/green, low saturation). The 星宿
// theme survives as the dark-green header banner + master/disciple badges.
// Run: node daily-advisor/_tools/build_scout_html.mjs
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const data = JSON.parse(fs.readFileSync(path.join(ROOT, 'daily-advisor/_tools/_scout_all.json'), 'utf8'));

const PIT = ['IP', 'W', 'K', 'ERA', 'WHIP', 'QS', 'SV+H'];
const BAT = ['R', 'HR', 'RBI', 'SB', 'BB', 'AVG', 'OPS'];

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

// Only the top-3 get a faint blue tint (deepest at #1). Everyone else: no tint.
function rankClass(rank) {
  if (rank === 1) return ' r1';
  if (rank === 2) return ' r2';
  if (rank === 3) return ' r3';
  return '';
}

function cellHtml(c) {
  if (!c || c.v === '' || c.v == null) return `<td class="empty">—</td>`;
  const rk = c.rank ? `<span class="rk">#${c.rank}</span>` : '';
  return `<td class="d${rankClass(c.rank)}"><span class="v">${esc(c.v)}</span>${rk}</td>`;
}

const md = (x) => x.slice(5).replace('-', '/');

function rowHtml(row, cats, kind) {
  const opp = row.opponent ?? '—';
  const prog = row.in_progress ? ' <em class="prog">進行中</em>' : '';
  const cells = cats.map((c) => cellHtml((row[kind] || {})[c])).join('');
  return `<tr><td class="wk"><span class="w">W${row.week}</span> ` +
         `<small>${md(row.dates[0])}–${md(row.dates[1])}</small>` +
         `<br><b>${esc(opp)}</b>${prog}</td>${cells}</tr>`;
}

function table(weeks, cats, kind, caption) {
  const head = `<tr><th class="wk">週 · 所遇之敵</th>${cats.map((c) => `<th>${c}</th>`).join('')}</tr>`;
  const body = weeks.map((r) => rowHtml(r, cats, kind)).join('');
  return `<div class="tbl-wrap"><div class="cap">${caption}</div><table>${head}${body}</table></div>`;
}

// 運氣分：對手各類別名次反推 (of+1-rank)，#1→12、#12→1。整組任一格無排名 → null。
function luckOf(stats, cats) {
  let s = 0;
  for (const c of cats) {
    const cell = stats && stats[c];
    if (!cell || !cell.rank || !cell.of) return null;
    s += (cell.of + 1 - cell.rank);
  }
  return s;
}

function bar(val, max) {
  const pct = Math.max(0, Math.min(100, Math.round((val / max) * 100)));
  return `<span class="bar"><span style="width:${pct}%"></span></span>`;
}

function luckTable(weeks, teamName, totRank) {
  const head = `<tr><th class="wk">週 · 所遇之敵</th><th>投手<small>/84</small></th><th>打者<small>/84</small></th><th>投+打<small>分 · 當週名次</small></th></tr>`;
  const body = weeks.map((row) => {
    const opp = row.opponent ?? '—';
    const prog = row.in_progress ? ' <em class="prog">進行中</em>' : '';
    const p = luckOf(row.pitching, PIT);
    const b = luckOf(row.batting, BAT);
    const tot = (p != null && b != null) ? p + b : null;
    const tr = totRank[row.week] && totRank[row.week][teamName];
    const num = (v) => v == null ? `<td class="empty">—</td>` : `<td class="d"><span class="v">${v}</span></td>`;
    const totCell = tot == null
      ? `<td class="empty">—</td>`
      : `<td class="d tot${tr ? rankClass(tr.rank) : ''}"><span class="v">${tot}</span>` +
        `${tr ? `<span class="rk">#${tr.rank}/${tr.of}</span>` : ''}${bar(tot, 168)}</td>`;
    return `<tr><td class="wk"><span class="w">W${row.week}</span> ` +
           `<small>${md(row.dates[0])}–${md(row.dates[1])}</small>` +
           `<br><b>${esc(opp)}</b>${prog}</td>${num(p)}${num(b)}${totCell}</tr>`;
  }).join('');
  return `<div class="tbl-wrap"><div class="cap">運氣 · 對手強度（分數越高＝對手越強＝該週運氣越差；投+打附當週 12 隊對手強度排名）</div><table class="luck">${head}${body}</table></div>`;
}

// 跨隊預算：每週 12 個「對手投+打分」的排名（#1 = 該週對手最強）。
const _wt = {}; // week -> { team: tot }
for (const [team, rows] of Object.entries(data.teams)) {
  for (const row of rows) {
    const p = luckOf(row.pitching, PIT), b = luckOf(row.batting, BAT);
    if (p == null || b == null) continue;
    (_wt[row.week] = _wt[row.week] || {})[team] = p + b;
  }
}
const totRank = {}; // week -> { team: {rank, of} }
for (const [wk, tm] of Object.entries(_wt)) {
  const vals = Object.values(tm), of = vals.length;
  for (const [team, tot] of Object.entries(tm)) {
    const better = vals.filter((v) => v > tot).length;
    (totRank[wk] = totRank[wk] || {})[team] = { rank: better + 1, of };
  }
}

const slug = (name, i) => 'team-' + i;

const MASTER = 'WorkWork';
const DISCIPLES = new Set(['99 TeTe', 'YoBonBonLo']);
const roleRank = (n) => (n === MASTER ? 0 : DISCIPLES.has(n) ? 1 : 2);
function role(n) {
  if (n === MASTER) return { cls: 'self', badge: '老仙本尊', nav: 'self' };
  if (DISCIPLES.has(n)) return { cls: 'disciple', badge: '星宿門徒', nav: 'disciple' };
  return { cls: '', badge: '', nav: '' };
}

let names = Object.keys(data.teams);
names.sort((a, b) => roleRank(a) - roleRank(b));

const nav = names.map((n, i) => {
  const r = role(n);
  return `<a href="#${slug(n, i)}"${r.nav ? ` class="${r.nav}"` : ''}>${esc(n)}</a>`;
}).join('');

const sections = names.map((n, i) => {
  const weeks = data.teams[n];
  const r = role(n);
  const badge = r.badge ? ` <span class="badge ${r.cls}">${r.badge}</span>` : '';
  const sub = n === MASTER
    ? `老仙親征！下表為老仙歷週所<b>遭遇之敵</b>的累積戰功，每格下方為該數據當週 12 隊排名。`
    : DISCIPLES.has(n)
    ? `星宿門下，隨侍老仙左右。下表為此弟子歷週所<b>遭遇之敵</b>的累積戰功，每格下方為當週 12 隊排名。`
    : `下表為此路諸侯歷週所<b>遭遇之敵</b>的累積戰功，每格下方為該數據當週 12 隊排名。`;
  return `<section id="${slug(n, i)}" class="team${r.cls ? ' ' + r.cls : ''}">
    <h2>${esc(n)}${badge}<a class="top" href="#top">↑ 返頂</a></h2>
    <p class="sub">${sub}</p>
    ${luckTable(weeks, n, totRank)}
    ${table(weeks, PIT, 'pitching', '投 · 七律')}
    ${table(weeks, BAT, 'batting', '打 · 七律')}
  </section>`;
}).join('\n');

const html = `<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>星宿老仙群雄譜 · 十二路諸侯虛實錄</title>
<style>
:root{
  --ink:#1c241c; --muted:#717b71; --line:#e3e7e3; --paper:#ffffff; --bg:#eef1ee;
  --gold:#8f7426; --green:#2e7d32; --head:#06140a;
  --r1:#cfe3f7; --r2:#e1edfa; --r3:#eff5fc;
}
*{ box-sizing:border-box; }
html{ scroll-behavior:smooth; }
body{
  margin:0; color:var(--ink); background:var(--bg);
  font-family:"Noto Sans TC",system-ui,-apple-system,"Segoe UI",Roboto,"PingFang TC","Microsoft JhengHei",sans-serif;
  font-size:14px; line-height:1.5;
}
a{ color:#1769b0; text-decoration:none; }

/* ── 星宿 banner（唯一深色區，作品牌頭）── */
header{
  text-align:center; color:#dffbd0; padding:30px 18px 22px;
  background:radial-gradient(900px 360px at 50% -30%,rgba(57,255,20,.16),transparent 60%),
             linear-gradient(160deg,#06140a 0%,#0c2210 55%,#04100a 100%);
  border-bottom:3px solid var(--gold);
}
header h1{
  margin:0; font-family:"Noto Serif TC",serif; font-size:clamp(24px,4.6vw,40px);
  letter-spacing:.12em; color:#e6ffd9; text-shadow:0 0 12px rgba(57,255,20,.5),0 0 26px rgba(57,255,20,.25);
}
header .smoke{ font-size:22px; filter:drop-shadow(0 0 8px #39ff14); opacity:.9; }
header .boast{ max-width:720px; margin:12px auto 0; line-height:1.85; color:#cfe6c2; font-size:14px; }
header .boast b{ color:#ffe9a8; }
header .src{ color:#8fb583; font-size:12.5px; }

/* ── 導覽 ── */
nav{
  position:sticky; top:0; z-index:5; display:flex; flex-wrap:wrap; gap:6px; justify-content:center;
  padding:9px 12px; background:rgba(255,255,255,.96); backdrop-filter:blur(6px);
  border-bottom:1px solid var(--line);
}
nav a{ font-size:12.5px; padding:3px 9px; border:1px solid #d4dad4; border-radius:999px; color:#3a463a; background:#fff; }
nav a:hover{ background:#f0f4f0; }
nav a.self{ border-color:var(--gold); color:var(--gold); font-weight:600; }
nav a.disciple{ border-color:#9ccc9e; color:var(--green); }

main{ max-width:1040px; margin:0 auto; padding:18px 14px 60px; }

.legend{
  background:var(--paper); border:1px solid var(--line); border-radius:10px;
  padding:11px 14px; margin:10px 0 18px; color:#3a463a; font-size:13px; line-height:1.9;
}
.legend b{ color:var(--ink); }
.legend .sw{ display:inline-block; padding:1px 7px; border:1px solid var(--line); border-radius:4px; font-size:12px; color:var(--ink); }
.legend .sw1{ background:var(--r1); } .legend .sw2{ background:var(--r2); } .legend .sw3{ background:var(--r3); }

/* ── 隊伍卡片 ── */
section.team{
  margin:16px 0; padding:16px 18px; background:var(--paper);
  border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,.05);
}
section.team.self{ border:1px solid var(--gold); box-shadow:0 0 0 1px rgba(143,116,38,.25),0 1px 6px rgba(0,0,0,.06); }
section.team.disciple{ border:1px solid #a9d3ab; }
section.team h2{ margin:0 0 4px; font-size:19px; color:var(--ink); display:flex; align-items:center; gap:10px; flex-wrap:wrap; font-family:"Noto Serif TC",serif; letter-spacing:.03em; }
.badge{ font-size:12px; border-radius:999px; padding:2px 10px; font-family:"Noto Sans TC",sans-serif; }
.badge.self{ color:var(--gold); border:1px solid var(--gold); background:#fbf6e6; }
.badge.disciple{ color:var(--green); border:1px solid #9ccc9e; background:#eef7ee; }
.top{ margin-left:auto; font-size:12px; color:#8a948a; }
.sub{ margin:6px 0 12px; color:var(--muted); font-size:12.5px; line-height:1.7; }
.sub b{ color:#3a463a; }

.tbl-wrap{ overflow-x:auto; margin:10px 0; -webkit-overflow-scrolling:touch; }
.cap{ font-size:12px; color:var(--gold); letter-spacing:.22em; margin:8px 2px 4px; font-weight:600; }
table{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums; }
th,td{ border:1px solid var(--line); padding:5px 6px; text-align:center; white-space:nowrap; }
th{ background:#f4f6f4; color:#404a40; font-weight:600; letter-spacing:.04em; }
td.wk,th.wk{ text-align:left; min-width:140px; position:sticky; left:0; z-index:1; box-shadow:1px 0 0 var(--line); }
td.wk{ background:#fafbfa; }
th.wk{ background:#eef1ee; z-index:2; }
td.wk .w{ color:var(--gold); font-weight:700; }
td.wk small{ color:#98a298; }
td.wk b{ color:var(--ink); font-size:13.5px; font-weight:600; }
td.d .v{ display:block; font-size:13.5px; font-weight:600; color:var(--ink); }
td.d .rk{ display:block; font-size:10.5px; color:var(--muted); margin-top:1px; }
td.d.r1{ background:var(--r1); } td.d.r2{ background:var(--r2); } td.d.r3{ background:var(--r3); }
td.d.r1 .rk{ color:#3a5d80; font-weight:600; }
td.d.tot .v{ font-weight:700; }
.bar{ display:block; height:5px; margin-top:3px; background:#edf0ed; border-radius:3px; overflow:hidden; }
.bar>span{ display:block; height:100%; background:#7ba7d0; }
table.luck th small{ color:#98a298; font-weight:400; font-size:10px; }
td.empty{ color:#b3bbb3; background:repeating-linear-gradient(45deg,#f6f8f6,#f6f8f6 6px,#fff 6px,#fff 12px); }
.prog{ color:var(--green); font-style:normal; font-size:10.5px; border:1px solid #a9d3ab; border-radius:4px; padding:0 5px; background:#eef7ee; }

footer{ text-align:center; color:#7d877d; font-size:12.5px; padding:26px 16px 44px; letter-spacing:.18em; }
footer .seal{ color:var(--gold); }

/* ── RWD：手機優先優化（≤640px）── */
@media (max-width:640px){
  body{ font-size:13px; }
  header{ padding:20px 12px 14px; }
  header h1{ font-size:23px; letter-spacing:.08em; }
  header .smoke{ font-size:18px; }
  header .boast{ font-size:12.5px; line-height:1.7; }
  nav{ padding:7px 8px; gap:5px; flex-wrap:nowrap; overflow-x:auto; justify-content:flex-start; -webkit-overflow-scrolling:touch; }
  nav a{ flex:0 0 auto; }
  main{ padding:12px 8px 44px; }
  .legend{ padding:9px 11px; font-size:12px; line-height:1.8; }
  section.team{ padding:12px 10px; border-radius:8px; }
  section.team h2{ font-size:16px; gap:8px; }
  .badge{ font-size:11px; padding:1px 8px; }
  .top{ font-size:11px; }
  .sub{ font-size:11.5px; }
  .tbl-wrap{ margin:8px -10px; }                 /* 表格貼齊卡片左右緣，吃滿寬度 */
  .cap{ margin-left:10px; letter-spacing:.16em; }
  table{ font-size:12px; }
  th,td{ padding:4px 5px; }
  td.wk,th.wk{ min-width:78px; }                 /* 縮窄固定首欄，留更多空間給數據 */
  td.wk b{ font-size:11.5px; }
  td.wk small{ font-size:10px; }
  td.d .v{ font-size:12px; }
  td.d .rk{ font-size:9.5px; }
}
@media (max-width:380px){
  td.wk,th.wk{ min-width:70px; }
  th,td{ padding:3px 4px; }
}
</style>
</head>
<body>
<a id="top"></a>
<header>
  <div class="smoke">☘ ﹏ ☘</div>
  <h1>星宿老仙群雄譜</h1>
  <div class="boast">
    星宿老仙 <b>WorkWork</b> 法力無邊，德配天地，威震寰宇！今遍閱十二路諸侯逐週所遇群敵之投打虛實。<br>
    <span class="src">數據取自 Yahoo 聯盟每週對戰，排名為當週全聯盟 12 隊同場相較。</span>
  </div>
</header>
<nav>${nav}</nav>
<main>
  <div class="legend">
    <b>讀法</b>：每格上為數據、下為該數據當週 12 隊<b>排名</b>（<b>#1</b> 最佳；投手 ERA／WHIP 以低者為尊）。
    僅前三名淡藍標示 <span class="sw sw1">#1</span> <span class="sw sw2">#2</span> <span class="sw sw3">#3</span>，其餘白底；斜紋格為本週進行中。
    <br><b>運氣分</b>：對手各類別名次反推（#1＝12 分…#12＝1 分）加總 — 投手／打者各 7 項（滿分 84）、投+打 14 項（滿分 168）；<b>分數越高＝該週對手越強</b>。投+打另附 <b>#當週名次</b>（該週 12 隊對手強度相較，#1＝對手最強），跨週可比、前三名淡藍。
  </div>
${sections}
</main>
<footer>
  星宿老仙　千秋萬載　一統江湖　<span class="seal">— 星宿派 謹製 —</span>
</footer>
</body>
</html>`;

const outDir = path.join(ROOT, 'scout-site');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'index.html');
fs.writeFileSync(outFile, html, 'utf8');
console.log('WROTE ' + outFile + ' (' + html.length + ' bytes, ' + names.length + ' teams)');
console.log('ORDER ' + names.join(' | '));
