"""Checks that skip HTTP: control validation and patching, the cover allowlist, workflow reload and eta."""

import json
from unittest import mock

import httpx
import pytest
from fastapi import HTTPException

from app.comfy import client as comfy_client
from app.config import WorkflowCatalog, load_workflows
from app.database import JobSubmission, now
from app.jobs import controls
from app.jobs import eta as eta_module
from app.jobs.eta import COLD_START_SECONDS, EtaModel
from app.jobs.models import Job
from app.lora.router import get_cover


@pytest.fixture
def workflows(example_registry):
    return load_workflows(example_registry)


@pytest.fixture
def example(workflows):
    return workflows["example"]


@pytest.fixture
def values():
    return {
        "model": "krea2Turbo_v10_fp8.safetensors",
        "quality": "masterpiece",
        "positive": "1girl",
        "negative": "lowres",
        "size": {"preset": "photo", "highres": True, "landscape": False},
        "steps": 12,
        "cfg": 4.5,
        "seed": 123456789,
        "sampler": "euler",
        "scheduler": "normal",
        "upscale": 2,
        "lora": [
            {"file": "Ps_Special_Merge_for_Krea2-v1", "strength": 0.8},
            {"file": "Ps_gpt2-style_v3-krea2", "strength": 1},
        ],
    }


# --- controls ---


# What the node inputs must look like after the `values` fixture is patched into the example workflow.
# The whole map is compared at once, so a failure shows every difference instead of pointing at a single node id.
EXAMPLE_PATCHED = {
    "20735:6196": {"unet_name": "krea2Turbo_v10_fp8.safetensors"},
    "20735:6198": {
        "clip_name": "qwen3vl_4b_fp8_scaled.safetensors",
        "type": "krea2",
    },
    "20739": {"positive": "masterpiece"},
    "20740": {"positive": "1girl"},
    "20741": {"negative": "lowres"},
    "20742": {
        "steps": 12,
        "cfg": 4.5,
        "seed": 123456789,
        "sampler_name": "euler",
        "scheduler": "normal",
    },
    "20744": {"resize_type.scale": 2},
    "20753": {"anything": ["20752", 0]},
    "20755": {"custom_width": 1440, "custom_height": 1920},
    "20737": {
        "text": "",
        "loras": {
            "__value__": [
                {
                    "name": "Ps_Special_Merge_for_Krea2-v1",
                    "strength": 0.8,
                    "active": True,
                },
                {"name": "Ps_gpt2-style_v3-krea2", "strength": 1, "active": True},
            ]
        },
    },
    "20738": {
        "orinalMessage": "",
        "toggle_trigger_words": {"__value__": []},
        "trigger_words": ["20737", 2],
    },
}


def inputs_like(graph: dict, expected: dict) -> dict:
    """Narrow the graph down to the shape of expected so the two compare in one go."""
    return {
        node: {key: graph[node]["inputs"].get(key) for key in fields}
        for node, fields in expected.items()
    }


def test_patch_example_graph(example, values):
    before = json.dumps(example["graph"], sort_keys=True)
    validated = controls.validate(example["parameters"], values)
    g = controls.patch(example["graph"], example["parameters"], validated)
    assert json.dumps(example["graph"], sort_keys=True) == before, (
        "patch mutated the source graph"
    )
    assert inputs_like(g, EXAMPLE_PATCHED) == EXAMPLE_PATCHED, (
        "example patched node inputs differ"
    )


def test_patch_example_upscale_one_rewires_bypass(example, values):
    values["upscale"] = 1
    validated = controls.validate(example["parameters"], values)
    g1 = controls.patch(example["graph"], example["parameters"], validated)
    assert g1["20753"]["inputs"]["anything"] == ["20743", 0]
    assert isinstance(g1["20753"]["inputs"]["anything"][0], str)
    assert "20744" in g1 and "20752" in g1, "orphaned nodes must stay"


