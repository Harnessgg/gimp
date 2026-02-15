from pathlib import Path

from harness_gimp.bridge import operations
from PIL import Image


def test_actions_contains_core_methods() -> None:
    data = operations.handle_method("system.actions", {})
    actions = data["actions"]
    assert "image.resize" in actions
    assert "filter.gaussian_blur" in actions
    assert "macro.run" in actions


def test_clone_project(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("hello", encoding="utf-8")
    out = operations.handle_method("image.clone", {"source": str(src), "target": str(dst)})
    assert dst.read_text(encoding="utf-8") == "hello"
    assert out["target"] == str(dst)


def test_preset_list() -> None:
    out = operations.handle_method("preset.list", {})
    assert "thumbnail" in out["presets"]


def test_run_action_uses_batch_runner(monkeypatch) -> None:
    called = {}

    def fake_run(code: str, timeout_seconds: float = 0, gimp_bin=None):  # noqa: ANN001
        called["seen"] = "gimp-image-scale" in code
        return {"ok": True}

    monkeypatch.setattr(operations, "run_python_batch", fake_run)
    out = operations._run_action("resize", {"image": "x.png", "width": 1, "height": 1, "output": "y.png"})
    assert called["seen"] is True
    assert out["ok"] is True


def test_curves_accepts_xy_pairs(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_text("x", encoding="utf-8")

    def fake_run_action(action: str, payload: dict, timeout_seconds: float = 0):  # noqa: ANN001
        return {"action": action, "payload": payload}

    monkeypatch.setattr(operations, "_run_action", fake_run_action)
    out = operations.handle_method(
        "adjust.curves",
        {"image": str(image), "points": [[0, 0], [255, 255]], "channel": "value"},
    )
    assert out["action"] == "curves"
    assert out["payload"]["points"] == [[0, 0], [255, 255]]


def test_layer_id_alias_is_supported(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "image.xcf"
    image.write_text("x", encoding="utf-8")
    calls = []

    def fake_run_action(action: str, payload: dict, timeout_seconds: float = 0):  # noqa: ANN001
        calls.append((action, payload))
        return {"ok": True}

    monkeypatch.setattr(operations, "_run_action", fake_run_action)
    operations.handle_method("mask.add", {"image": str(image), "layerId": 3, "mode": "WHITE"})
    operations.handle_method("mask.apply", {"image": str(image), "layerId": 4})
    operations.handle_method("text.update", {"image": str(image), "layerId": 5, "text": "x"})

    assert calls[0][0] == "mask_add"
    assert calls[0][1]["layerIndex"] == 3
    assert calls[1][0] == "mask_apply"
    assert calls[1][1]["layerIndex"] == 4
    assert calls[2][0] == "text_update"
    assert calls[2][1]["layerIndex"] == 5


def test_montage_grid_composes_tiles(tmp_path: Path) -> None:
    sources = []
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for i, color in enumerate(colors):
        p = tmp_path / f"src_{i}.png"
        Image.new("RGB", (20, 10), color).save(p)
        sources.append(str(p))

    out = tmp_path / "grid.png"
    result = operations.handle_method(
        "image.montage_grid",
        {
            "images": sources,
            "rows": 2,
            "cols": 2,
            "tileWidth": 20,
            "tileHeight": 10,
            "gutter": 0,
            "background": "#000000",
            "fitMode": "cover",
            "output": str(out),
        },
    )
    assert out.exists()
    image = Image.open(out)
    assert image.size == (40, 20)
    assert result["rows"] == 2
    assert result["cols"] == 2


def test_crop_center_uses_inspected_dimensions(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "img.png"
    image.write_text("x", encoding="utf-8")
    seen = []

    def fake_run_action(action: str, payload: dict, timeout_seconds: float = 0):  # noqa: ANN001
        seen.append((action, payload))
        if action == "inspect":
            return {"width": 1000, "height": 800}
        return {"ok": True, **payload}

    monkeypatch.setattr(operations, "_run_action", fake_run_action)
    out = operations.handle_method("image.crop_center", {"image": str(image), "width": 400, "height": 200})
    assert seen[0][0] == "inspect"
    assert seen[1][0] == "crop"
    assert seen[1][1]["x"] == 300
    assert seen[1][1]["y"] == 300
    assert out["ok"] is True


def test_doctor_verbose_includes_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(operations, "resolve_gimp_binary", lambda: tmp_path / "gimp.exe")
    monkeypatch.setattr(operations, "resolve_profile_dir", lambda: tmp_path / "profile")

    class DummyProc:
        returncode = 0
        stdout = "gimp 3.x"
        stderr = ""

    monkeypatch.setattr(operations.subprocess, "run", lambda *args, **kwargs: DummyProc())
    out = operations.handle_method("system.doctor", {"verbose": True})
    assert out["healthy"] is True
    assert "runtime" in out
    assert "pythonExecutable" in out["runtime"]
