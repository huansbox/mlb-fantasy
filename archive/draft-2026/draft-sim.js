// 7×7 蛇形選秀模擬器 v2 — 前 8 輪 × 12 隊 × 200 次蒙地卡羅
// 改進：A.擴充球員池 B.對手隨機偏移 C.守位覆蓋輸出 E.Punt SB 邏輯
// node draft-sim.js

const TEAMS = 12;
const ROUNDS = 8;
const SIMULATIONS = 200; // 每個順位跑 200 次

const ROSTER = {
  C: 1, '1B': 1, '2B': 1, '3B': 1, SS: 1, OF: 3, UTIL: 2, SP: 4, RP: 2, P: 3, BN: 3
};

// 完整球員池（App 1-202 + 關鍵晚輪）
// sbHeavy: true = SB 為主要 VOR 來源，punt SB 下 VOR 扣 1
const POOL = [
  // App 1-12
  { name: "Shohei Ohtani", pos: ["UTIL"], app: 1, vor: 8 },
  { name: "Tarik Skubal", pos: ["SP"], app: 2, vor: 12 },
  { name: "Aaron Judge", pos: ["OF"], app: 3, vor: 10 },
  { name: "Paul Skenes", pos: ["SP"], app: 4, vor: 8 },
  { name: "Bobby Witt Jr.", pos: ["SS"], app: 5, vor: 6, sbHeavy: true },
  { name: "Juan Soto", pos: ["OF"], app: 6, vor: 9 },
  { name: "Garrett Crochet", pos: ["SP"], app: 7, vor: 8 },
  { name: "Ronald Acuna Jr.", pos: ["OF"], app: 8, vor: 7 },
  { name: "Jose Ramirez", pos: ["3B"], app: 9, vor: 7 },
  { name: "Bryan Woo", pos: ["SP"], app: 10, vor: 5 },
  { name: "Cristopher Sanchez", pos: ["SP"], app: 11, vor: 7 },
  { name: "Vladimir Guerrero Jr.", pos: ["1B"], app: 12, vor: 7 },
  // App 13-24
  { name: "Julio Rodriguez", pos: ["OF"], app: 13, vor: 3 },
  { name: "Fernando Tatis Jr.", pos: ["OF"], app: 14, vor: 6 },
  { name: "Corbin Carroll", pos: ["OF"], app: 15, vor: 5, sbHeavy: true },
  { name: "Jacob deGrom", pos: ["SP"], app: 16, vor: 2 },
  { name: "Chris Sale", pos: ["SP"], app: 17, vor: 4 },
  { name: "Kyle Tucker", pos: ["OF"], app: 18, vor: 5 },
  { name: "Kyle Schwarber", pos: ["OF"], app: 19, vor: 3 },
  { name: "Logan Gilbert", pos: ["SP"], app: 20, vor: 6 },
  { name: "Max Fried", pos: ["SP"], app: 21, vor: 4 },
  { name: "Yoshinobu Yamamoto", pos: ["SP"], app: 22, vor: 1 },
  { name: "Gunnar Henderson", pos: ["SS"], app: 23, vor: 7 },
  { name: "Junior Caminero", pos: ["3B"], app: 24, vor: 1 },
  // App 25-36
  { name: "Logan Webb", pos: ["SP"], app: 25, vor: 7 },
  { name: "Zack Wheeler", pos: ["SP"], app: 26, vor: 4 },
  { name: "Elly De La Cruz", pos: ["SS"], app: 27, vor: 4, sbHeavy: true },
  { name: "Ketel Marte", pos: ["2B"], app: 28, vor: 5 },
  { name: "Cole Ragans", pos: ["SP"], app: 29, vor: 4 },
  { name: "Mason Miller", pos: ["RP"], app: 30, vor: 5 },
  { name: "Pete Alonso", pos: ["1B"], app: 31, vor: 3 },
  { name: "Trea Turner", pos: ["SS"], app: 32, vor: 0, sbHeavy: true },
  { name: "Nick Kurtz", pos: ["1B"], app: 33, vor: 4 },
  { name: "Brent Rooker", pos: ["OF"], app: 34, vor: 3 },
  { name: "Yordan Alvarez", pos: ["OF"], app: 35, vor: 5 },
  { name: "Francisco Lindor", pos: ["SS"], app: 36, vor: 2 },
  // App 37-48
  { name: "Jackson Chourio", pos: ["OF"], app: 37, vor: 1 },
  { name: "George Kirby", pos: ["SP"], app: 38, vor: 4 },
  { name: "Jesus Luzardo", pos: ["SP"], app: 39, vor: 3 },
  { name: "Bryce Harper", pos: ["1B"], app: 40, vor: 5 },
  { name: "Freddie Freeman", pos: ["1B"], app: 41, vor: 5 },
  { name: "Cal Raleigh", pos: ["C"], app: 42, vor: 3 },
  { name: "Cade Smith", pos: ["RP"], app: 43, vor: 6 },
  { name: "Edwin Diaz", pos: ["RP"], app: 44, vor: 4 },
  { name: "Framber Valdez", pos: ["SP"], app: 45, vor: 5 },
  { name: "Shohei Ohtani P", pos: ["SP"], app: 46, vor: 5 },
  { name: "Freddy Peralta", pos: ["SP"], app: 47, vor: 2 },
  { name: "Zach Neto", pos: ["SS"], app: 48, vor: 0 },
  // App 49-60
  { name: "Nathan Eovaldi", pos: ["SP"], app: 49, vor: 3 },
  { name: "Hunter Brown", pos: ["SP"], app: 50, vor: 3 },
  { name: "Manny Machado", pos: ["3B"], app: 51, vor: 5 },
  { name: "George Springer", pos: ["OF"], app: 52, vor: 2 },
  { name: "Jazz Chisholm Jr.", pos: ["2B", "3B"], app: 53, vor: 5 },
  { name: "Dylan Cease", pos: ["SP"], app: 54, vor: 3 },
  { name: "Rafael Devers", pos: ["1B"], app: 55, vor: 3 },
  { name: "Hunter Greene", pos: ["SP"], app: 56, vor: 2 },
  { name: "Joe Ryan", pos: ["SP"], app: 57, vor: 3 },
  { name: "Crow-Armstrong", pos: ["OF"], app: 58, vor: 1 },
  { name: "Devin Williams", pos: ["RP"], app: 59, vor: 4 },
  { name: "Andres Munoz", pos: ["RP"], app: 60, vor: 3 },
  // App 61-72
  { name: "Sonny Gray", pos: ["SP"], app: 61, vor: 4 },
  { name: "Blake Snell", pos: ["SP"], app: 62, vor: 0 },
  { name: "Jhoan Duran", pos: ["RP"], app: 63, vor: 3 },
  { name: "Nick Pivetta", pos: ["SP"], app: 64, vor: 2 },
  { name: "Mookie Betts", pos: ["SS"], app: 65, vor: 3 },
  { name: "Yandy Diaz", pos: ["1B"], app: 66, vor: -2 },
  { name: "James Wood", pos: ["OF"], app: 67, vor: 3 },
  { name: "Brandon Woodruff", pos: ["SP"], app: 68, vor: 2 },
  { name: "Roman Anthony", pos: ["OF"], app: 69, vor: 3 },
  { name: "Wyatt Langford", pos: ["OF"], app: 70, vor: 2 },
  { name: "Austin Riley", pos: ["3B"], app: 71, vor: 4 },
  { name: "Matt Olson", pos: ["1B"], app: 72, vor: 4 },
  // App 73-84
  { name: "Aroldis Chapman", pos: ["RP"], app: 73, vor: 2 },
  { name: "Emmet Sheehan", pos: ["SP"], app: 74, vor: 1 },
  { name: "Jarren Duran", pos: ["OF"], app: 75, vor: 3, sbHeavy: true },
  { name: "Jackson Merrill", pos: ["OF"], app: 76, vor: -1 },
  { name: "Shota Imanaga", pos: ["SP"], app: 77, vor: 3 },
  { name: "Josh Hader", pos: ["RP"], app: 78, vor: 2 },
  { name: "Maikel Garcia", pos: ["2B", "3B", "SS"], app: 79, vor: 1 },
  { name: "Seiya Suzuki", pos: ["OF"], app: 80, vor: 1 },
  { name: "Corey Seager", pos: ["SS"], app: 81, vor: 2 },
  { name: "Corbin Burns", pos: ["SP"], app: 82, vor: 3 },
  { name: "Josh Naylor", pos: ["1B"], app: 83, vor: 2 },
  { name: "Brice Turang", pos: ["2B"], app: 84, vor: 2, sbHeavy: true },
  // App 85-96
  { name: "David Bednar", pos: ["RP"], app: 85, vor: 2 },
  { name: "Riley Greene", pos: ["OF"], app: 86, vor: 5 },
  { name: "Kevin Gausman", pos: ["SP"], app: 87, vor: 2 },
  { name: "Eury Perez", pos: ["SP"], app: 88, vor: 2 },
  { name: "Jeremy Pena", pos: ["SS"], app: 89, vor: 1 },
  { name: "Nestor McLain", pos: ["SP"], app: 90, vor: 2 },
  { name: "Byron Buxton", pos: ["OF"], app: 91, vor: 4 },
  { name: "Bo Bichette", pos: ["SS"], app: 92, vor: -1 },
  { name: "Willy Adames", pos: ["SS"], app: 93, vor: 1 },
  { name: "Christian Yelich", pos: ["OF"], app: 94, vor: 2 },
  { name: "Kevin Bradish", pos: ["SP"], app: 95, vor: 3 },
  { name: "Geraldo Perdomo", pos: ["SS"], app: 96, vor: -1, sbHeavy: true },
  // App 97-120
  { name: "Randy Arozarena", pos: ["OF"], app: 97, vor: 0 },
  { name: "Teoscar Hernandez", pos: ["OF"], app: 98, vor: 1 },
  { name: "Eugenio Suarez", pos: ["3B"], app: 99, vor: 5 },
  { name: "William Contreras", pos: ["C"], app: 100, vor: 1 },
  { name: "Griffin Jax", pos: ["RP"], app: 101, vor: 2 },
  { name: "Vinnie Pasquantino", pos: ["1B"], app: 102, vor: 0 },
  { name: "Drew Rasmussen", pos: ["SP"], app: 103, vor: 2 },
  { name: "CJ Abrams", pos: ["SS"], app: 104, vor: 0, sbHeavy: true },
  { name: "Taylor Ward", pos: ["OF"], app: 105, vor: 1 },
  { name: "Michael King", pos: ["SP"], app: 106, vor: 2 },
  { name: "Raisel Iglesias", pos: ["RP"], app: 107, vor: 2 },
  { name: "Cody Bellinger", pos: ["OF"], app: 108, vor: 3 },
  { name: "Shane McClanahan", pos: ["SP"], app: 109, vor: 1 },
  { name: "Ezequiel Tovar", pos: ["SS"], app: 110, vor: 1 },
  { name: "Nico Hoerner", pos: ["2B"], app: 111, vor: 2 },
  { name: "Dansby Swanson", pos: ["SS"], app: 112, vor: 0 },
  { name: "Ryan Pepiot", pos: ["SP"], app: 113, vor: 1 },
  { name: "Ryan Helsley", pos: ["RP"], app: 114, vor: 2 },
  { name: "Alex Bregman", pos: ["3B"], app: 115, vor: 1 },
  { name: "Michael Busch", pos: ["1B"], app: 116, vor: 1 },
  { name: "Jose Altuve", pos: ["2B"], app: 117, vor: 4 },
  { name: "Jordan Hoffman", pos: ["RP"], app: 118, vor: 1 },
  { name: "Tanner Yesavage", pos: ["SP"], app: 119, vor: 1 },
  { name: "Tyler Glasnow", pos: ["SP"], app: 120, vor: -1 },
  // App 121-151
  { name: "Joe Musgrove", pos: ["SP"], app: 121, vor: 0 },
  { name: "Michael Harris II", pos: ["OF"], app: 122, vor: 2 },
  { name: "Ian Happ", pos: ["OF"], app: 123, vor: 1 },
  { name: "Luis Castillo", pos: ["SP"], app: 124, vor: 2 },
  { name: "Ranger Suarez", pos: ["SP"], app: 125, vor: 2 },
  { name: "Brandon Nimmo", pos: ["OF"], app: 126, vor: 1 },
  { name: "Tyler Megill", pos: ["RP"], app: 127, vor: 1 },
  { name: "Cade Horton", pos: ["SP"], app: 128, vor: 1 },
  { name: "Carlos Rodon", pos: ["SP"], app: 129, vor: 0 },
  { name: "Tyler Soderstrom", pos: ["1B"], app: 130, vor: 1 },
  { name: "Shea Langeliers", pos: ["C"], app: 131, vor: 0 },
  { name: "Hunter Goodman", pos: ["C"], app: 132, vor: 1 },
  { name: "Ben Rice", pos: ["C"], app: 133, vor: 1 },
  { name: "Matt Chapman", pos: ["3B"], app: 134, vor: 1 },
  { name: "Salvador Perez", pos: ["C"], app: 135, vor: 1 },
  { name: "Andy Pages", pos: ["OF"], app: 136, vor: 4 },
  { name: "Shane Bieber", pos: ["SP"], app: 137, vor: 0 },
  { name: "Emilio Pagan", pos: ["RP"], app: 138, vor: 1 },
  { name: "Peter Fairbanks", pos: ["RP"], app: 139, vor: 1 },
  { name: "Oneil Cruz", pos: ["OF"], app: 140, vor: 2 },
  { name: "Andres Uribe", pos: ["RP"], app: 141, vor: 0 },
  { name: "Trevor Story", pos: ["SS"], app: 142, vor: 1 },
  { name: "Matthew Boyd", pos: ["SP"], app: 143, vor: 0 },
  { name: "Bryan Abreu", pos: ["RP"], app: 144, vor: 2 },
  { name: "Tanner Bibee", pos: ["SP"], app: 145, vor: 2 },
  { name: "Jo Adell", pos: ["OF"], app: 146, vor: 1 },
  { name: "Kris Bubic", pos: ["SP"], app: 147, vor: 0 },
  { name: "Daniel Palencia", pos: ["RP"], app: 148, vor: 3 },
  { name: "Gleyber Torres", pos: ["2B"], app: 149, vor: 1 },
  { name: "Alec Burleson", pos: ["1B", "OF"], app: 150, vor: 1 },
  { name: "Bryan Reynolds", pos: ["OF"], app: 151, vor: 1 },
  // App 152-202
  { name: "Kenley Jansen", pos: ["RP"], app: 152, vor: 1 },
  { name: "Will Smith", pos: ["C"], app: 155, vor: 1 },
  { name: "Schwellenbach", pos: ["SP"], app: 156, vor: 1 },
  { name: "Nick Lodolo", pos: ["SP"], app: 157, vor: 1 },
  { name: "Brenton Doyle", pos: ["OF"], app: 158, vor: 1, sbHeavy: true },
  { name: "Jack Flaherty", pos: ["SP"], app: 159, vor: 1 },
  { name: "Xander Bogaerts", pos: ["SS"], app: 160, vor: 0 },
  { name: "Garrett Whitlock", pos: ["RP"], app: 161, vor: 4 },
  { name: "Spencer Strider", pos: ["SP"], app: 162, vor: 4 },
  { name: "Kyle Stowers", pos: ["OF"], app: 163, vor: 1 },
  { name: "Edward Cabrera", pos: ["SP"], app: 165, vor: 1 },
  { name: "Trevor Rogers", pos: ["SP"], app: 166, vor: 1 },
  { name: "Bryson Stott", pos: ["2B", "SS"], app: 168, vor: 0 },
  { name: "Aaron Nola", pos: ["SP"], app: 170, vor: 5 },
  { name: "Luis Robert Jr.", pos: ["OF"], app: 173, vor: 1 },
  { name: "Munetaka Murakami", pos: ["1B", "3B"], app: 174, vor: 2 },
  { name: "Steven Kwan", pos: ["OF"], app: 185, vor: 1 },
  { name: "Robert Garcia", pos: ["RP"], app: 188, vor: 2 },
  { name: "Gavin Williams", pos: ["SP"], app: 190, vor: 1 },
  { name: "Luis Arraez", pos: ["1B", "2B"], app: 194, vor: -2 },
  { name: "Jacob Wilson", pos: ["SS"], app: 196, vor: 1 },
  { name: "Ozzie Albies", pos: ["2B"], app: 199, vor: 5 },
  { name: "Lawrence Butler", pos: ["OF"], app: 202, vor: 4 },
  { name: "Adley Rutschman", pos: ["C"], app: 167, vor: 1 },
  { name: "Hunter Gaddis", pos: ["RP"], app: 210, vor: 3 },
];

