// SessionStart hook（mlb-fantasy 專案專屬）：把本機 git mirror 與 origin/master 同步，
// 讓每個 session 開場拿到 VPS cron 已同步的最新 roster_config.json（+ docs / waiver-log）。
//
// 背景（兩層 staleness）：
//   第 2 層 [Yahoo → origin]：VPS roster_sync cron（*/15）偵測異動 → 更新 config → push。
//   第 1 層 [origin → 本機]：本 hook 補這層。FA add 即時生效、waiver 15:00 後同步，
//                            兩者都靠「把 origin 拉進本機」拿到，不需本機 call Yahoo。
//   詳見 CLAUDE.md「roster freshness pipeline」段。
//
// 安全原則：
//   - 只在 source == "startup"（全新 session）才自動 pull；resume/compact/clear 只報告，
//     不動 working tree（避免工作到一半被 pull 改檔）。
//   - 只在「分支 = master + working tree 乾淨 + 能 fast-forward」時才 pull --ff-only。
//     在 feature branch / 有未 commit 變更 / 有未推的本機 commit 時 → 只警告，不碰 working tree。
//   - 永不讓 session 啟動失敗：全程 try/catch，git fetch 帶 timeout，網路不通只軟提示。
//   - 純 git 操作，走 GitHub（非 VPS）→ 不受本機↔VPS 間歇丟包影響，不碰 Yahoo / token。

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const REMOTE = "origin";
const BRANCH = "master";
const FETCH_TIMEOUT_MS = 15000;

// repo root：優先 CLAUDE_PROJECT_DIR，否則由本檔位置（hooks/）回推上一層。
const repoRoot =
  process.env.CLAUDE_PROJECT_DIR ||
  resolve(dirname(fileURLToPath(import.meta.url)), "..");

function git(args, { timeout } = {}) {
  const r = spawnSync("git", ["-C", repoRoot, ...args], {
    encoding: "utf8",
    timeout,
  });
  if (r.status !== 0 || r.error) return null;
  return (r.stdout || "").trim();
}

function emit(msg) {
  process.stdout.write(msg + "\n");
}

try {
  let source = "startup";
  try {
    const input = JSON.parse(readFileSync(0, "utf8"));
    source = input?.source || "startup";
  } catch {
    // 讀不到 stdin（手動測試等）→ 當作 startup
  }

  const fetched = git(["fetch", REMOTE, BRANCH], { timeout: FETCH_TIMEOUT_MS });
  if (fetched === null) {
    emit("⚠️ [roster-sync] 無法 fetch origin（離線？）— roster 新鮮度未驗證，動名單前手動 `git pull`。");
    process.exit(0);
  }

  const behind = parseInt(git(["rev-list", "--count", `HEAD..${REMOTE}/${BRANCH}`]) || "0", 10);
  // origin/master 的 roster_config.json 最後更新相對時間（roster 真實新鮮度）
  const rosterAge =
    git(["log", "-1", "--format=%cr", `${REMOTE}/${BRANCH}`, "--", "daily-advisor/roster_config.json"]) || "unknown";

  if (behind === 0) {
    const head = git(["rev-parse", "--short", "HEAD"]) || "?";
    emit(`✅ [roster-sync] 本機已是最新（@ ${head}）。roster_config.json 最後異動：${rosterAge}。`);
    process.exit(0);
  }

  const branch = git(["rev-parse", "--abbrev-ref", "HEAD"]) || "?";
  const dirty = (git(["status", "--porcelain"]) || "") !== "";
  const ahead = parseInt(git(["rev-list", "--count", `${REMOTE}/${BRANCH}..HEAD`]) || "0", 10);

  const canPull = source === "startup" && branch === BRANCH && !dirty && ahead === 0;

  if (canPull) {
    const pulled = git(["pull", "--ff-only", REMOTE, BRANCH], { timeout: FETCH_TIMEOUT_MS });
    if (pulled !== null) {
      const head = git(["rev-parse", "--short", "HEAD"]) || "?";
      emit(`✅ [roster-sync] 已自動同步 ${behind} 個 commit → ${head}。roster_config.json 最後異動：${rosterAge}。`);
    } else {
      emit(`⚠️ [roster-sync] 本機落後 origin/${BRANCH} ${behind} 個 commit，但 pull --ff-only 失敗 — 手動 \`git pull\` 確認。`);
    }
    process.exit(0);
  }

  // 不自動 pull：說明原因，提醒手動處理。
  let reason;
  if (source !== "startup") reason = `非全新 session（source=${source}，不在工作中途自動改檔）`;
  else if (branch !== BRANCH) reason = `目前在分支 ${branch}（非 ${BRANCH}）`;
  else if (dirty) reason = "有未 commit 的本機變更";
  else reason = `有 ${ahead} 個未推送的本機 commit`;

  emit(
    `⚠️ [roster-sync] origin/${BRANCH} 領先 ${behind} 個 commit（${reason}）。` +
    `roster_config.json 可能 stale（origin 上最後異動：${rosterAge}）— 做 roster 判斷前先 \`git pull\` / rebase。`
  );
  process.exit(0);
} catch (e) {
  // 任何意外都不可擋住 session 啟動。
  emit(`⚠️ [roster-sync] hook 異常（${e?.message || e}）— roster 新鮮度未驗證。`);
  process.exit(0);
}
