"""Shared git-sync helper for cron scripts.

The cron scripts (fa_scan.py, roster_sync.py, weekly_review.py) and the
cron_capture_payload.sh wrapper all run `git pull --rebase origin master`
before touching tracked files. A recurring failure mode: an *untracked*
file on the VPS shadows a path that origin later starts tracking — git
refuses to overwrite the untracked file and aborts every pull, silently
stalling all automation (see docs/handoff-vps-git-sync-fix.md, the
2026-05-19 mlb_query.py incident).

pull_rebase_with_recovery() auto-resolves the *harmless* case: when every
blocking untracked file is byte-identical to the upstream version,
removing it loses nothing — so we remove them and retry the pull once.
If even one blocking file differs from upstream (or the failure is
unrelated), nothing is touched and the caller alerts a human. We never
silently discard real local work.

Importable by the Python cron scripts; also runnable as a CLI so the
bash wrapper can reuse the same logic:

    python3 daily-advisor/git_sync.py [REPO_ROOT]   # exit 0 = ok, 2 = failed
"""

import os
import subprocess
import sys

# git's wording for the collision we can recover from. Covers both the
# "...overwritten by merge" and "...overwritten by checkout" variants.
_OVERWRITE_HEADER = "untracked working tree files would be overwritten"


def parse_blocking_files(text):
    """Extract the untracked-file paths git reports as blocking the pull.

    git prints them tab-indented between a header line containing
    'untracked working tree files would be overwritten' and a trailing
    'Please move or remove them ...' line. Returns [] when `text` is not
    that error (caller treats empty as 'not a recoverable collision').
    """
    files = []
    collecting = False
    for line in text.splitlines():
        if _OVERWRITE_HEADER in line:
            collecting = True
            continue
        if collecting:
            if line.startswith(("\t", " ")) and line.strip():
                files.append(line.strip())
            else:
                break
    return files


def _git(args, repo_root, timeout=30):
    """Run a git subcommand in repo_root, capturing output as text."""
    return subprocess.run(
        ["git", *args], cwd=repo_root,
        capture_output=True, text=True, timeout=timeout,
    )


def _upstream_blob(repo_root, path):
    """Blob hash for `path` in the just-fetched FETCH_HEAD, or None if absent.

    FETCH_HEAD (not origin/master) because `git pull` always fetches before
    it rebases — FETCH_HEAD is guaranteed fresh even when the rebase aborts.
    """
    r = _git(["rev-parse", f"FETCH_HEAD:{path}"], repo_root)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _worktree_blob(repo_root, path):
    """git's blob hash for the working-tree file, or None if it cannot hash."""
    r = _git(["hash-object", path], repo_root)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def pull_rebase_with_recovery(repo_root):
    """`git pull --rebase origin master`, auto-recovering harmless collisions.

    Returns (ok: bool, detail: str). `detail` is a short human-readable
    reason suitable for logging / Telegram.

    Recovery rule is all-or-nothing: on an 'untracked files would be
    overwritten' abort, EVERY blocking file must be byte-identical to its
    FETCH_HEAD version before any file is removed. A per-file approach
    could delete the identical ones, leave a differing one, and still
    fail the retry — stranding a half-cleaned working tree. So we verify
    the whole set first, then remove all and retry the pull exactly once.
    """
    r = _git(["pull", "--rebase", "origin", "master"], repo_root)
    if r.returncode == 0:
        return True, "pull --rebase OK"

    # git aborts the collision case on its own; this clears any other
    # partially-applied rebase. Harmless no-op when no rebase is active.
    _git(["rebase", "--abort"], repo_root, timeout=10)

    combined = (r.stderr or "") + "\n" + (r.stdout or "")
    blocking = parse_blocking_files(combined)
    if not blocking:
        return False, (
            "pull --rebase failed (not a recoverable collision): "
            + (r.stderr or r.stdout or "").strip()[:200]
        )

    # All-or-nothing: confirm every blocking file is identical upstream.
    mismatched = []
    for path in blocking:
        up = _upstream_blob(repo_root, path)
        wt = _worktree_blob(repo_root, path)
        if up is None or wt is None or up != wt:
            mismatched.append(path)
    if mismatched:
        return False, (
            "pull --rebase blocked by untracked files that DIFFER from "
            "upstream — manual fix needed: " + ", ".join(mismatched)
        )

    # Safe: every blocker is a duplicate of the upstream version.
    for path in blocking:
        try:
            os.remove(os.path.join(repo_root, path))
        except OSError:
            pass  # already gone — fine, the retry will tell us

    r2 = _git(["pull", "--rebase", "origin", "master"], repo_root)
    if r2.returncode == 0:
        return True, (
            f"recovered: removed {len(blocking)} untracked file(s) identical "
            f"to upstream ({', '.join(blocking)}), pull --rebase OK"
        )
    _git(["rebase", "--abort"], repo_root, timeout=10)
    return False, (
        "pull --rebase still failed after collision recovery — manual fix "
        "needed: " + (r2.stderr or r2.stdout or "").strip()[:200]
    )


def main(argv=None):
    """CLI entry point for the bash wrapper. Exit 0 = synced, 2 = failed."""
    argv = sys.argv[1:] if argv is None else argv
    repo_root = argv[0] if argv else os.getcwd()
    ok, detail = pull_rebase_with_recovery(repo_root)
    print(detail)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