// ── 工具函式 ──

function canFit(team, playerPos) {
  for (const p of playerPos) {
    const key = p === 'LF' || p === 'CF' || p === 'RF' ? 'OF' : p;
    if (ROSTER[key] && (team.filled[key] || 0) < ROSTER[key]) return key;
  }
  const isPitcher = playerPos.some(p => p === 'SP' || p === 'RP');
  if (!isPitcher && (team.filled['UTIL'] || 0) < ROSTER['UTIL']) return 'UTIL';
  if (isPitcher && (team.filled['P'] || 0) < ROSTER['P']) return 'P';
  if ((team.filled['BN'] || 0) < ROSTER['BN']) return 'BN';
  return null;
}

// B: 對手選秀加隨機偏移（±5 App 排名）
function opponentPick(team, available) {
  const shuffled = available.map(p => ({
    ...p,
    effectiveApp: p.app + Math.round((Math.random() - 0.5) * 10) // ±5
  }));
  shuffled.sort((a, b) => a.effectiveApp - b.effectiveApp);
  for (const sp of shuffled) {
    const original = available.find(a => a.name === sp.name);
    const slot = canFit(team, original.pos);
    if (slot) return { player: original, slot };
  }
  return { player: available[0], slot: 'BN' };
}

// E: 我方邏輯，VOR 加 Punt SB 扣分
function myPick(team, available, round) {
  let candidates = available.filter(p => {
    if (p.pos.includes('RP') && !p.pos.includes('SP')) {
      if (round < 7) return false;
      const rpFilled = (team.filled['RP'] || 0);
      if (rpFilled >= ROSTER['RP']) return false;
    }
    return true;
  });

  let good = candidates.filter(p => p.vor >= 1);
  if (good.length === 0) good = candidates;

  // E: Punt SB — SB 為主的球員 VOR 扣 1
  good = good.map(p => ({
    ...p,
    effectiveVor: p.sbHeavy ? p.vor - 1 : p.vor
  }));

  good.sort((a, b) => b.effectiveVor - a.effectiveVor || a.app - b.app);

  for (const player of good) {
    const original = candidates.find(c => c.name === player.name);
    const slot = canFit(team, original.pos);
    if (slot && slot !== 'BN') return { player: original, slot };
  }
  for (const player of good) {
    const original = candidates.find(c => c.name === player.name);
    const slot = canFit(team, original.pos);
    if (slot) return { player: original, slot };
  }
  if (!good[0]) return { player: available[0], slot: 'BN' };
  return { player: good[0], slot: 'BN' };
}

