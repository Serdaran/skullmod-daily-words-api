from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.deps import get_db
from app.main import app
from app.models import DailyWord, NFCScanLog, PhysicalSkull


def make_test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    return TestClient(app), engine


def test_root_healthcheck():
    client, _ = make_test_client()

    try:
        response = client.get("/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "SkullMod Daily Words API",
    }


def test_register_returns_token_and_user_id():
    client, _ = make_test_client()

    try:
        response = client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 20
    assert isinstance(body["user_id"], str)


def test_register_with_email_then_login_returns_working_token():
    client, _ = make_test_client()

    try:
        register_response = client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
                "email": "Deniz@example.com",
                "password": "strongpass123",
            },
        )
        login_response = client.post(
            "/api/v1/login",
            json={
                "email": "deniz@example.com",
                "password": "strongpass123",
            },
        )
        token = login_response.json()["token"]
        daily_response = client.get(
            "/api/v1/daily-words",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert register_response.status_code == 200
    assert login_response.status_code == 200
    assert login_response.json()["success"] is True
    assert daily_response.status_code == 200
    assert daily_response.json()["success"] is True


def test_register_rejects_duplicate_email_and_short_password():
    client, _ = make_test_client()
    payload = {
        "first_name": "DENIZ",
        "last_name": "KAYA",
        "birth_date": "1990-08-17T14:30:00",
        "birth_place": "Izmir, Turkiye",
        "email": "deniz@example.com",
        "password": "strongpass123",
    }

    try:
        first_response = client.post("/api/v1/register", json=payload)
        duplicate_response = client.post("/api/v1/register", json=payload)
        short_password_response = client.post(
            "/api/v1/register",
            json={**payload, "email": "short@example.com", "password": "short"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 409
    assert short_password_response.status_code == 400


def test_login_rejects_wrong_password():
    client, _ = make_test_client()

    try:
        client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
                "email": "deniz@example.com",
                "password": "strongpass123",
            },
        )
        response = client.post(
            "/api/v1/login",
            json={
                "email": "deniz@example.com",
                "password": "wrongpass123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_daily_words_requires_token():
    client, _ = make_test_client()

    try:
        response = client.get("/api/v1/daily-words")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_register_then_daily_words_returns_expected_contract():
    client, _ = make_test_client()

    try:
        register_response = client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
            },
        )
        token = register_response.json()["token"]

        daily_response = client.get(
            "/api/v1/daily-words",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    body = daily_response.json()

    assert daily_response.status_code == 200
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["date"] == date.today().isoformat()
    assert isinstance(body["data"]["word1"], str)
    assert isinstance(body["data"]["word2"], str)
    assert isinstance(body["data"]["motto"], str)
    assert body["data"]["word1"]
    assert body["data"]["word2"]
    assert body["data"]["motto"]


def test_daily_words_supports_english_language():
    client, _ = make_test_client()

    try:
        register_response = client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
            },
        )
        token = register_response.json()["token"]

        english_response = client.get(
            "/api/v1/daily-words?lang=en",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    body = english_response.json()

    assert english_response.status_code == 200
    assert body["success"] is True
    assert body["data"]["language"] == "en"
    assert "Bugün" not in body["data"]["motto"]
    assert "Today" in body["data"]["motto"] or "today" in body["data"]["motto"]


def test_daily_energy_is_deterministic_for_same_person_same_day():
    client, _ = make_test_client()
    payload = {
        "first_name": "DENIZ",
        "last_name": "KAYA",
        "birth_date": "1990-08-17T14:30:00",
        "birth_place": "Izmir, Turkiye",
    }

    try:
        first_token = client.post("/api/v1/register", json=payload).json()["token"]
        second_token = client.post("/api/v1/register", json=payload).json()["token"]

        first_daily = client.get(
            "/api/v1/daily-words",
            headers={"Authorization": f"Bearer {first_token}"},
        ).json()
        second_daily = client.get(
            "/api/v1/daily-words",
            headers={"Authorization": f"Bearer {second_token}"},
        ).json()
    finally:
        app.dependency_overrides.clear()

    assert first_daily["data"]["word1"] == second_daily["data"]["word1"]
    assert first_daily["data"]["word2"] == second_daily["data"]["word2"]
    assert first_daily["data"]["motto"] == second_daily["data"]["motto"]


def test_daily_words_cache_creates_one_record_per_user_per_day():
    client, engine = make_test_client()

    try:
        token = client.post(
            "/api/v1/register",
            json={
                "first_name": "DENIZ",
                "last_name": "KAYA",
                "birth_date": "1990-08-17T14:30:00",
                "birth_place": "Izmir, Turkiye",
            },
        ).json()["token"]

        headers = {"Authorization": f"Bearer {token}"}
        first_response = client.get("/api/v1/daily-words", headers=headers)
        second_response = client.get("/api/v1/daily-words", headers=headers)

        with Session(engine) as session:
            records = session.exec(select(DailyWord)).all()
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["data"] == second_response.json()["data"]
    assert len(records) == 1


def register_test_user(client, first_name="DENIZ"):
    return client.post(
        "/api/v1/register",
        json={
            "first_name": first_name,
            "last_name": "KAYA",
            "birth_date": "1990-08-17T14:30:00",
            "birth_place": "Izmir, Turkiye",
        },
    ).json()["token"]


def create_test_artifact(engine, public_token="public-token-001"):
    with Session(engine) as session:
        artifact = PhysicalSkull(
            artifact_code="SKM-000001",
            public_token=public_token,
            claim_token="claim-token-001",
            production_batch="TEST-BATCH",
            artifact_type="prototype",
            material_type="prototype",
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        return artifact


def test_nfc_status_recognizes_unclaimed_artifact_and_logs_scan():
    client, engine = make_test_client()
    create_test_artifact(engine)

    try:
        response = client.get("/api/v1/nfc/public-token-001")

        with Session(engine) as session:
            artifact = session.exec(select(PhysicalSkull)).first()
            logs = session.exec(select(NFCScanLog)).all()
    finally:
        app.dependency_overrides.clear()

    body = response.json()

    assert response.status_code == 200
    assert body["valid"] is True
    assert body["artifact_code"] == "SKM-000001"
    assert body["claim_status"] == "unclaimed"
    assert body["requires_auth"] is True
    assert body["owner_match"] is None
    assert artifact.scan_count == 1
    assert len(logs) == 1
    assert logs[0].event_type == "first_scan"


def test_nfc_claim_binds_artifact_to_current_user_and_lists_collection():
    client, engine = make_test_client()
    create_test_artifact(engine)

    try:
        token = register_test_user(client)
        claim_response = client.post(
            "/api/v1/nfc/public-token-001/claim",
            headers={"Authorization": f"Bearer {token}"},
        )
        status_response = client.get(
            "/api/v1/nfc/public-token-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        collection_response = client.get(
            "/api/v1/me/artifacts",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert claim_response.status_code == 200
    assert claim_response.json()["success"] is True
    assert claim_response.json()["claim_status"] == "claimed"
    assert status_response.json()["owner_match"] is True
    assert collection_response.status_code == 200
    assert collection_response.json()[0]["artifact_code"] == "SKM-000001"


def test_nfc_claim_is_idempotent_for_owner_and_rejects_other_user():
    client, engine = make_test_client()
    create_test_artifact(engine)

    try:
        owner_token = register_test_user(client, first_name="DENIZ")
        other_token = register_test_user(client, first_name="MERT")

        first_claim = client.post(
            "/api/v1/nfc/public-token-001/claim",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        owner_second_claim = client.post(
            "/api/v1/nfc/public-token-001/claim",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        other_claim = client.post(
            "/api/v1/nfc/public-token-001/claim",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        other_status = client.get(
            "/api/v1/nfc/public-token-001",
            headers={"Authorization": f"Bearer {other_token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first_claim.status_code == 200
    assert owner_second_claim.status_code == 200
    assert other_claim.status_code == 409
    assert other_status.json()["owner_match"] is False


def test_nfc_invalid_token_returns_safe_response():
    client, engine = make_test_client()

    try:
        response = client.get("/api/v1/nfc/not-a-real-token")

        with Session(engine) as session:
            logs = session.exec(select(NFCScanLog)).all()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert len(logs) == 1
    assert logs[0].event_type == "invalid_token"
