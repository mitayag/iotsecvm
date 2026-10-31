from __future__ import annotations

import json
import socket
from pathlib import Path

from .protocol import MAX_RESPONSE_BYTES, PROTOCOL_VERSION


class HelperError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: str | None = None,
        response: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.response = response


class HelperUnavailable(HelperError):
    def __init__(self, message: str) -> None:
        super().__init__("helper_unavailable", message)


class HelperClient:
    def __init__(self, socket_path: Path | str, timeout: float = 320.0) -> None:
        self.socket_path = str(socket_path)
        self.timeout = timeout

    def request(self, action: str, **fields) -> dict:
        payload = {"version": PROTOCOL_VERSION, "action": action, **fields}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(self.timeout)
                connection.connect(self.socket_path)
                connection.sendall(
                    json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
                )
                connection.shutdown(socket.SHUT_WR)
                chunks = []
                total = 0
                while True:
                    chunk = connection.recv(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES * 2:
                        raise HelperError(
                            "response_too_large", "helper response was too large"
                        )
                    chunks.append(chunk)
                    if b"\n" in chunk:
                        break
        except (OSError, socket.timeout) as exc:
            raise HelperUnavailable(f"helper is not reachable: {exc}") from exc

        raw = b"".join(chunks).split(b"\n", 1)[0]
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperError("invalid_response", "helper returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise HelperError("invalid_response", "helper returned an invalid response")
        return response

    def health(self) -> dict:
        response = self.request("health")
        if not response.get("ok"):
            error = response.get("error", {})
            raise HelperError(
                str(error.get("code", "helper_error")),
                str(error.get("message", "helper health check failed")),
            )
        return response

    def call(self, action: str, *, lab: str | None = None, **fields) -> dict:
        if lab is not None:
            fields["lab"] = lab
        response = self.request(action, **fields)
        if not response.get("ok"):
            error = response.get("error", {})
            raise HelperError(
                str(error.get("code", "helper_error")),
                str(error.get("message", "helper operation failed")),
                details=str(error.get("details", "")) or None,
                response=response,
            )
        return response