function snakeOrder(numTeams, numRounds) {
  const order = [];
  for (let r = 0; r < numRounds; r++) {
    const forward = r % 2 === 0;
    for (let t = 0; t < numTeams; t++) {
      order.push(forward ? t : numTeams - 1 - t);
    }
  }
  return order;
}

// C: 守位覆蓋率
function positionCoverage(team) {
  const needed = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP'];
  const missing = [];
  for (const p of needed) {
    const need = ROSTER[p] || 0;
    const have = team.filled[p] || 0;
    if (have < need) {
      const gap = need - have;
      missing.push(`${p}${gap > 1 ? 'x' + gap : ''}`);
    }
  }
  return missing;
}

// ── 蒙地卡羅模擬 ──

function simulate(myPosition) {
  const teams = Array.from({ length: TEAMS }, () => ({
    picks: [], filled: {}, totalVor: 0,
  }));

  const available = [...POOL];
  const order = snakeOrder(TEAMS, ROUNDS);
  const draftLog = [];

  for (let pickIdx = 0; pickIdx < order.length; pickIdx++) {
    const teamIdx = order[pickIdx];
    const round = Math.floor(pickIdx / TEAMS) + 1;
    const team = teams[teamIdx];
    const isMe = teamIdx === myPosition;

    const result = isMe
      ? myPick(team, available, round)
      : opponentPick(team, available);

    const { player, slot } = result;
    const idx = available.findIndex(a => a.name === player.name);
    if (idx >= 0) available.splice(idx, 1);

    team.picks.push({ ...player, slot, round });
    team.filled[slot] = (team.filled[slot] || 0) + 1;
    team.totalVor += player.vor;

    if (isMe) {
      draftLog.push({
        round, pick: pickIdx + 1, name: player.name,
        pos: player.pos.join('/'), slot, app: player.app, vor: player.vor
      });
    }
  }

  return { draftLog, myTeam: teams[myPosition] };
}