def test_missing_lora_gets_a_fresh_list(example, values):
    missing_lora = {k: v for k, v in values.items() if k != "lora"}
    first = controls.validate(example["parameters"], missing_lora)["lora"]
    second = controls.validate(example["parameters"], missing_lora)["lora"]
    assert first == [] and second == [], (first, second)
    assert first is not second, "a missing lora must yield a fresh list every time"


def test_unknown_control_type_rejected():
    bad_decl = {
        "basic": {"q": {"type": "nope", "node": "1", "target": "x"}},
        "advanced": {},
        "hidden": {},
    }
    with pytest.raises(RuntimeError):  # an unknown type must fail validation
        controls.validate(bad_decl, {"q": 1})
    with pytest.raises(RuntimeError):  # an unknown type must fail patching
        controls.patch({}, bad_decl, {"q": 1})


def test_all_of_type_counts(example):
    empty = {"basic": {}, "advanced": {}, "hidden": {}}
    two_lora = {
        "basic": {
            "a": {"type": "lora"},
            "b": {"type": "lora"},
        },
        "advanced": {},
        "hidden": {},
    }
    assert controls.all_of_type(empty, "lora") == []
    assert len(controls.all_of_type(example["parameters"], "lora")) == 1
    assert len(controls.all_of_type(two_lora, "lora")) == 2


def test_one_of_type_rejects_zero_or_two():
    empty = {"basic": {}, "advanced": {}, "hidden": {}}
    two_lora = {
        "basic": {
            "a": {"type": "lora"},
            "b": {"type": "lora"},
        },
        "advanced": {},
        "hidden": {},
    }
    with pytest.raises(RuntimeError):  # zero seed controls must fail
        controls.one_of_type(empty, "seed")
    with pytest.raises(RuntimeError):  # two lora controls must fail
        controls.one_of_type(two_lora, "lora")


def test_resolve_seed(example, values):
    assert controls.resolve_seed(42) == 42
    with mock.patch.object(controls, "random") as fake_random:
        fake_random.randint.side_effect = lambda lo, hi: hi
        top = controls.resolve_seed(-1)
    assert (
        controls.validate(example["parameters"], {**values, "seed": top})["seed"] == top
    )


def test_check_declaration_requires_max_length():
    bad_len = {
        "basic": {"positive": {"type": "multiline", "node": "1", "target": "x"}},
        "advanced": {},
        "hidden": {},
    }
    with pytest.raises(RuntimeError) as err:  # a missing max_length must fail
        controls.check_declaration(bad_len, "probe")
    assert "probe" in str(err.value) and "positive" in str(err.value), str(err.value)


@pytest.mark.parametrize("bad", ["1500", True, 0, -1])
def test_check_declaration_rejects_bad_max_length(bad):
    decl = {
        "basic": {
            "positive": {
                "type": "multiline",
                "node": "1",
                "target": "x",
                "max_length": bad,
            }
        },
        "advanced": {},
        "hidden": {},
    }
    with pytest.raises(RuntimeError):  # a non-positive-int max_length must fail
        controls.check_declaration(decl, "probe")


def test_load_workflows_checks_every_declaration(example_registry):
    with mock.patch.object(controls, "check_declaration") as fake_check:
        loaded = load_workflows(example_registry)
    assert [c.args[1] for c in fake_check.call_args_list] == list(loaded), (
        fake_check.call_args_list
    )


def test_load_workflows_propagates_declaration_error(example_registry):
    with mock.patch.object(
        controls, "check_declaration", side_effect=RuntimeError("boom")
    ):
        # load_workflows must propagate a failed declaration check
        with pytest.raises(RuntimeError):
            load_workflows(example_registry)


def test_declared_multiline_defaults_fit_max_length(workflows):
    for wid, wf in workflows.items():
        controls.check_declaration(wf["parameters"], wid)
        controls_all = {**wf["parameters"]["basic"], **wf["parameters"]["advanced"]}
        for cname, c in controls_all.items():
            if c["type"] == "multiline":
                assert len(c.get("default", "")) <= c["max_length"], (wid, cname)


