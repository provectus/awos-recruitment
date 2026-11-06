"""Behavior tests for registry/hooks/checks-before-stop/checks-before-stop.sh.

Runs the real script via subprocess in scratch git repositories. Package
managers and Python tools are stub scripts that record their arguments and
exit with a code read from the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[2]
    / "registry"
    / "hooks"
    / "checks-before-stop"
    / "checks-before-stop.sh"
)

STOP = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})
STOP_ACTIVE = json.dumps({"hook_event_name": "Stop", "stop_hook_active": True})


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _stub(path: Path, log: Path, fail_env: str | None = None) -> None:
    """Executable that logs its name and args; exits 1 when *fail_env* is set."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fail = f'[ -n "${{{fail_env}:-}}" ] && {{ echo "boom from $(basename "$0") $*"; exit 1; }}\n' if fail_env else ""
    path.write_text(f'#!/bin/sh\necho "$(basename "$0") $*" >> "{log}"\n{fail}exit 0\n')
    path.chmod(0o755)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("hi\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


@pytest.fixture
def log(tmp_path):
    return tmp_path / "calls.log"


@pytest.fixture
def tools(tmp_path, log):
    """A PATH dir with stub npm, pnpm and yarn."""
    d = tmp_path / "tools"
    for name in ("npm", "pnpm", "yarn"):
        _stub(d / name, log, fail_env="FAIL_PM")
    return d


def run_hook(repo: Path, tmp_path: Path, payload: str = STOP, path_dirs=(), **env_extra):
    path = os.pathsep.join([str(p) for p in path_dirs] + [os.environ["PATH"]])
    env = {
        "PATH": path,
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "CLAUDE_PROJECT_DIR": str(repo),
        **env_extra,
    }
    return subprocess.run(
        [str(HOOK)], input=payload, capture_output=True, text=True, env=env, timeout=60
    )


def calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def package_json(repo: Path, scripts: dict[str, str]) -> None:
    (repo / "package.json").write_text(json.dumps({"name": "x", "scripts": scripts}, indent=2))


def test_clean_tree_runs_nothing(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint .", "test": "vitest"})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "pkg")

    result = run_hook(repo, tmp_path, path_dirs=[tools])

    assert result.returncode == 0
    assert calls(log) == []


def test_runs_package_scripts_in_order(repo, tmp_path, tools, log):
    package_json(repo, {"test": "vitest", "build": "vite build", "typecheck": "tsc", "lint": "eslint ."})

    result = run_hook(repo, tmp_path, path_dirs=[tools])

    assert result.returncode == 0, result.stderr
    assert calls(log) == ["npm run lint", "npm run typecheck", "npm run test"]


def test_uses_the_package_manager_of_the_lock_file(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")

    run_hook(repo, tmp_path, path_dirs=[tools])

    assert calls(log) == ["pnpm run lint"]


def test_reads_only_the_scripts_object(repo, tmp_path, tools, log):
    # "directories.test" and an Nx "lint" target are not scripts.
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "x",
                "directories": {"test": "spec"},
                "nx": {"targets": {"lint": {"executor": "x"}}},
                "scripts": {"build": "vite build"},
            },
            indent=2,
        )
    )

    result = run_hook(repo, tmp_path, path_dirs=[tools], FAIL_PM="1")

    assert result.returncode == 0, result.stderr
    assert calls(log) == []


def test_brace_inside_a_script_does_not_hide_later_scripts(repo, tmp_path, tools, log):
    package_json(
        repo,
        {"lint": "eslint 'src/**/*.{ts,tsx}'", "typecheck": "tsc --noEmit", "test": "vitest"},
    )

    run_hook(repo, tmp_path, path_dirs=[tools])

    assert calls(log) == ["npm run lint", "npm run typecheck", "npm run test"]


def test_minified_package_json(repo, tmp_path, tools, log):
    (repo / "package.json").write_text(
        '{"name":"x","directories":{"test":"spec"},"scripts":{"lint":"eslint ."}}'
    )

    run_hook(repo, tmp_path, path_dirs=[tools])

    assert calls(log) == ["npm run lint"]


def test_package_manager_not_on_path_lets_claude_stop(repo, tmp_path, log):
    package_json(repo, {"lint": "eslint ."})
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
    only_npm = tmp_path / "only-npm"
    _stub(only_npm / "npm", log, fail_env="FAIL_PM")

    # PATH without the user's own pnpm, so the test does not depend on the machine.
    result = run_hook(repo, tmp_path, PATH=f"{only_npm}:/usr/bin:/bin", FAIL_PM="1")

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert calls(log) == []


def test_skips_the_npm_init_placeholder_test(repo, tmp_path, tools, log):
    package_json(repo, {"test": 'echo "Error: no test specified" && exit 1'})

    result = run_hook(repo, tmp_path, path_dirs=[tools])

    assert result.returncode == 0
    assert calls(log) == []


