import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import typer

from harness_gimp import __version__
from harness_gimp.bridge.client import BridgeClient, BridgeClientError
from harness_gimp.bridge.protocol import ERROR_CODES, PROTOCOL_VERSION
from harness_gimp.bridge.server import run_bridge_server

app = typer.Typer(add_completion=False, help="Bridge-first CLI for GIMP editing")
bridge_app = typer.Typer(add_completion=False, help="Bridge lifecycle and verification")
app.add_typer(bridge_app, name="bridge")


def _print(payload: Dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _ok(command: str, data: Dict[str, Any]) -> None:
    _print({"ok": True, "protocolVersion": PROTOCOL_VERSION, "command": command, "data": data})


def _fail(command: str, code: str, message: str, retryable: bool = False) -> None:
    _print(
        {
            "ok": False,
            "protocolVersion": PROTOCOL_VERSION,
            "command": command,
            "error": {"code": code, "message": message, "retryable": retryable},
        }
    )
    raise SystemExit(ERROR_CODES.get(code, 1))


def _bridge_state_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", str(Path.home())))
    state_dir = root / "harness-gimp"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _bridge_pid_file() -> Path:
    return _bridge_state_dir() / "bridge.pid"


def _bridge_client() -> BridgeClient:
    return BridgeClient()


def _call_bridge(command: str, method: str, params: Dict[str, Any], timeout_seconds: float = 30) -> Dict[str, Any]:
    client = _bridge_client()
    try:
        return client.call(method, params, timeout_seconds=timeout_seconds)
    except BridgeClientError as exc:
        _fail(command, exc.code, exc.message, retryable=exc.code == "BRIDGE_UNAVAILABLE")
    except Exception as exc:  # pragma: no cover
        _fail(command, "ERROR", str(exc))
    raise RuntimeError("unreachable")


def _ensure_bridge_ready(command: str) -> None:
    _call_bridge(command, "system.health", {}, timeout_seconds=5)


@bridge_app.command("serve")
def bridge_serve(host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(41749, "--port")) -> None:
    run_bridge_server(host, port)


@bridge_app.command("start")
def bridge_start(host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(41749, "--port")) -> None:
    pid_file = _bridge_pid_file()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            _ok("bridge.start", {"status": "already-running", "pid": pid, "host": host, "port": port})
            return
        except Exception:
            pid_file.unlink(missing_ok=True)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen(
        [sys.executable, "-m", "harness_gimp", "bridge", "serve", "--host", host, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    os.environ["HARNESS_GIMP_BRIDGE_URL"] = f"http://{host}:{port}"

    for _ in range(30):
        time.sleep(0.1)
        try:
            status = BridgeClient(f"http://{host}:{port}").health()
            if status.get("ok"):
                _ok("bridge.start", {"status": "started", "pid": process.pid, "host": host, "port": port})
                return
        except BridgeClientError:
            continue
    _fail("bridge.start", "BRIDGE_UNAVAILABLE", "Bridge process started but health check failed")


@bridge_app.command("stop")
def bridge_stop() -> None:
    pid_file = _bridge_pid_file()
    if not pid_file.exists():
        _ok("bridge.stop", {"status": "not-running"})
        return
    pid = int(pid_file.read_text(encoding="utf-8").strip())
    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        _ok("bridge.stop", {"status": "stopped", "pid": pid})
    except Exception as exc:
        _fail("bridge.stop", "ERROR", str(exc))


@bridge_app.command("status")
def bridge_status() -> None:
    client = _bridge_client()
    try:
        health = client.health()
        _ok("bridge.status", {"running": True, "health": health, "url": client.url})
    except BridgeClientError as exc:
        _fail("bridge.status", exc.code, exc.message, retryable=True)


@bridge_app.command("verify")
def bridge_verify(
    iterations: int = typer.Option(10, "--iterations", min=1, max=200),
    max_failures: int = typer.Option(0, "--max-failures", min=0),
) -> None:
    client = _bridge_client()
    failures = 0
    latencies_ms = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            client.call("system.health", {})
        except BridgeClientError:
            failures += 1
        latencies_ms.append(round((time.perf_counter() - start) * 1000, 3))
        time.sleep(0.02)
    stable = failures <= max_failures
    data = {
        "stable": stable,
        "iterations": iterations,
        "failures": failures,
        "maxFailuresAllowed": max_failures,
        "latencyMs": {
            "min": min(latencies_ms),
            "max": max(latencies_ms),
            "avg": round(sum(latencies_ms) / len(latencies_ms), 3),
        },
    }
    _ok("bridge.verify", data)
    if not stable:
        raise SystemExit(ERROR_CODES["ERROR"])


@bridge_app.command("soak")
def bridge_soak(
    iterations: int = typer.Option(100, "--iterations", min=1, max=5000),
    action: str = typer.Option("system.health", "--action"),
    action_params_json: str = typer.Option("{}", "--action-params-json"),
) -> None:
    try:
        params = json.loads(action_params_json)
    except json.JSONDecodeError as exc:
        _fail("bridge.soak", "INVALID_INPUT", f"Invalid JSON: {exc}")
    if not isinstance(params, dict):
        _fail("bridge.soak", "INVALID_INPUT", "action-params-json must be an object")
    _ok(
        "bridge.soak",
        _call_bridge(
            "bridge.soak",
            "system.soak",
            {"iterations": iterations, "action": action, "action_params": params},
            timeout_seconds=max(30, iterations),
        ),
    )


@app.command("actions")
def actions() -> None:
    _ok("actions", _call_bridge("actions", "system.actions", {}))


@app.command("doctor")
def doctor() -> None:
    _ok("doctor", _call_bridge("doctor", "system.doctor", {}, timeout_seconds=30))


@app.command("inspect")
def inspect_image(image: Path) -> None:
    _ok("inspect", _call_bridge("inspect", "image.inspect", {"image": str(image)}, timeout_seconds=180))


@app.command("validate")
def validate_image(image: Path) -> None:
    data = _call_bridge("validate", "image.validate", {"image": str(image)}, timeout_seconds=180)
    _ok("validate", data)
    if not data.get("isValid", False):
        raise SystemExit(ERROR_CODES["VALIDATION_FAILED"])


@app.command("diff")
def diff_images(source: Path, target: Path) -> None:
    _ok("diff", _call_bridge("diff", "image.diff", {"source": str(source), "target": str(target)}, timeout_seconds=180))


@app.command("snapshot")
def snapshot_image(image: Path, description: str) -> None:
    _ok("snapshot", _call_bridge("snapshot", "image.snapshot", {"image": str(image), "description": description}, timeout_seconds=30))


@app.command("undo")
def undo_image(image: Path) -> None:
    _ok("undo", _call_bridge("undo", "image.undo", {"image": str(image)}, timeout_seconds=30))


@app.command("redo")
def redo_image(image: Path) -> None:
    _ok("redo", _call_bridge("redo", "image.redo", {"image": str(image)}, timeout_seconds=30))


@app.command("open")
def open_image(image: Path) -> None:
    _ok("open", _call_bridge("open", "image.open", {"image": str(image)}, timeout_seconds=180))


@app.command("save")
def save_image(image: Path, output: Path) -> None:
    _ensure_bridge_ready("save")
    _ok("save", _call_bridge("save", "image.save", {"image": str(image), "output": str(output)}, timeout_seconds=300))


@app.command("clone-project")
def clone_project(source: Path, target: Path, overwrite: bool = typer.Option(False, "--overwrite")) -> None:
    _ok(
        "clone-project",
        _call_bridge("clone-project", "image.clone", {"source": str(source), "target": str(target), "overwrite": overwrite}, timeout_seconds=30),
    )


@app.command("plan-edit")
def plan_edit(image: Path, action: str, params_json: str = "{}") -> None:
    _ensure_bridge_ready("plan-edit")
    try:
        parsed = json.loads(params_json)
    except json.JSONDecodeError as exc:
        _fail("plan-edit", "INVALID_INPUT", f"Invalid JSON: {exc}")
    if not isinstance(parsed, dict):
        _fail("plan-edit", "INVALID_INPUT", "params-json must be an object")
    _ok(
        "plan-edit",
        _call_bridge("plan-edit", "project.plan_edit", {"image": str(image), "action": action, "params": parsed}, timeout_seconds=300),
    )


@app.command("resize")
def resize_image(
    image: Path,
    width: int = typer.Option(..., "--width"),
    height: int = typer.Option(..., "--height"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("resize")
    _ok(
        "resize",
        _call_bridge(
            "resize",
            "image.resize",
            {
                "image": str(image),
                "width": width,
                "height": height,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("crop")
def crop_image(
    image: Path,
    x: int = typer.Option(..., "--x"),
    y: int = typer.Option(..., "--y"),
    width: int = typer.Option(..., "--width"),
    height: int = typer.Option(..., "--height"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("crop")
    _ok(
        "crop",
        _call_bridge(
            "crop",
            "image.crop",
            {"image": str(image), "x": x, "y": y, "width": width, "height": height, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("rotate")
def rotate_image(
    image: Path,
    degrees: int = typer.Option(..., "--degrees"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("rotate")
    _ok(
        "rotate",
        _call_bridge(
            "rotate",
            "image.rotate",
            {"image": str(image), "degrees": degrees, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("flip")
def flip_image(
    image: Path,
    axis: str = typer.Option(..., "--axis"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("flip")
    _ok(
        "flip",
        _call_bridge(
            "flip",
            "image.flip",
            {"image": str(image), "axis": axis, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("canvas-size")
def canvas_size(
    image: Path,
    width: int = typer.Option(..., "--width"),
    height: int = typer.Option(..., "--height"),
    offset_x: int = typer.Option(0, "--offset-x"),
    offset_y: int = typer.Option(0, "--offset-y"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("canvas-size")
    _ok(
        "canvas-size",
        _call_bridge(
            "canvas-size",
            "image.canvas_size",
            {
                "image": str(image),
                "width": width,
                "height": height,
                "offsetX": offset_x,
                "offsetY": offset_y,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("export")
def export_image(image: Path, output: Path) -> None:
    _ensure_bridge_ready("export")
    _ok(
        "export",
        _call_bridge("export", "image.export", {"image": str(image), "output": str(output)}, timeout_seconds=300),
    )


@app.command("brightness-contrast")
def brightness_contrast(
    image: Path,
    brightness: float = typer.Option(0, "--brightness"),
    contrast: float = typer.Option(0, "--contrast"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("brightness-contrast")
    _ok(
        "brightness-contrast",
        _call_bridge(
            "brightness-contrast",
            "adjust.brightness_contrast",
            {
                "image": str(image),
                "brightness": brightness,
                "contrast": contrast,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("levels")
def levels(
    image: Path,
    black: float = typer.Option(0, "--black"),
    white: float = typer.Option(255, "--white"),
    gamma: float = typer.Option(1.0, "--gamma"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("levels")
    _ok(
        "levels",
        _call_bridge(
            "levels",
            "adjust.levels",
            {
                "image": str(image),
                "black": black,
                "white": white,
                "gamma": gamma,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("hue-saturation")
def hue_saturation(
    image: Path,
    hue: float = typer.Option(0, "--hue"),
    saturation: float = typer.Option(0, "--saturation"),
    lightness: float = typer.Option(0, "--lightness"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("hue-saturation")
    _ok(
        "hue-saturation",
        _call_bridge(
            "hue-saturation",
            "adjust.hue_saturation",
            {
                "image": str(image),
                "hue": hue,
                "saturation": saturation,
                "lightness": lightness,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("color-balance")
def color_balance(
    image: Path,
    cyan_red: float = typer.Option(0, "--cyan-red"),
    magenta_green: float = typer.Option(0, "--magenta-green"),
    yellow_blue: float = typer.Option(0, "--yellow-blue"),
    transfer_mode: str = typer.Option("MIDTONES", "--transfer-mode"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("color-balance")
    _ok(
        "color-balance",
        _call_bridge(
            "color-balance",
            "adjust.color_balance",
            {
                "image": str(image),
                "cyanRed": cyan_red,
                "magentaGreen": magenta_green,
                "yellowBlue": yellow_blue,
                "transferMode": transfer_mode,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("curves")
def curves(
    image: Path,
    channel: str = typer.Option("value", "--channel"),
    points_json: str = typer.Option(..., "--points-json"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("curves")
    try:
        points = json.loads(points_json)
    except json.JSONDecodeError as exc:
        _fail("curves", "INVALID_INPUT", f"Invalid JSON: {exc}")
    _ok(
        "curves",
        _call_bridge(
            "curves",
            "adjust.curves",
            {
                "image": str(image),
                "channel": channel,
                "points": points,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("color-temperature")
def color_temperature(
    image: Path,
    temperature: float = typer.Option(..., "--temperature"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("color-temperature")
    _ok(
        "color-temperature",
        _call_bridge(
            "color-temperature",
            "adjust.color_temperature",
            {"image": str(image), "temperature": temperature, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("invert")
def invert(image: Path, layer_index: int = typer.Option(0, "--layer-index"), output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("invert")
    _ok(
        "invert",
        _call_bridge(
            "invert",
            "adjust.invert",
            {"image": str(image), "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("desaturate")
def desaturate(
    image: Path,
    mode: str = typer.Option("luma", "--mode"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("desaturate")
    _ok(
        "desaturate",
        _call_bridge(
            "desaturate",
            "adjust.desaturate",
            {"image": str(image), "mode": mode, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("blur")
def blur(
    image: Path,
    radius: float = typer.Option(4.0, "--radius"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("blur")
    _ok(
        "blur",
        _call_bridge(
            "blur",
            "filter.blur",
            {"image": str(image), "radius": radius, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("gaussian-blur")
def gaussian_blur(
    image: Path,
    radius_x: float = typer.Option(4.0, "--radius-x"),
    radius_y: float = typer.Option(4.0, "--radius-y"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("gaussian-blur")
    _ok(
        "gaussian-blur",
        _call_bridge(
            "gaussian-blur",
            "filter.gaussian_blur",
            {
                "image": str(image),
                "radiusX": radius_x,
                "radiusY": radius_y,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("sharpen")
def sharpen(
    image: Path,
    radius: float = typer.Option(2.0, "--radius"),
    amount: float = typer.Option(1.0, "--amount"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("sharpen")
    _ok(
        "sharpen",
        _call_bridge(
            "sharpen",
            "filter.sharpen",
            {"image": str(image), "radius": radius, "amount": amount, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("unsharp-mask")
def unsharp_mask(
    image: Path,
    radius: float = typer.Option(2.0, "--radius"),
    amount: float = typer.Option(1.0, "--amount"),
    threshold: float = typer.Option(0.0, "--threshold"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("unsharp-mask")
    _ok(
        "unsharp-mask",
        _call_bridge(
            "unsharp-mask",
            "filter.unsharp_mask",
            {
                "image": str(image),
                "radius": radius,
                "amount": amount,
                "threshold": threshold,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("noise-reduction")
def noise_reduction(
    image: Path,
    strength: int = typer.Option(3, "--strength"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("noise-reduction")
    _ok(
        "noise-reduction",
        _call_bridge(
            "noise-reduction",
            "filter.noise_reduction",
            {"image": str(image), "strength": strength, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-list")
def layer_list(image: Path) -> None:
    _ok("layer-list", _call_bridge("layer-list", "layer.list", {"image": str(image)}, timeout_seconds=180))


@app.command("layer-add")
def layer_add(
    image: Path,
    name: str = typer.Option(..., "--name"),
    position: int = typer.Option(0, "--position"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-add")
    _ok(
        "layer-add",
        _call_bridge(
            "layer-add",
            "layer.add",
            {"image": str(image), "name": name, "position": position, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-remove")
def layer_remove(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-remove")
    _ok(
        "layer-remove",
        _call_bridge(
            "layer-remove",
            "layer.remove",
            {"image": str(image), "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-rename")
def layer_rename(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    name: str = typer.Option(..., "--name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-rename")
    _ok(
        "layer-rename",
        _call_bridge(
            "layer-rename",
            "layer.rename",
            {"image": str(image), "layerIndex": layer_index, "name": name, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-opacity")
def layer_opacity(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    opacity: float = typer.Option(..., "--opacity"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-opacity")
    _ok(
        "layer-opacity",
        _call_bridge(
            "layer-opacity",
            "layer.opacity",
            {"image": str(image), "layerIndex": layer_index, "opacity": opacity, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-blend-mode")
def layer_blend_mode(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    mode: str = typer.Option(..., "--mode"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-blend-mode")
    _ok(
        "layer-blend-mode",
        _call_bridge(
            "layer-blend-mode",
            "layer.blend_mode",
            {"image": str(image), "layerIndex": layer_index, "mode": mode, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-merge-down")
def layer_merge_down(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-merge-down")
    _ok(
        "layer-merge-down",
        _call_bridge(
            "layer-merge-down",
            "layer.merge_down",
            {"image": str(image), "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-duplicate")
def layer_duplicate(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    position: int = typer.Option(0, "--position"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-duplicate")
    _ok(
        "layer-duplicate",
        _call_bridge(
            "layer-duplicate",
            "layer.duplicate",
            {"image": str(image), "layerIndex": layer_index, "position": position, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("layer-reorder")
def layer_reorder(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index"),
    index: int = typer.Option(..., "--index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("layer-reorder")
    _ok(
        "layer-reorder",
        _call_bridge(
            "layer-reorder",
            "layer.reorder",
            {"image": str(image), "layerIndex": layer_index, "index": index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("add-layer-mask")
def add_layer_mask(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index", "--layer-id"),
    mode: str = typer.Option("WHITE", "--mode"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("add-layer-mask")
    _ok(
        "add-layer-mask",
        _call_bridge(
            "add-layer-mask",
            "mask.add",
            {"image": str(image), "layerIndex": layer_index, "mode": mode, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("apply-layer-mask")
def apply_layer_mask(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index", "--layer-id"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("apply-layer-mask")
    _ok(
        "apply-layer-mask",
        _call_bridge(
            "apply-layer-mask",
            "mask.apply",
            {"image": str(image), "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("select-all")
def select_all(image: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("select-all")
    _ok(
        "select-all",
        _call_bridge("select-all", "selection.all", {"image": str(image), "output": str(output) if output else str(image)}, timeout_seconds=300),
    )


@app.command("select-none")
def select_none(image: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("select-none")
    _ok(
        "select-none",
        _call_bridge("select-none", "selection.none", {"image": str(image), "output": str(output) if output else str(image)}, timeout_seconds=300),
    )


@app.command("feather-selection")
def feather_selection(
    image: Path,
    radius: float = typer.Option(..., "--radius"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("feather-selection")
    _ok(
        "feather-selection",
        _call_bridge(
            "feather-selection",
            "selection.feather",
            {"image": str(image), "radius": radius, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("select-rectangle")
def select_rectangle(
    image: Path,
    x: int = typer.Option(..., "--x"),
    y: int = typer.Option(..., "--y"),
    width: int = typer.Option(..., "--width"),
    height: int = typer.Option(..., "--height"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("select-rectangle")
    _ok(
        "select-rectangle",
        _call_bridge(
            "select-rectangle",
            "selection.rectangle",
            {"image": str(image), "x": x, "y": y, "width": width, "height": height, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("select-ellipse")
def select_ellipse(
    image: Path,
    x: int = typer.Option(..., "--x"),
    y: int = typer.Option(..., "--y"),
    width: int = typer.Option(..., "--width"),
    height: int = typer.Option(..., "--height"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("select-ellipse")
    _ok(
        "select-ellipse",
        _call_bridge(
            "select-ellipse",
            "selection.ellipse",
            {"image": str(image), "x": x, "y": y, "width": width, "height": height, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("invert-selection")
def invert_selection(image: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("invert-selection")
    _ok(
        "invert-selection",
        _call_bridge(
            "invert-selection",
            "selection.invert",
            {"image": str(image), "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("add-text")
def add_text(
    image: Path,
    text: str = typer.Option(..., "--text"),
    x: int = typer.Option(..., "--x"),
    y: int = typer.Option(..., "--y"),
    font: str = typer.Option("Sans", "--font"),
    size: float = typer.Option(36.0, "--size"),
    color: str = typer.Option("#ffffff", "--color"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("add-text")
    _ok(
        "add-text",
        _call_bridge(
            "add-text",
            "text.add",
            {
                "image": str(image),
                "text": text,
                "x": x,
                "y": y,
                "font": font,
                "size": size,
                "color": color,
                "layerIndex": layer_index,
                "output": str(output) if output else str(image),
            },
            timeout_seconds=300,
        ),
    )


@app.command("update-text")
def update_text(
    image: Path,
    layer_index: int = typer.Option(..., "--layer-index", "--layer-id"),
    text: str = typer.Option(..., "--text"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("update-text")
    _ok(
        "update-text",
        _call_bridge(
            "update-text",
            "text.update",
            {"image": str(image), "layerIndex": layer_index, "text": text, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("stroke-selection")
def stroke_selection(
    image: Path,
    width: float = typer.Option(..., "--width"),
    color: str = typer.Option("#ffffff", "--color"),
    layer_index: int = typer.Option(0, "--layer-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("stroke-selection")
    _ok(
        "stroke-selection",
        _call_bridge(
            "stroke-selection",
            "annotation.stroke_selection",
            {"image": str(image), "width": width, "color": color, "layerIndex": layer_index, "output": str(output) if output else str(image)},
            timeout_seconds=300,
        ),
    )


@app.command("run-macro")
def run_macro(
    image: Path,
    macro: str = typer.Option(..., "--macro"),
    params_json: str = typer.Option("{}", "--params-json"),
) -> None:
    _ensure_bridge_ready("run-macro")
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as exc:
        _fail("run-macro", "INVALID_INPUT", f"Invalid JSON: {exc}")
    _ok("run-macro", _call_bridge("run-macro", "macro.run", {"image": str(image), "macro": macro, "params": params}, timeout_seconds=600))


@app.command("list-presets")
def list_presets() -> None:
    _ok("list-presets", _call_bridge("list-presets", "preset.list", {}, timeout_seconds=30))


@app.command("apply-preset")
def apply_preset(image: Path, preset_name: str) -> None:
    _ensure_bridge_ready("apply-preset")
    _ok(
        "apply-preset",
        _call_bridge("apply-preset", "preset.apply", {"image": str(image), "preset": preset_name}, timeout_seconds=600),
    )


@app.command("version")
def version() -> None:
    _ok("version", {"packageVersion": __version__, "protocolVersion": PROTOCOL_VERSION})


def main() -> None:
    app()
