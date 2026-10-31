from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from backend.helper.protocol import RequestError
from backend.helper.server import HelperService

ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = ""):
        self.calls: list[list[str]] = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, command, cwd, timeout):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, self.stderr)


def service(runner: FakeRunner, tmp_path: Path) -> HelperService:
    return HelperService(ROOT, socket_path=tmp_path / "helper.sock", runner=runner)


def test_health_needs_no_runner(tmp_path: Path) -> None:
    runner = FakeRunner()
    helper = service(runner, tmp_path)
    payload = helper.handle({"version": 1, "action": "health"})
    assert payload["ok"] is True
    assert payload["action"] == "health"
    assert "start" in payload["allowed_actions"]
    assert runner.calls == []


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("start", ["lab-start.sh", "week01"]),
        ("stop", ["lab-stop.sh", "week01"]),
        ("reset", ["lab-reset.sh", "week01", "--yes"]),
        ("status", ["lab-inspect.sh", "week01"]),
        ("evidence_list", ["lab-evidence-list.sh", "week01"]),
        ("evidence_read", ["lab-evidence-read.sh", "week01", "notes.log"]),
    ],
)
def test_actions_use_fixed_scripts(
    action: str, expected: list[str], tmp_path: Path
) -> None:
    runner = FakeRunner()
    helper = service(runner, tmp_path)
    request = {"version": 1, "action": action, "lab": "week01"}
    if action == "evidence_read":
        request["filename"] = "notes.log"
    payload = helper.handle(request)
    assert payload["ok"] is True
    assert runner.calls[0][0] == str((ROOT / "scripts" / expected[0]).resolve())
    assert runner.calls[0][1:] == expected[1:]


def test_unknown_action_is_rejected(tmp_path: Path) -> None:
    helper = service(FakeRunner(), tmp_path)
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 1, "action": "shell", "lab": "week01"})
    assert error.value.code == "unknown_action"


@pytest.mark.parametrize("lab", ["week99", "../etc", "week1", "", None])
def test_invalid_lab_is_rejected(lab, tmp_path: Path) -> None:
    helper = service(FakeRunner(), tmp_path)
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 1, "action": "start", "lab": lab})
    assert error.value.code == "invalid_lab"


def test_planned_lab_is_rejected(tmp_path: Path) -> None:
    runner = FakeRunner()
    helper = service(runner, tmp_path)
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 1, "action": "start", "lab": "week02"})
    assert error.value.code == "lab_not_implemented"
    assert runner.calls == []


@pytest.mark.parametrize(
    "filename",
    ["../etc/passwd", "..", ".hidden/secret", "bad name.txt", "x" * 200, None],
)
def test_evidence_filename_traversal_is_rejected(filename, tmp_path: Path) -> None:
    runner = FakeRunner()
    helper = service(runner, tmp_path)
    with pytest.raises(RequestError) as error:
        helper.handle(
            {
                "version": 1,
                "action": "evidence_read",
                "lab": "week01",
                "filename": filename,
            }
        )
    assert error.value.code == "invalid_filename"
    assert runner.calls == []


def test_command_failure_returns_structured_error(tmp_path: Path) -> None:
    helper = service(FakeRunner(returncode=2, stderr="boom"), tmp_path)
    payload = helper.handle({"version": 1, "action": "start", "lab": "week01"})
    assert payload["ok"] is False
    assert payload["error"]["code"] == "command_failed"
    assert payload["result"]["returncode"] == 2
    assert payload["result"]["stderr"] == "boom"


def test_timeout_returns_structured_error(tmp_path: Path) -> None:
    def timeout_runner(command, cwd, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    helper = HelperService(
        ROOT, socket_path=tmp_path / "helper.sock", runner=timeout_runner
    )
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 1, "action": "reset", "lab": "week01"})
    assert error.value.code == "timeout"


def test_concurrent_operations_are_rejected(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_runner(command, cwd, timeout):
        started.set()
        release.wait(5)
        return subprocess.CompletedProcess(command, 0, "done", "")

    helper = HelperService(
        ROOT, socket_path=tmp_path / "helper.sock", runner=blocking_runner
    )
    results: list[dict] = []

    def first_call():
        results.append(helper.handle({"version": 1, "action": "start", "lab": "week01"}))

    thread = threading.Thread(target=first_call)
    thread.start()
    assert started.wait(2)
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 1, "action": "stop", "lab": "week01"})
    assert error.value.code == "busy"
    release.set()
    thread.join(5)
    assert results and results[0]["ok"] is True


def test_wrong_protocol_version_is_rejected(tmp_path: Path) -> None:
    helper = service(FakeRunner(), tmp_path)
    with pytest.raises(RequestError) as error:
        helper.handle({"version": 2, "action": "health"})
    assert error.value.code == "unsupported_version"
