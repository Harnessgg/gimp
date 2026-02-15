import json
import os
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import Request, urlopen


class BridgeClientError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BridgeClient:
    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("HARNESS_GIMP_BRIDGE_URL", "http://127.0.0.1:41749")

    def health(self) -> Dict[str, Any]:
        req = Request(f"{self.url}/health", method="GET")
        try:
            with urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise BridgeClientError("BRIDGE_UNAVAILABLE", str(exc)) from exc

    def call(self, method: str, params: Dict[str, Any], timeout_seconds: float = 30) -> Dict[str, Any]:
        payload = json.dumps({"method": method, "params": params}).encode("utf-8")
        req = Request(
            f"{self.url}/rpc",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise BridgeClientError("BRIDGE_UNAVAILABLE", str(exc)) from exc
        except Exception as exc:
            raise BridgeClientError("ERROR", str(exc)) from exc
        if not body.get("ok"):
            err = body.get("error") or {}
            raise BridgeClientError(err.get("code", "ERROR"), err.get("message", "unknown bridge error"))
        return body.get("result") or {}
