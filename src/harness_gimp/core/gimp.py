import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class GimpExecutionError(Exception):
    pass


def resolve_gimp_binary() -> Path:
    env = os.getenv("HARNESS_GIMP_BIN")
    if env:
        path = Path(env)
        if path.exists():
            return path

    candidates = [
        Path(r"C:\Users\vivid\AppData\Local\Programs\GIMP 3\bin\gimp-console-3.0.exe"),
        Path(r"C:\Users\vivid\AppData\Local\Programs\GIMP 3\bin\gimp-console.exe"),
        Path(r"C:\Program Files\GIMP 3\bin\gimp-console-3.0.exe"),
        Path(r"C:\Program Files\GIMP 3\bin\gimp-console.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise GimpExecutionError("GIMP binary not found. Set HARNESS_GIMP_BIN.")


def _profile_dir() -> Path:
    env = os.getenv("HARNESS_GIMP_PROFILE_DIR")
    if env:
        path = Path(env)
    else:
        path = Path.cwd() / ".gimp-profile" / "GIMP" / "3.0"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_python_batch(
    code: str,
    timeout_seconds: float = 180.0,
    gimp_bin: Optional[Path] = None,
) -> Dict[str, Any]:
    binary = gimp_bin or resolve_gimp_binary()
    env = os.environ.copy()
    env["GIMP3_DIRECTORY"] = str(_profile_dir())
    cmd = [
        str(binary),
        "--no-interface",
        "--quit",
        "--batch-interpreter=python-fu-eval",
        "--batch",
        code,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_seconds,
    )
    merged = (proc.stdout or "") + "\n" + (proc.stderr or "")
    marker = "HARNESS_JSON:"
    data_line = None
    for line in merged.splitlines():
        if line.startswith(marker):
            data_line = line[len(marker) :].strip()
    if proc.returncode != 0:
        raise GimpExecutionError((merged.strip() or "GIMP batch execution failed"))
    if not data_line:
        raise GimpExecutionError("GIMP did not return structured output.")
    try:
        return json.loads(data_line)
    except json.JSONDecodeError as exc:
        raise GimpExecutionError(f"Invalid JSON from GIMP: {exc}") from exc
