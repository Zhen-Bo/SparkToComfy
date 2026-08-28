"""HTTP-level checks: forms, request validation, history, images, cancel and error shape."""

import re
import uuid

import pytest
from conftest import assert_camel

from app.database import HISTORY_LIMIT, JobSubmission, now
from app.history.router import LIMIT_HEADER


@pytest.fixture
async def workflows(client):
    resp = await client.get("/v1/workflows")
    assert resp.status_code == 200, resp.status_code
    return resp.json()


@pytest.fixture
async def openapi(client):
    resp = await client.get("/v1/openapi.json")
    assert resp.status_code == 200, resp.status_code
    return resp.json()


# --- forms ---


def test_workflow_list_is_camel_and_ordered(workflows):
    assert_camel(workflows, "workflows")
    assert [w["id"] for w in workflows] == ["example"], workflows


def test_workflow_top_level_shape(workflows):
    for w in workflows:
        assert set(w) == {"id", "name", "parameters"}, w
        assert list(w["parameters"]) == ["basic", "advanced"], w


def test_workflow_advanced_sliders(workflows):
    for w in workflows:
        assert w["parameters"]["advanced"]["upscale"]["max"] == 2, w["id"]
        for cname, kind in (("steps", "int"), ("cfg", "float"), ("upscale", "float")):
            control = w["parameters"]["advanced"][cname]
            assert control["type"] == "input", (w["id"], cname, control)
            assert control["valueKind"] == kind, (w["id"], cname, control)
            assert control["display"] == "slider", (w["id"], cname, control)


def test_workflow_size_presets(workflows):
    for w in workflows:
        size = w["parameters"]["basic"]["size"]
        assert set(size) == {"type", "presets"}, (w["id"], size)
        assert list(size["presets"]) == ["square", "poster", "photo", "wallpaper"], size
        assert size["presets"]["poster"] == {
            "label": "2:3",
            "icon": "poster",
            "standard": {"width": 1024, "height": 1536},
            "highres": {"width": 1280, "height": 1920},
        }, size["presets"]["poster"]


def test_example_model_dropdown(workflows):
    model = workflows[0]["parameters"]["basic"]["model"]
    assert model["type"] == "dropdown", model
    assert model["options"]["krea2Turbo_v10_fp8.safetensors"] == {
        "label": "Krea2 Turbo FP8"
    }, model
    bf16 = model["options"]["krea2Turbo_v10_bf16.safetensors"]
    assert bf16 == {"label": "Krea2 Turbo", "disabled": True}, bf16


def test_example_advanced_controls(workflows):
    adv = workflows[0]["parameters"]["advanced"]
    assert adv["sampler"]["options"]["euler"] == "Euler", adv["sampler"]
    assert list(adv).index("scheduler") == list(adv).index("sampler") + 1, list(adv)
    sched = adv["scheduler"]
    assert set(sched["options"]) == {"normal", "simple", "beta"}, sched
    assert sched["options"]["beta"] == "Beta", sched
    assert sched["default"] == "beta", sched
    assert adv["upscale"]["default"] == 1, adv["upscale"]
    lora_options = adv["lora"]["options"]
    assert lora_options["Ps_Special_Merge_for_Krea2-v1"] == "Ps Special Merge Style", (
        lora_options
    )


# --- validation ---


async def test_generate_rejects_snake_case_body(client, example_values):
    sid = uuid.uuid4().hex
    resp = await client.post(
        "/v1/generate",
        json={"workflow_id": "example", "session_id": sid, "params": example_values},
    )
    body = resp.json()
    assert resp.status_code == 422, (resp.status_code, body)
    assert_camel(body, "generate-snake")


async def test_generate_unknown_workflow_id(client, example_values):
    sid = uuid.uuid4().hex
    resp = await client.post(
        "/v1/generate",
        json={"workflowId": "nope", "sessionId": sid, "params": example_values},
    )
    body = resp.json()
    assert resp.status_code == 404, (resp.status_code, body)
    assert_camel(body, "generate-404")


async def test_generate_rejects_bad_params(client, example_values):
    sid = uuid.uuid4().hex
    bad_cases = [
        {**example_values, "model": "nope.safetensors"},
        {**example_values, "steps": 999},
        {**example_values, "seed": -2},
        {
            **example_values,
            "size": {"preset": "nope", "highres": False, "landscape": False},
        },
        {**example_values, "size": {"preset": "square", "highres": False}},
        {
            **example_values,
            "size": {"preset": "square", "highres": False, "landscape": "yes"},
        },
        {**example_values, "size": {"width": 1280, "height": 1280}},
        {**example_values, "lora": [{"file": "nope", "strength": 1}]},
        {**example_values, "extra": 1},
        {**example_values, "positive": "x" * 3001},
        {**example_values, "negative": "x" * 501},
    ]
    for bad in bad_cases:
        resp = await client.post(
            "/v1/generate",
            json={"workflowId": "example", "sessionId": sid, "params": bad},
        )
        body = resp.json()
        assert resp.status_code == 400, (bad, resp.status_code, body)
        assert body["code"] == "bad_request", (bad, body)
        assert_camel(body, "generate-400")


