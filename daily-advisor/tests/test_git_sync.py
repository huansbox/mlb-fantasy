"""Unit + integration tests for git_sync collision recovery.

parse_blocking_files is pure → plain unit tests. pull_rebase_with_recovery
touches real git, so each test builds a throwaway bare origin + two clones
(a 'seed' clone that drives origin forward, a 'vps' clone under test) under
pytest's tmp_path. No network — all remotes are local paths.
"""

import subprocess

from git_sync import main, parse_blocking_files, pull_rebase_with_recovery


# ── parse_blocking_files (pure) ──

_MERGE_ERR = (
    "From https://github.com/x/y\n"
    " * branch            master     -> FETCH_HEAD\n"
    "error: The following untracked working tree files would be "
    "overwritten by merge:\n"
    "\tdaily-advisor/mlb_query.py\n"
    "Please move or remove them before you merge.\n"
    "Aborting\n"
)

_CHECKOUT_ERR = (
    "error: The following untracked working tree files would be "
    "overwritten by checkout:\n"
    "\tdaily-advisor/mlb_query.py\n"
    "Please move or remove them before you switch branches.\n"
    "Aborting\n"
)

_MULTI_ERR = (
    "error: The following untracked working tree files would be "
    "overwritten by merge:\n"
    "\ta/one.py\n"
    "\tb/two.json\n"
    "Please move or remove them before you merge.\n"
)


def test_parse_single_merge_variant():
    assert parse_blocking_files(_MERGE_ERR) == ["daily-advisor/mlb_query.py"]


def test_parse_checkout_variant():
    """git uses '...by checkout' wording for the rebase checkout step."""
    assert parse_blocking_files(_CHECKOUT_ERR) == ["daily-advisor/mlb_query.py"]


def test_parse_multiple_files():
    assert parse_blocking_files(_MULTI_ERR) == ["a/one.py", "b/two.json"]


def test_parse_unrelated_error_returns_empty():
    assert parse_blocking_files("fatal: unable to access remote") == []


def test_parse_empty_string():
    assert parse_blocking_files("") == []


# ── integration: pull_rebase_with_recovery (real git repos) ──

def _run(args, cwd):
    subprocess.run(args, cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _configure(repo):
    _run(["git", "config", "user.email", "t@t"], repo)
    _run(["git", "config", "user.name", "tester"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)


def _make_origin_with_clones(tmp_path):
    """Bare origin + 'seed' clone (drives origin) + 'vps' clone (under test).

    Both clones start at the same single-commit master.
    """
    origin = tmp_path / "origin.git"
    _run(["git", "init", "--bare", "-b", "master", str(origin)], tmp_path)

    seed = tmp_path / "seed"
    _run(["git", "clone", str(origin), str(seed)], tmp_path)
    _configure(seed)
    (seed / "README.md").write_text("seed\n")
    _run(["git", "add", "."], seed)
    _run(["git", "commit", "-m", "seed"], seed)
    _run(["git", "push", "origin", "master"], seed)

    vps = tmp_path / "vps"
    _run(["git", "clone", str(origin), str(vps)], tmp_path)
    _configure(vps)
    return origin, seed, vps


def _origin_adds_tracked_file(seed, name, content):
    """Seed clone commits a new tracked file and pushes it to origin."""
    (seed / name).write_text(content)
    _run(["git", "add", "."], seed)
    _run(["git", "commit", "-m", f"add {name}"], seed)
    _run(["git", "push", "origin", "master"], seed)


def test_clean_pull_succeeds(tmp_path):
    """No collision: a normal pull --rebase just advances the working tree."""
    _, seed, vps = _make_origin_with_clones(tmp_path)
    _origin_adds_tracked_file(seed, "new.py", "x\n")
    ok, detail = pull_rebase_with_recovery(str(vps))
    assert ok, detail
    assert (vps / "new.py").read_text() == "x\n"


def test_recovers_identical_untracked_file(tmp_path):
    """Untracked file byte-identical to incoming tracked file → auto-remove + pull."""
    _, seed, vps = _make_origin_with_clones(tmp_path)
    _origin_adds_tracked_file(seed, "new.py", "print('hi')\n")
    # VPS independently created an identical untracked copy.
    (vps / "new.py").write_text("print('hi')\n")
    ok, detail = pull_rebase_with_recovery(str(vps))
    assert ok, detail
    assert "recovered" in detail
    # File is now tracked from origin.
    r = subprocess.run(["git", "ls-files", "new.py"], cwd=str(vps),
                        capture_output=True, text=True)
    assert r.stdout.strip() == "new.py"


def test_aborts_when_untracked_file_differs(tmp_path):
    """Untracked file differs from upstream → never removed, caller must fix."""
    _, seed, vps = _make_origin_with_clones(tmp_path)
    _origin_adds_tracked_file(seed, "new.py", "print('hi')\n")
    (vps / "new.py").write_text("print('LOCAL EDIT')\n")
    ok, detail = pull_rebase_with_recovery(str(vps))
    assert not ok
    assert "DIFFER" in detail
    # Local content preserved untouched.
    assert (vps / "new.py").read_text() == "print('LOCAL EDIT')\n"


def test_all_or_nothing_partial_match(tmp_path):
    """Two blockers, one identical + one differing → neither removed."""
    _, seed, vps = _make_origin_with_clones(tmp_path)
    (seed / "a.py").write_text("same\n")
    (seed / "b.py").write_text("origin-version\n")
    _run(["git", "add", "."], seed)
    _run(["git", "commit", "-m", "add a.py b.py"], seed)
    _run(["git", "push", "origin", "master"], seed)
    (vps / "a.py").write_text("same\n")          # identical to upstream
    (vps / "b.py").write_text("vps-version\n")   # differs from upstream
    ok, detail = pull_rebase_with_recovery(str(vps))
    assert not ok
    # The identical file must NOT be removed when the set isn't all-clean.
    assert (vps / "a.py").exists()
    assert (vps / "b.py").read_text() == "vps-version\n"


def test_main_cli_returns_zero_on_clean_pull(tmp_path):
    _, seed, vps = _make_origin_with_clones(tmp_path)
    _origin_adds_tracked_file(seed, "new.py", "x\n")
    assert main([str(vps)]) == 0


def test_main_cli_returns_two_on_unrecoverable(tmp_path):
    _, seed, vps = _make_origin_with_clones(tmp_path)
    _origin_adds_tracked_file(seed, "new.py", "a\n")
    (vps / "new.py").write_text("DIFFERENT\n")
    assert main([str(vps)]) == 2
