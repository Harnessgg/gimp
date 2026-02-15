import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from harness_gimp.bridge.operations import BridgeOperationError, handle_method


class BridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/rpc":
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
            method = payload.get("method")
            params = payload.get("params") or {}
            result = handle_method(method, params)
            self._send_json(200, {"ok": True, "result": result})
        except BridgeOperationError as exc:
            self._send_json(400, {"ok": False, "error": {"code": exc.code, "message": exc.message}})
        except Exception as exc:  # pragma: no cover
            self._send_json(500, {"ok": False, "error": {"code": "ERROR", "message": str(exc)}})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_bridge_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), BridgeHandler)
    server.serve_forever()
