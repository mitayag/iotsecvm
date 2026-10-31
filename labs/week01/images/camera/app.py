import json
import os
import socketserver
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
EVIDENCE_DIR = Path(os.environ.get("EVIDENCE_DIR", "/evidence"))
STATE_FILE = STATE_DIR / "state.json"
DEVICE = {
    "vendor": "HAU Virtual Devices",
    "model": "VC-100",
    "firmware": "1.0.0-stage1",
    "serial": "HAU-VC-0001",
}
DEFAULT_STATE = {"recording": True, "privacy_mode": False, "motion_detection": True}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_directories():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_STATE)


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def log_event(event, detail=""):
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        record = {"ts": utc_now(), "event": event, "detail": detail}
        with (EVIDENCE_DIR / "camera-events.log").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"evidence write failed: {exc}", flush=True)


class CameraHandler(BaseHTTPRequestHandler):
    server_version = "HAU-Camera/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def send_json(self, code, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, code, body):
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        state = load_state()
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "device": DEVICE["model"]})
        elif self.path == "/status":
            self.send_json(200, {"device": DEVICE, "state": state, "ts": utc_now()})
        elif self.path == "/api/state":
            self.send_json(200, state)
        elif self.path in ("/", "/index.html"):
            log_event("view", "device landing page")
            rows = "".join(
                f"<tr><th>{key}</th><td>{value}</td></tr>"
                for key, value in DEVICE.items()
            )
            self.send_html(
                200,
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>HAU Virtual Camera</title></head><body>"
                f"<h1>{DEVICE['model']} Virtual Camera</h1>"
                f"<table>{rows}</table>"
                "<p>Status endpoint: <code>/status</code></p>"
                "</body></html>",
            )
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/state":
            self.send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 4096:
            self.send_json(413, {"error": "payload too large"})
            return
        try:
            changes = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid json"})
            return
        if not isinstance(changes, dict):
            self.send_json(400, {"error": "object required"})
            return
        state = load_state()
        for key, value in changes.items():
            if key in DEFAULT_STATE and isinstance(value, bool):
                state[key] = value
        save_state(state)
        log_event("state-change", json.dumps(changes, sort_keys=True))
        self.send_json(200, state)


class RtspHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            request = self.rfile.readline(2048).decode("utf-8", "replace").strip()
        except OSError:
            return
        if not request:
            return
        method = request.split(" ", 1)[0].upper()
        log_event("rtsp", request)
        if method == "OPTIONS":
            response = "RTSP/1.0 200 OK\r\nPublic: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\nCSeq: 1\r\n\r\n"
        elif method == "DESCRIBE":
            sdp = (
                "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=HAU Virtual Camera\r\n"
                "t=0 0\r\nm=video 0 RTP/AVP 96\r\na=rtpmap:96 H264/90000\r\n"
            )
            response = (
                "RTSP/1.0 200 OK\r\nContent-Type: application/sdp\r\n"
                f"Content-Length: {len(sdp)}\r\nCSeq: 2\r\n\r\n{sdp}"
            )
        elif method in ("SETUP", "PLAY", "TEARDOWN"):
            response = f"RTSP/1.0 200 OK\r\nCSeq: 3\r\n\r\n"
        else:
            response = "RTSP/1.0 400 Bad Request\r\nCSeq: 1\r\n\r\n"
        try:
            self.wfile.write(response.encode("utf-8"))
        except OSError:
            pass


class ThreadedTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ensure_directories()
    if not STATE_FILE.exists():
        save_state(dict(DEFAULT_STATE))
    log_event("startup", f"{DEVICE['vendor']} {DEVICE['model']}")
    rtsp = ThreadedTcpServer(("0.0.0.0", 8554), RtspHandler)
    threading.Thread(target=rtsp.serve_forever, daemon=True).start()
    httpd = ThreadingHTTPServer(("0.0.0.0", 8080), CameraHandler)
    print("camera http listening on 8080, rtsp on 8554", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
