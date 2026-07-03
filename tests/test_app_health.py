from app import app


def test_public_health_minimal():
    client = app.test_client()
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "api_version" in data
    assert "database" not in data


def test_health_detail_requires_admin():
    client = app.test_client()
    res = client.get("/health/detail")
    assert res.status_code == 403
