"""Tests for REST API endpoints."""



async def test_create_case(async_client):
    """Test creating a new case via POST /api/cases."""
    resp = await async_client.post("/api/cases", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "active"
    assert data["full_transcript"] == ""
    assert data["core_info_complete"] is False
    assert data["nemsis_data"]["patient"]["patient_name_first"] is None


async def test_list_cases_empty(async_client):
    """Test listing cases when none exist."""
    resp = await async_client.get("/api/cases")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_cases_after_create(async_client):
    """Test listing cases after creating one."""
    create_resp = await async_client.post("/api/cases", json={})
    case_id = create_resp.json()["id"]

    resp = await async_client.get("/api/cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 1
    assert cases[0]["id"] == case_id
    assert cases[0]["status"] == "active"


async def test_get_case(async_client):
    """Test retrieving a single case."""
    create_resp = await async_client.post("/api/cases", json={})
    case_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == case_id
    assert data["status"] == "active"
    assert "nemsis_data" in data


async def test_get_case_not_found(async_client):
    """Test 404 for non-existent case."""
    resp = await async_client.get("/api/cases/nonexistent-id")
    assert resp.status_code == 404


async def test_get_case_nemsis(async_client):
    """Test retrieving NEMSIS data for a case."""
    create_resp = await async_client.post("/api/cases", json={})
    case_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/cases/{case_id}/nemsis")
    assert resp.status_code == 200
    data = resp.json()
    assert "patient" in data
    assert "vitals" in data
    assert "situation" in data


async def test_get_case_nemsis_not_found(async_client):
    """Test 404 for NEMSIS of non-existent case."""
    resp = await async_client.get("/api/cases/nonexistent-id/nemsis")
    assert resp.status_code == 404


async def test_get_case_transcripts_empty(async_client):
    """Test retrieving transcripts for a case with none."""
    create_resp = await async_client.post("/api/cases", json={})
    case_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/cases/{case_id}/transcripts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segments"] == []
    assert data["total"] == 0


async def test_get_transcripts_not_found(async_client):
    """Test 404 for transcripts of non-existent case."""
    resp = await async_client.get("/api/cases/nonexistent-id/transcripts")
    assert resp.status_code == 404


async def test_update_case_status(async_client):
    """Test updating case status via PATCH."""
    create_resp = await async_client.post("/api/cases", json={})
    case_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/api/cases/{case_id}", json={"status": "completed"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"

    # Verify the update persisted
    get_resp = await async_client.get(f"/api/cases/{case_id}")
    assert get_resp.json()["status"] == "completed"


async def test_update_case_not_found(async_client):
    """Test 404 for updating non-existent case."""
    resp = await async_client.patch(
        "/api/cases/nonexistent-id", json={"status": "completed"}
    )
    assert resp.status_code == 404


async def test_hospital_summary_stub(async_client):
    """Test hospital summary stub endpoint."""
    resp = await async_client.get("/api/hospital/summary/test-case-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "interface_ready"
    assert "expected_sections" in data


async def test_serve_index(async_client):
    """Test that the root serves the paramedic UI."""
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_multiple_cases_ordering(async_client):
    """Test that cases are returned in reverse chronological order."""
    ids = []
    for _ in range(3):
        resp = await async_client.post("/api/cases", json={})
        ids.append(resp.json()["id"])

    resp = await async_client.get("/api/cases")
    cases = resp.json()
    assert len(cases) == 3
    # Most recent first
    assert cases[0]["id"] == ids[2]
    assert cases[2]["id"] == ids[0]
