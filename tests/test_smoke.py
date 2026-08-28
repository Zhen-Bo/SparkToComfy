import pytest


@pytest.mark.asyncio
async def test_workflows_shape(client):
    resp = await client.get("/v1/workflows")
    assert resp.status_code == 200
    body = resp.json()
    assert body and all({"id", "name", "parameters"} <= set(w) for w in body)


@pytest.mark.asyncio
async def test_history_empty_session(client):
    resp = await client.get("/v1/history", params={"sessionId": "nobody"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_generate_unknown_workflow(client):
    resp = await client.post(
        "/v1/generate", json={"workflowId": "nope", "sessionId": "s", "params": {}}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
