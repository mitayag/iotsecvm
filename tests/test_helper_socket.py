from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from backend.helper.client import HelperClient, HelperError

ROOT = Path(__file__).resolve().parents[1]


def start_helper(socket_path: Path, allowed_uid: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "backend.helper.server",
            "--root",
            str(ROOT),
            "--socket",
            str(socket_path),
            "--allowed-uid",
            str(allowed_uid),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("helper exited")
        if socket_path.exists():
            try:
                HelperClient(socket_path, timeout=2).health()
                return process
            except HelperError:
                time.sleep(0.1)
        else:
            time.sleep(0.1)
    process.terminate()
    raise RuntimeError("helper socket did not become ready")


@pytest.fixture
def helper_socket():
    directory = Path(tempfile.mkdtemp(prefix="iotlab-sock-", dir="/tmp"))
    socket_path = directory / "h.sock"
    process = start_helper(socket_path, os.getuid())
    try:
        yield socket_path
    finally:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
        shutil.rmtree(directory, ignore_errors=True)


def test_socket_is_group_restricted(helper_socket: Path) -> None:
    mode = stat.S_IMODE(helper_socket.stat().st_mode)
    assert mode == 0o660


def test_health_over_socket(helper_socket: Path) -> None:
    payload = HelperClient(helper_socket).health()
    assert payload["ok"] is True
    assert payload["helper_version"] == "1.0"
    assert payload["app_version"] == (ROOT / "VERSION").read_text().strip()


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="SO_PEERCRED peer UID enforcement is Linux-specific",
)
@pytest.mark.skipif(os.getuid() == 0, reason="test requires an unprivileged user")
def test_unauthorized_peer_uid_is_rejected() -> None:
    directory = Path(tempfile.mkdtemp(prefix="iotlab-sock-", dir="/tmp"))
    socket_path = directory / "h.sock"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "backend.helper.server",
            "--root",
            str(ROOT),
            "--socket",
            str(socket_path),
            "--allowed-uid",
            "0",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline and not socket_path.exists():
            time.sleep(0.1)
        assert socket_path.exists()
        with pytest.raises(HelperError) as error:
            HelperClient(socket_path, timeout=3).health()
        assert error.value.code == "unauthorized_peer"
    finally:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
        shutil.rmtree(directory, ignore_errors=True)
