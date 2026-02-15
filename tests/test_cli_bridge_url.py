from pathlib import Path

from harness_gimp.cli import main as cli_main


def test_resolve_bridge_url_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_GIMP_BRIDGE_URL", "http://127.0.0.1:49999")
    assert cli_main._resolve_bridge_url() == "http://127.0.0.1:49999"


def test_resolve_bridge_url_uses_persisted_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HARNESS_GIMP_BRIDGE_URL", raising=False)
    monkeypatch.setenv("HARNESS_GIMP_STATE_DIR", str(tmp_path / ".harness-gimp"))
    state_dir = tmp_path / ".harness-gimp"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "bridge.url").write_text("http://127.0.0.1:47777", encoding="utf-8")
    assert cli_main._resolve_bridge_url() == "http://127.0.0.1:47777"