def test_multiline_accepts_max_length_value(example, values):
    # Read the cap from the declaration.
    # Hardcoding it would stop this from testing the boundary as soon as max_length changes.
    limit = example["parameters"]["basic"]["positive"]["max_length"]
    edge = {**values, "positive": "x" * limit}
    assert (
        controls.validate(example["parameters"], edge)["positive"] == edge["positive"]
    )


# --- cover ---

COVER_LORA = "Ps_gpt2-style_v3-krea2"


def _fake_lora_manager(request: httpx.Request) -> httpx.Response:
    """Fake LoRA Manager: the listing knows this LoRA, but its cover returns 404."""
    if request.url.path.startswith("/api/lm/loras/list"):
        return httpx.Response(
            200,
            json={
                "items": [
                    {"file_name": COVER_LORA, "preview_url": "/api/lm/preview/x.png"}
                ],
                "total_pages": 1,
            },
        )
    return httpx.Response(404)


@pytest.fixture
def lora_manager_rt(rt):
    """Swap the runtime comfy client for the fake LoRA Manager."""
    rt.ctx.comfy = comfy_client.ComfyClient(
        "http://lora-manager.test", transport=httpx.MockTransport(_fake_lora_manager)
    )
    return rt


async def test_cover_rejects_lora_outside_config(rt):
    with pytest.raises(HTTPException) as err:  # a name outside the config must 404
        await get_cover("not-in-config", rt)
    assert err.value.status_code == 404, err.value.status_code


async def test_cover_maps_upstream_404(lora_manager_rt):
    with pytest.raises(HTTPException) as err:  # an upstream 404 must be caught
        await get_cover(COVER_LORA, lora_manager_rt)
    assert (err.value.status_code, err.value.detail) == (404, "not_found"), (
        err.value.status_code,
        err.value.detail,
    )


# --- reload ---


def test_reload_workflows_swaps_the_object(example_registry):
    catalog = WorkflowCatalog(example_registry)
    old = catalog.all()
    catalog.reload()
    assert catalog.all() is not old, "reload did not swap in a new object"
    assert set(catalog.all()) == set(old), (set(catalog.all()), set(old))


# --- eta ---


@pytest.fixture
def eta():
    return EtaModel()


@pytest.fixture
def eta_job():
    return Job(
        submission=JobSubmission(
            prompt_id="eta-probe",
            session_id="eta",
            workflow_id="eta-probe",
            params={},
            created_at=now(),
        ),
        ip="0.0.0.0",
        size_key=("eta-probe", 1024 * 1024),
        dims=(1024, 1024),
        upscale=1,
    )


def test_eta_cold_start_without_samples(eta, eta_job):
    cold = eta.expected(eta_job)
    assert cold == COLD_START_SECONDS, cold


def test_eta_forget_leaves_no_sample(eta, eta_job):
    with mock.patch.object(eta_module, "time") as fake_time:
        fake_time.monotonic.side_effect = [0.0, 99.0]
        eta.start(eta_job.prompt_id)
        eta.forget(eta_job.prompt_id)
        eta.finish(eta_job)
    assert eta.expected(eta_job) == COLD_START_SECONDS, "forget must leave no sample"


def test_eta_finish_records_sample(eta, eta_job):
    with mock.patch.object(eta_module, "time") as fake_time:
        fake_time.monotonic.side_effect = [0.0, 12.0]
        eta.start(eta_job.prompt_id)
        eta.finish(eta_job)
    assert eta.expected(eta_job) == 12.0, eta.expected(eta_job)


# --- WebSocket protocol contract: the generated file must track the schema ---


def test_ws_contract_is_fresh():
    """Fails when the schema changed and the codegen was not rerun.

    Fix with: uv run python scripts/gen_ws_contract.py
    """
    from scripts.gen_ws_contract import OUT, render

    assert OUT.read_text(encoding="utf-8") == render(), (
        "ws-contract.generated.js is stale, rerun scripts/gen_ws_contract.py"
    )


def test_ws_contract_covers_every_job_status():
    """The list of terminal states exists once: the Literals in schemas."""
    from app.ws.schemas import JOB_STATUSES

    assert set(JOB_STATUSES) == {"queued", "running", "done", "error", "cancelled"}, (
        JOB_STATUSES
    )