// ── 主程式：蒙地卡羅 ──

console.log('='.repeat(72));
console.log('  7x7 蛇形選秀模擬 v2 — 蒙地卡羅 200 次 × 12 順位');
console.log('  對手：App 排名 ±5 隨機偏移 + 守位需求');
console.log('  我方：7x7 VOR + Punt SB(-1) + Punt SV+H');
console.log('='.repeat(72));

const allSummaries = [];

for (let pos = 0; pos < TEAMS; pos++) {
  // 每個順位跑 N 次
  const vorResults = [];
  const pickFreq = {}; // 各輪各球員出現次數
  const missingFreq = {}; // 守位缺口頻率
  const bestRun = { vor: -999, log: null, missing: null };

  for (let sim = 0; sim < SIMULATIONS; sim++) {
    const { draftLog, myTeam } = simulate(pos);
    vorResults.push(myTeam.totalVor);

    if (myTeam.totalVor > bestRun.vor) {
      bestRun.vor = myTeam.totalVor;
      bestRun.log = draftLog;
      bestRun.missing = positionCoverage(myTeam);
    }

    // 統計各輪球員出現頻率
    for (const d of draftLog) {
      const key = `R${d.round}`;
      if (!pickFreq[key]) pickFreq[key] = {};
      pickFreq[key][d.name] = (pickFreq[key][d.name] || 0) + 1;
    }

    // 統計守位缺口
    const missing = positionCoverage(myTeam);
    for (const m of missing) {
      missingFreq[m] = (missingFreq[m] || 0) + 1;
    }
  }

  // 統計
  vorResults.sort((a, b) => a - b);
  const mid = Math.floor(SIMULATIONS / 2);
  const median = (vorResults[mid - 1] + vorResults[mid]) / 2;
  const p10 = vorResults[Math.floor(SIMULATIONS * 0.1)];
  const p90 = vorResults[Math.floor(SIMULATIONS * 0.9)];
  const avg = (vorResults.reduce((a, b) => a + b, 0) / SIMULATIONS).toFixed(1);

  console.log(`\n${'─'.repeat(72)}`);
  console.log(`  順位 #${pos + 1}  │  VOR: 中位 ${median} / 平均 ${avg} / 範圍 ${p10}-${p90}`);
  console.log(`${'─'.repeat(72)}`);

  // 最佳路徑
  console.log('  [最佳路徑] VOR ' + bestRun.vor);
  console.log('  R  球員                     守位   槽位  App   VOR');
  console.log('  ── ───────────────────────── ────── ──── ───── ────');
  for (const d of bestRun.log) {
    console.log(`  R${d.round}  ${d.name.padEnd(25)} ${d.pos.padEnd(6)} ${d.slot.padEnd(4)} #${String(d.app).padStart(3)}   ${d.vor >= 0 ? '+' : ''}${d.vor}`);
  }

  // 各輪最常出現球員 Top 3
  console.log('\n  [各輪到手機率 Top 3]');
  for (let r = 1; r <= ROUNDS; r++) {
    const freq = pickFreq[`R${r}`] || {};
    const sorted = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const parts = sorted.map(([name, count]) => `${name} ${Math.round(count / SIMULATIONS * 100)}%`);
    console.log(`  R${r}: ${parts.join(' | ')}`);
  }

  // C: 守位缺口
  if (Object.keys(missingFreq).length > 0) {
    const gaps = Object.entries(missingFreq)
      .sort((a, b) => b[1] - a[1])
      .map(([pos, count]) => `${pos} ${Math.round(count / SIMULATIONS * 100)}%`);
    console.log(`\n  [R8 後守位缺口] ${gaps.join(' | ')}`);
  } else {
    console.log('\n  [R8 後守位缺口] 無（全部填滿）');
  }

  allSummaries.push({ pos: pos + 1, median, avg: parseFloat(avg), p10, p90 });
}

// 總結
console.log(`\n${'='.repeat(72)}`);
console.log('  總結：各順位 VOR（中位數排序）');
console.log('='.repeat(72));
allSummaries.sort((a, b) => b.median - a.median || b.avg - a.avg);
for (const s of allSummaries) {
  const bar = '█'.repeat(Math.max(0, Math.round(s.median / 2)));
  console.log(`  #${String(s.pos).padStart(2)}  中位 ${String(s.median).padStart(3)}  (${s.p10}-${s.p90})  ${bar}`);
}
