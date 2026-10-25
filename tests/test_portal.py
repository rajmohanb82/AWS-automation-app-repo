import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal"))


def test_portal_security_and_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DB", str(tmp_path / "portal.db"))
    monkeypatch.setenv("DEPLOY_ENV", "production")
    import db
    importlib.reload(db)
    from http_app import create_app
    app = create_app()
    client = app.test_client()
    assert client.get("/healthz").json == {"status": "ok"}
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    # Anonymous mutation must be rejected, including before first setup.
    assert client.post("/api/aws/connect", json={"username": "intruder"}).status_code == 400
    key = db.secret_key()
    assert create_app().secret_key == key
    assert db.DB_PATH == tmp_path / "portal.db"


def test_instance_role_uses_default_chain(monkeypatch):
    monkeypatch.setenv("AWS_AUTH_MODE", "instance-role")
    import aws_connect
    calls = []
    monkeypatch.setattr(aws_connect.boto3, "Session", lambda **kw: calls.append(kw) or "session")
    assert aws_connect.base_session("ap-south-1") == "session"
    assert calls == [{"region_name": "ap-south-1"}]
