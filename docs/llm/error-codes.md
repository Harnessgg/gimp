# Error Codes

## Process exit codes

- `0`: success
- `1`: general/internal failure
- `2`: file not found
- `3`: validation failed
- `4`: invalid input
- `5`: bridge unavailable

## Retry guidance

- Retry only when `error.code == "BRIDGE_UNAVAILABLE"`.
- Suggested retry: `0.5s`, `1s`, `2s` (max 3 retries).
