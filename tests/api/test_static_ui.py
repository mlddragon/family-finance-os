from __future__ import annotations

from fastapi.testclient import TestClient

import family_finance_os.main as main_module


def test_static_ui_route_does_not_serve_paths_outside_static_dir(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "assets").mkdir()
    (static_dir / "index.html").write_text("<html>Family Finance OS UI</html>")
    (tmp_path / "private.txt").write_text("outside static dir")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    app = main_module.create_app(data_root=tmp_path / "data", local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/%2E%2E/private.txt")

    assert response.status_code == 200
    assert response.text == "<html>Family Finance OS UI</html>"
    assert "outside static dir" not in response.text
    assert response.headers.get("cache-control") == "no-cache, must-revalidate"


def test_static_ui_shell_sets_no_cache_headers(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "assets").mkdir()
    (static_dir / "index.html").write_text("<html>Family Finance OS UI</html>")
    monkeypatch.setattr(main_module, "STATIC_DIR", static_dir)

    app = main_module.create_app(data_root=tmp_path / "data", local_bind_host="127.0.0.1")

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache, must-revalidate"