async def test_generate_rejects_missing_param(client, example_values):
    sid = uuid.uuid4().hex
    missing = {k: v for k, v in example_values.items() if k != "steps"}
    resp = await client.post(
        "/v1/generate",
        json={"workflowId": "example", "sessionId": sid, "params": missing},
    )
    assert resp.status_code == 400, (resp.status_code, resp.json())


async def test_generate_rejects_disabled_model(client, example_values):
    sid = uuid.uuid4().hex
    resp = await client.post(
        "/v1/generate",
        json={
            "workflowId": "example",
            "sessionId": sid,
            "params": {**example_values, "model": "krea2Turbo_v10_bf16.safetensors"},
        },
    )
    body = resp.json()
    assert resp.status_code == 400, (resp.status_code, body)
    assert body["code"] == "bad_request", body


def test_openapi_generate_has_no_response_body(openapi):
    assert "GenerateResponse" not in openapi["components"]["schemas"], openapi[
        "components"
    ]
    gen_resp = openapi["paths"]["/generate"]["post"]["responses"]
    assert "200" not in gen_resp, gen_resp
    assert "204" in gen_resp and "content" not in gen_resp["204"], gen_resp


def test_openapi_control_type_enum(openapi):
    control_enum = openapi["components"]["schemas"]["Control"]["properties"]["type"][
        "enum"
    ]
    assert control_enum == [
        "dropdown",
        "multiline",
        "size",
        "input",
        "seed",
        "lora",
    ], control_enum


# --- history ---


def test_openapi_history_item_properties(openapi):
    hist_props = openapi["components"]["schemas"]["HistoryItem"]["properties"]
    assert set(hist_props) == {
        "workflowId",
        "promptId",
        "params",
        "images",
        "createdAt",
        "finishedAt",
    }, hist_props


async def test_history_rejects_snake_case_query(client):
    sid = uuid.uuid4().hex
    resp = await client.get("/v1/history", params={"session_id": sid})
    assert resp.status_code == 422, (resp.status_code, resp.json())


async def test_history_of_unknown_session_is_empty(client):
    sid = uuid.uuid4().hex
    resp = await client.get("/v1/history", params={"sessionId": sid})
    rows = resp.json()
    assert resp.status_code == 200 and rows == [], rows
    assert_camel(rows, "history")


async def test_history_clear_empty_session(client):
    sid = uuid.uuid4().hex
    resp = await client.delete("/v1/history", params={"sessionId": sid})
    assert resp.status_code == 204, "clearing an empty session must return 204"


async def test_history_delete_unknown_prompt_id(client):
    sid = uuid.uuid4().hex
    resp = await client.delete(
        "/v1/history", params={"sessionId": sid, "promptId": str(uuid.uuid4())}
    )
    assert resp.status_code == 404, (
        "a batch holding an unknown prompt_id must return 404"
    )


# --- images ---


async def test_image_of_unknown_prompt_is_404(client):
    bogus = uuid.uuid4().hex
    resp = await client.get(f"/v1/images/{bogus}")
    body = resp.json()
    assert resp.status_code == 404 and body["code"] == "not_found", (
        resp.status_code,
        body,
    )
    assert_camel(body, "images-404")


async def test_image_rejects_negative_index(client):
    bogus = uuid.uuid4().hex
    resp = await client.get(f"/v1/images/{bogus}", params={"index": -1})
    assert resp.status_code == 422, (resp.status_code, resp.json())


async def test_image_rejects_non_integer_index(client):
    bogus = uuid.uuid4().hex
    resp = await client.get(f"/v1/images/{bogus}", params={"index": "abc"})
    assert resp.status_code == 422, (resp.status_code, resp.json())


# --- cancel ---


async def test_cancel_rejects_snake_case_body(client):
    sid = uuid.uuid4().hex
    resp = await client.post(
        f"/v1/jobs/{uuid.uuid4()}/cancel", json={"session_id": sid}
    )
    assert resp.status_code == 422, (resp.status_code, resp.json())


