# Bridge Protocol

## Transport
- HTTP bridge
- `GET /health`
- `POST /rpc` with JSON body:
  - `{"method":"system.health","params":{}}`

## Response
- Success:
  - `{"ok": true, "result": {...}}`
- Error:
  - `{"ok": false, "error": {"code":"INVALID_INPUT","message":"..."}}`

## CLI Contract
- CLI wraps bridge payloads into the standard response envelope:
  - `ok`
  - `protocolVersion`
  - `command`
  - `data` or `error`