def test_failure_blocks_with_the_command_and_output(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint .", "test": "vitest"})

    result = run_hook(repo, tmp_path, path_dirs=[tools], FAIL_PM="1")

    assert result.returncode == 2
    assert "`npm run lint`" in result.stderr
    assert "boom from npm run lint" in result.stderr
    assert "Fix the problems below" in result.stderr
    # Stops at the first failing check.
    assert calls(log) == ["npm run lint"]


def test_green_run_is_remembered_until_the_tree_changes(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})

    run_hook(repo, tmp_path, path_dirs=[tools])
    run_hook(repo, tmp_path, path_dirs=[tools])
    assert calls(log) == ["npm run lint"]

    (repo / "new.ts").write_text("export {}\n")
    run_hook(repo, tmp_path, path_dirs=[tools])
    assert calls(log) == ["npm run lint", "npm run lint"]


def test_failed_run_is_not_remembered(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})

    assert run_hook(repo, tmp_path, path_dirs=[tools], FAIL_PM="1").returncode == 2
    assert run_hook(repo, tmp_path, path_dirs=[tools], FAIL_PM="1").returncode == 2
    assert len(calls(log)) == 2


def test_stop_hook_active_lets_claude_stop(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})

    result = run_hook(repo, tmp_path, payload=STOP_ACTIVE, path_dirs=[tools], FAIL_PM="1")

    assert result.returncode == 0
    assert calls(log) == []


def test_custom_command_wins_over_detection(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})
    marker = tmp_path / "custom.ran"

    result = run_hook(
        repo, tmp_path, path_dirs=[tools], AWOS_STOP_CHECKS_CMD=f"touch {marker}"
    )

    assert result.returncode == 0
    assert marker.exists()
    assert calls(log) == []


def test_checks_run_with_ci_set(repo, tmp_path):
    (repo / "change.txt").write_text("x\n")
    seen = tmp_path / "ci.txt"

    run_hook(repo, tmp_path, AWOS_STOP_CHECKS_CMD=f'echo "$CI" > {seen}')

    assert seen.read_text().strip() == "1"


def test_python_project_uses_venv_tools(repo, tmp_path, log):
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n\n[tool.ruff]\nline-length = 100\n")
    _stub(repo / ".venv" / "bin" / "ruff", log)
    _stub(repo / ".venv" / "bin" / "pytest", log)
    (repo / ".gitignore").write_text(".venv/\n")

    result = run_hook(repo, tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls(log) == ["ruff check .", "pytest -q"]


@pytest.mark.parametrize(("pytest_exit", "hook_exit"), [(5, 0), (1, 2)])
def test_pytest_with_no_tests_is_not_a_failure(repo, tmp_path, pytest_exit, hook_exit):
    # pytest exits 5 when it collects no tests: a new project, not a failure.
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    stub = repo / ".venv" / "bin" / "pytest"
    stub.parent.mkdir(parents=True)
    stub.write_text(f"#!/bin/sh\necho 'pytest said {pytest_exit}'\nexit {pytest_exit}\n")
    stub.chmod(0o755)
    (repo / ".gitignore").write_text(".venv/\n")

    result = run_hook(repo, tmp_path)

    assert result.returncode == hook_exit, result.stderr
    if hook_exit == 2:
        assert "pytest said 1" in result.stderr


def test_python_without_ruff_config_runs_only_pytest(repo, tmp_path, log):
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    _stub(repo / ".venv" / "bin" / "ruff", log)
    _stub(repo / ".venv" / "bin" / "pytest", log)
    (repo / ".gitignore").write_text(".venv/\n")

    run_hook(repo, tmp_path)

    assert calls(log) == ["pytest -q"]


def test_output_is_cut_to_the_last_lines(repo, tmp_path):
    (repo / "change.txt").write_text("x\n")
    cmd = "i=1; while [ $i -le 100 ]; do echo line$i; i=$((i+1)); done; exit 1"

    result = run_hook(repo, tmp_path, AWOS_STOP_CHECKS_CMD=cmd, AWOS_STOP_CHECKS_LINES="5")

    assert result.returncode == 2
    assert "line100" in result.stderr and "line96" in result.stderr
    assert "line95" not in result.stderr


def test_no_checks_found_exits_zero(repo, tmp_path):
    (repo / "notes.txt").write_text("x\n")

    result = run_hook(repo, tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_not_a_git_repo_exits_zero(tmp_path, tools, log):
    plain = tmp_path / "plain"
    plain.mkdir()
    package_json(plain, {"lint": "eslint ."})

    result = run_hook(plain, tmp_path, path_dirs=[tools], FAIL_PM="1")

    assert result.returncode == 0
    assert calls(log) == []


@pytest.mark.parametrize("payload", ["", "not json"])
def test_malformed_input_still_checks_safely(repo, tmp_path, payload):
    (repo / "change.txt").write_text("x\n")

    result = run_hook(repo, tmp_path, payload=payload, AWOS_STOP_CHECKS_CMD="true")

    assert result.returncode == 0


def test_can_be_turned_off(repo, tmp_path, tools, log):
    package_json(repo, {"lint": "eslint ."})

    result = run_hook(repo, tmp_path, path_dirs=[tools], FAIL_PM="1", AWOS_STOP_CHECKS="0")

    assert result.returncode == 0
    assert calls(log) == []
