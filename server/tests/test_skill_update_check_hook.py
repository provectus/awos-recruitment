"""Behavior tests for registry/hooks/skill-update-check/skill-update-check.sh.

Runs the real script via subprocess against a tiny local HTTP server that
plays the registry's POST /check.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[2]
    / "registry"
    / "hooks"
    / "skill-update-check"
    / "skill-update-check.sh"
)

LOCK = {
    "version": 1,
    "project_id": "b4252689-6fa4-4675-b630-ecb331160d84",
    "skills": {"s": {"server": "x", "installed_at": "t", "hash": "0" * 64, "files": {}}},
}


class _CheckServer:
    """Serves a fixed reply for POST /check and records the requests."""

    def __init__(self, reply: str, status: int = 200):
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append(
                    {
                        "path": self.path,
                        "accept": self.headers.get("Accept"),
                        "body": json.loads(self.rfile.read(length) or b"{}"),
                    }
                )
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(reply.encode())

            def log_message(self, *args):  # silence
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "awos-recruitment.lock.json").write_text(json.dumps(LOCK))
    return tmp_path


def run_hook(project: Path, cache: Path, server_url: str | None, **env_extra: str):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(cache),
        "XDG_CACHE_HOME": str(cache),
        "CLAUDE_PROJECT_DIR": str(project),
        "AWOS_UPDATE_CHECK_INTERVAL": "0",
        **env_extra,
    }
    if server_url is not None:
        env["AWOS_SERVER_URL"] = server_url
    return subprocess.run(
        [str(HOOK)], input="{}", capture_output=True, text=True, env=env, timeout=20
    )


def test_prints_system_message_when_outdated(project, tmp_path):
    server = _CheckServer("awos-recruitment: 1 skill outdated (s). Run `x`.")
    try:
        proc = run_hook(project, tmp_path / "cache", server.url)
    finally:
        server.close()

    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["systemMessage"] == "awos-recruitment: 1 skill outdated (s). Run `x`."
    context = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert context.startswith("awos-recruitment: 1 skill outdated (s). Run `x`. In your first reply")
    assert "offer to run `npx @provectusinc/awos-recruitment skill update`" in context
    assert "Run it only if the user agrees" in context
    assert server.requests[0]["path"] == "/check"
    assert server.requests[0]["accept"] == "text/plain"
    assert server.requests[0]["body"]["skills"]["s"]["hash"] == "0" * 64


def test_silent_when_everything_is_current(project, tmp_path):
    server = _CheckServer("")
    try:
        proc = run_hook(project, tmp_path / "cache", server.url)
    finally:
        server.close()

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_checks_once_per_interval(project, tmp_path):
    server = _CheckServer("awos-recruitment: 1 skill outdated (s). Run `x`.")
    cache = tmp_path / "cache"
    try:
        first = run_hook(project, cache, server.url, AWOS_UPDATE_CHECK_INTERVAL="86400")
        second = run_hook(project, cache, server.url, AWOS_UPDATE_CHECK_INTERVAL="86400")
    finally:
        server.close()

    assert "systemMessage" in first.stdout
    assert second.stdout == ""
    assert len(server.requests) == 1


def test_silent_without_lock_file_and_without_skills(tmp_path):
    project = tmp_path / "empty"
    project.mkdir()
    server = _CheckServer("awos-recruitment: would be shown")
    try:
        proc = run_hook(project, tmp_path / "cache", server.url)
    finally:
        server.close()

    assert proc.returncode == 0
    assert proc.stdout == ""
    assert server.requests == []


def test_names_skills_installed_without_a_lock_file(tmp_path):
    """A pre-lock project gets a local reminder; the server is not called."""
    project = tmp_path / "old"
    for name in ("pytest-best-practices", "react-best-practices"):
        (project / ".claude" / "skills" / name).mkdir(parents=True)
    server = _CheckServer("awos-recruitment: would be shown")
    try:
        proc = run_hook(project, tmp_path / "cache", server.url)
    finally:
        server.close()

    assert proc.returncode == 0
    message = json.loads(proc.stdout)["systemMessage"]
    assert message.startswith(
        "awos-recruitment: 2 skill(s) installed without a lock file "
        "(pytest-best-practices, react-best-practices). Run `npx"
    )
    assert server.requests == []


def test_silent_when_server_is_down(project, tmp_path):
    proc = run_hook(project, tmp_path / "cache", "http://127.0.0.1:9")

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_silent_on_unexpected_server_text(project, tmp_path):
    server = _CheckServer("<html>502 Bad Gateway</html>", status=502)
    try:
        proc = run_hook(project, tmp_path / "cache", server.url)
    finally:
        server.close()

    assert proc.returncode == 0
    assert proc.stdout == ""


def test_opt_out(project, tmp_path):
    server = _CheckServer("awos-recruitment: would be shown")
    try:
        proc = run_hook(project, tmp_path / "cache", server.url, AWOS_UPDATE_CHECK="0")
    finally:
        server.close()

    assert proc.stdout == ""
    assert server.requests == []