async def test_cancel_unknown_job_is_404(client):
    sid = uuid.uuid4().hex
    resp = await client.post(f"/v1/jobs/{uuid.uuid4()}/cancel", json={"sessionId": sid})
    body = resp.json()
    assert resp.status_code == 404 and body["code"] == "not_found", (
        resp.status_code,
        body,
    )
    assert_camel(body, "cancel-404")


async def test_cancel_requires_session_id(client):
    resp = await client.post(f"/v1/jobs/{uuid.uuid4()}/cancel", json={})
    assert resp.status_code == 422, (resp.status_code, resp.json())


# --- errors ---

ID_RE = re.compile(r"^req_[0-9a-f]{12}$")


async def test_error_shape_and_request_id(client):
    sid = uuid.uuid4().hex
    seen_ids = set()
    bad_body = {"workflowId": "example", "sessionId": sid, "params": {}}
    cases = [
        (400, "bad_request", "POST", "/v1/generate", bad_body),
        (404, "not_found", "GET", f"/v1/images/{uuid.uuid4().hex}", None),
        (404, "not_found", "GET", "/v1/nope", None),
        (405, "method_not_allowed", "POST", "/v1/workflows", {}),
        (422, "unprocessable_content", "GET", "/v1/history", None),
    ]
    for expected, code, method, path, body in cases:
        resp = await client.request(method, path, json=body)
        payload = resp.json()
        assert resp.status_code == expected, (path, resp.status_code, payload)
        assert set(payload) == {"code", "requestId"}, payload
        assert payload["code"] == code, (path, payload)
        assert ID_RE.match(payload["requestId"]), payload
        seen_ids.add(payload["requestId"])
    assert len(seen_ids) == 5, seen_ids


async def test_cancel_of_finished_job(client, rt, example_values):
    sid = uuid.uuid4().hex
    done_pid = "done-" + uuid.uuid4().hex
    await rt.db.insert_finished(
        JobSubmission(
            prompt_id=done_pid,
            session_id=sid,
            workflow_id="example",
            params=example_values,
            created_at=now(),
        ),
        "done",
        images=[],
    )
    resp = await client.post(f"/v1/jobs/{done_pid}/cancel", json={"sessionId": sid})
    assert (resp.status_code, resp.content) == (204, b""), (
        resp.status_code,
        resp.content,
    )
    resp = await client.post(f"/v1/jobs/{done_pid}/cancel", json={"sessionId": "other"})
    assert resp.status_code == 404 and resp.json()["code"] == "not_found", (
        resp.status_code,
        resp.content,
    )


def test_openapi_cancel_has_no_response_model(openapi):
    assert "CancelResponse" not in openapi["components"]["schemas"], openapi[
        "components"
    ]


def test_openapi_parameters_are_camel(openapi):
    for path, item in openapi["paths"].items():
        for method, op in item.items():
            if method == "parameters" or not isinstance(op, dict):
                continue
            for param in op.get("parameters") or []:
                assert "_" not in param["name"], (path, method, param["name"])
        for param in item.get("parameters") or []:
            assert "_" not in param["name"], (path, param["name"])


def test_openapi_schema_properties_are_camel(openapi):
    for name, schema in openapi["components"]["schemas"].items():
        for key in schema.get("properties") or {}:
            assert "_" not in key, (name, key)


async def test_unknown_v1_path_is_json_not_html(client):
    """The SPA fallback must never swallow a path under /v1."""
    resp = await client.get("/v1/definitely-not-a-route")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_openapi_declares_the_mount_prefix(openapi):
    """Paths carry no /v1; the servers entry carries the prefix. Together they are the real URL."""
    assert openapi["servers"] == [{"url": "/v1"}], openapi.get("servers")


async def test_docs_live_under_the_api_mount(client):
    """Docs follow the API under /v1."""
    for path in ("/v1/openapi.json", "/v1/docs", "/v1/redoc"):
        resp = await client.get(path)
        assert resp.status_code == 200, (path, resp.status_code)


async def test_history_reports_its_limit(client):
    """The frontend reads its N/LIMIT display from this header instead of guessing."""
    sid = uuid.uuid4().hex
    resp = await client.get("/v1/history", params={"sessionId": sid})
    assert resp.headers[LIMIT_HEADER] == str(HISTORY_LIMIT), resp.headers


async def test_spa_serves_the_root_but_never_v1(client):
    """The mount itself isolates /v1; no reserved-prefix list is involved."""
    unknown = await client.get("/v1/definitely-not-a-route")
    assert unknown.status_code == 404, unknown.status_code
    assert unknown.headers["content-type"].startswith("application/json"), (
        unknown.headers
    )
    root = await client.get("/some/spa/route")
    assert root.status_code == 200, "a frontend route must get index.html"
    assert root.headers["content-type"].startswith("text/html"), root.headers
