from __future__ import annotations

import argparse
import grp
import json
import os
import re
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

from .protocol import (
    HEALTH_ACTION,
    MAX_OUTPUT_CHARS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    PROTOCOL_VERSION,
    RequestError,
    build_command,
    validate_request,
)

IMPLEMENTED_PATTERN = re.compile(r"^status:\s*implemented\s*$", re.MULTILINE)
HELPER_VERSION = "1.0"


def log(message: str) -> None:
    print(f"[iotlab-helper] {message}", file=sys.stderr, flush=True)


def trim_output(value: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[-limit:], True


class HelperService:
    def __init__(
        self,
        root: Path,
        *,
        socket_path: Path,
        allowed_uids: set[int] | None = None,
        runner=None,
    ) -> None:
        self.root = root.resolve()
        self.socket_path = socket_path
        self.allowed_uids = allowed_uids or set()
        self._runner = runner or self._default_runner
        self._lock = threading.Lock()
        self._validate_root()

    def _validate_root(self) -> None:
        for relative in ("VERSION", "labs", "scripts"):
            if not (self.root / relative).exists():
                raise ValueError(f"helper root is missing {relative}: {self.root}")

    @staticmethod
    def _default_runner(command: list[str], cwd: Path, timeout: int):
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=dict(os.environ),
        )

    def _read_version(self) -> str:
        try:
            return (self.root / "VERSION").read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"

    def _check_lab(self, lab_id: str) -> None:
        lab_dir = self.root / "labs" / lab_id
        manifest = lab_dir / "lab.yaml"
        compose = lab_dir / "docker-compose.yml"
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError as exc:
            raise RequestError("unknown_lab", "lab manifest is unavailable") from exc
        if not IMPLEMENTED_PATTERN.search(text):
            raise RequestError(
                "lab_not_implemented",
                f"{lab_id} is planned and has no runtime",
            )
        if not compose.is_file():
            raise RequestError("lab_not_implemented", f"{lab_id} has no Compose file")

    def _check_script(self, script: Path) -> None:
        expected_dir = (self.root / "scripts").resolve()
        try:
            resolved = script.resolve(strict=True)
        except OSError as exc:
            raise RequestError("helper_misconfigured", "approved script is missing") from exc
        if resolved.parent != expected_dir or not resolved.is_file():
            raise RequestError("helper_misconfigured", "approved script is outside scripts/")

    def health(self) -> dict:
        return {
            "ok": True,
            "action": HEALTH_ACTION,
            "helper_version": HELPER_VERSION,
            "app_version": self._read_version(),
            "protocol_version": PROTOCOL_VERSION,
            "pid": os.getpid(),
            "allowed_actions": [
                "start",
                "stop",
                "reset",
                "status",
                "evidence_list",
                "evidence_read",
            ],
        }

    def handle(self, payload: object) -> dict:
        request = validate_request(payload)
        if request["action"] == HEALTH_ACTION:
            return self.health()

        lab_id = request["lab"]
        self._check_lab(lab_id)
        command, script_name, timeout, _mutating = build_command(
            str(self.root), request
        )
        self._check_script(Path(command[0]))

        if not self._lock.acquire(blocking=False):
            raise RequestError(
                "busy",
                "another laboratory operation is already running; retry shortly",
            )
        started = time.monotonic()
        try:
            try:
                completed = self._runner(command, self.root, timeout)
            except subprocess.TimeoutExpired as exc:
                raise RequestError(
                    "timeout",
                    f"{request['action']} exceeded {timeout} seconds",
                ) from exc
            except OSError as exc:
                raise RequestError("execution_error", str(exc)) from exc
        finally:
            self._lock.release()

        duration_ms = int((time.monotonic() - started) * 1000)
        stdout, stdout_truncated = trim_output(completed.stdout or "")
        stderr, stderr_truncated = trim_output(completed.stderr or "")
        result = {
            "script": script_name,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "duration_ms": duration_ms,
        }
        if completed.returncode != 0:
            return {
                "ok": False,
                "action": request["action"],
                "lab": lab_id,
                "result": result,
                "error": {
                    "code": "command_failed",
                    "message": f"{request['action']} failed with exit code {completed.returncode}",
                },
            }
        return {
            "ok": True,
            "action": request["action"],
            "lab": lab_id,
            "result": result,
        }


class ThreadedUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


class RequestHandler(socketserver.BaseRequestHandler):
    server: "HelperServer"

    def _peer_uid(self) -> int | None:
        if not hasattr(socket, "SO_PEERCRED"):
            return None
        try:
            raw = self.request.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            _pid, uid, _gid = struct.unpack("3i", raw)
            return uid
        except OSError:
            return None

    def handle(self) -> None:
        uid = self._peer_uid()
        allowed = self.server.service.allowed_uids
        if allowed and uid is not None and uid not in allowed:
            self._send(
                {
                    "ok": False,
                    "error": {
                        "code": "unauthorized_peer",
                        "message": "peer user is not allowed to use the helper",
                    },
                }
            )
            return

        payload = b""
        self.request.settimeout(10)
        try:
            while len(payload) <= MAX_REQUEST_BYTES and not payload.endswith(b"\n"):
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                payload += chunk
        except OSError:
            return

        if len(payload) > MAX_REQUEST_BYTES:
            self._send(
                {
                    "ok": False,
                    "error": {"code": "request_too_large", "message": "request is too large"},
                }
            )
            return
        try:
            request = json.loads(payload.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(
                {
                    "ok": False,
                    "error": {"code": "invalid_json", "message": "request is not valid JSON"},
                }
            )
            return

        try:
            response = self.server.service.handle(request)
        except RequestError as exc:
            response = {"ok": False, "error": exc.as_dict()}
        except Exception as exc:  # noqa: BLE001
            log(f"unhandled error: {exc!r}")
            response = {
                "ok": False,
                "error": {"code": "helper_error", "message": "internal helper error"},
            }
        self._send(response)

    def _send(self, payload: dict) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "response_too_large",
                        "message": "helper response exceeded the size limit",
                    },
                },
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
        try:
            self.request.sendall(encoded)
        except OSError:
            pass


class HelperServer(ThreadedUnixServer):
    def __init__(self, socket_path: Path, service: HelperService) -> None:
        self.service = service
        super().__init__(str(socket_path), RequestHandler)


def prepare_socket(path: Path, group: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o750)
    except PermissionError:
        pass
    if path.exists() or path.is_symlink():
        if not path.is_socket():
            raise SystemExit(f"refusing to replace non-socket path: {path}")
        path.unlink()


def secure_socket(path: Path, group: str | None) -> None:
    os.chmod(path, 0o660)
    if group:
        try:
            gid = grp.getgrnam(group).gr_gid
        except KeyError as exc:
            raise SystemExit(f"socket group does not exist: {group}") from exc
        os.chown(path, 0, gid)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="HAU IoT lab privileged helper")
    parser.add_argument("--root", default=os.environ.get("IOTLAB_ROOT", default_root))
    parser.add_argument(
        "--socket",
        default=os.environ.get("IOTLAB_HELPER_SOCKET", "/run/iotlab/helper.sock"),
    )
    parser.add_argument("--socket-group", default=os.environ.get("IOTLAB_SOCKET_GROUP"))
    parser.add_argument(
        "--allowed-uid",
        action="append",
        default=[],
        help="UID allowed to call the helper (repeatable)",
    )
    return parser.parse_args(argv)


def parse_allowed_uids(cli_values: list[str]) -> set[int]:
    raw = os.environ.get("IOTLAB_ALLOWED_UIDS", "")
    values = list(cli_values)
    if raw:
        values.extend(part.strip() for part in raw.split(",") if part.strip())
    uids: set[int] = set()
    for value in values:
        try:
            uids.add(int(value))
        except ValueError as exc:
            raise SystemExit(f"invalid allowed UID: {value}") from exc
    return uids


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    socket_path = Path(args.socket)
    allowed_uids = parse_allowed_uids(args.allowed_uid)

    prepare_socket(socket_path, args.socket_group)
    service = HelperService(root, socket_path=socket_path, allowed_uids=allowed_uids)
    server = HelperServer(socket_path, service)
    secure_socket(socket_path, args.socket_group)

    def stop(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log(
        f"listening on {socket_path} root={service.root} "
        f"allowed_uids={sorted(allowed_uids) if allowed_uids else 'socket-permissions-only'}"
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if socket_path.is_socket():
            socket_path.unlink()
        log("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
