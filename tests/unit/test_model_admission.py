from datetime import datetime, timedelta, timezone

import httpx
import pytest

from prometheist.attention_observation import HostResourceMetrics, build_resource_observation, discover_local_execution_resources
from prometheist.gui_config import AppSettings, ModelSelection, SpecialistModel, TaskRoutingSettings
from prometheist.model_admission import assess_model, classify_task, plan_task, read_model_evidence, resource_policy

AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def observation(settings=None, *, free=12288, total=16384, cpu=10, healthy=True):
    policy = resource_policy(settings or AppSettings())
    metrics = HostResourceMetrics(platform="test", logical_cpu_count=8, cpu_utilization_percent=cpu,
                                  memory_total_mib=total, memory_available_mib=free) if healthy else None
    return build_resource_observation(scheduler_cycle=1, captured_at=AT, policy=policy, metrics=metrics,
        resources=discover_local_execution_resources(metrics, policy=policy), reservations=[])


def evidence(name="default", *, weights=2048):
    return {"installed": {"name": name, "size": weights * 1024 * 1024, "digest": "digest-" + name},
            "details": {"capabilities": ["completion"], "model_info": {"general.architecture": "qwen3",
                "qwen3.context_length": 32768, "qwen3.block_count": 24, "qwen3.embedding_length": 2048,
                "qwen3.attention.head_count": 16, "qwen3.attention.head_count_kv": 4}}}


def check(settings=None, record=None, host=None, *, at=AT, selection=None, task="general"):
    settings = settings or AppSettings(selection=ModelSelection(model="default"))
    record = record or evidence()
    return assess_model(settings, selection or settings.selection, record["installed"], record["details"],
                        host or observation(settings), at=at, task=task)


def test_pure_replay_explicit_context_and_cost_components():
    first = check()
    assert first == check()
    assert first.status == "eligible"
    assert first.required_memory_mib == 3456
    assert first.components == {"weights_mib": 2048, "kv_mib": 384, "buffers_mib": 512, "worker_mib": 512}
    assert first.effective_selection.parameters == {"num_ctx": 4096, "num_gpu": 0, "num_batch": 128, "num_thread": 1, "keep_alive": 0}
    larger = check(selection=ModelSelection(model="default", parameters={"num_ctx": 32768}))
    assert larger.required_memory_mib > first.required_memory_mib
    assert larger.effective_selection.parameters["num_ctx"] == 32768
    assert check(selection=ModelSelection(model="default", parameters={"num_ctx": 65536})).status == "unsupported"


def test_host_changes_unknowns_and_gpu_are_not_optimistically_admitted():
    assert check(host=observation(free=2500)).status == "temporarily_blocked"
    assert check(host=observation(cpu=99)).status == "temporarily_blocked"
    assert check(host=observation(free=4000, total=4000)).status == "unsupported"
    assert check(host=observation(healthy=False)).status == "unverified"
    assert check(at=AT + timedelta(minutes=1)).status == "unverified"
    unknown = evidence()
    unknown["details"]["model_info"]["general.architecture"] = "unregistered-hybrid"
    assert check(record=unknown).status == "unverified"
    incomplete = evidence()
    del incomplete["details"]["model_info"]["qwen3.attention.head_count_kv"]
    assert check(record=incomplete).status == "unverified"
    assert check(selection=ModelSelection(model="default", parameters={"num_gpu": -1})).status == "unverified"
    assert check(selection=ModelSelection(model="default", parameters={"num_batch": 512})).status == "unverified"
    non_text = evidence()
    non_text["details"]["capabilities"] = ["embedding"]
    assert check(record=non_text).status == "unsupported"
    # Modality support is distinct from having an image transport in this pipeline.
    visual = evidence()
    visual["details"]["capabilities"].append("vision")
    assert check(record=visual, task="vision").status == "unsupported"


def configured(*names, **kwargs):
    return AppSettings(selection=ModelSelection(model="default"), task_routing=TaskRoutingSettings(
        specialists=[SpecialistModel(selection=ModelSelection(model=name), tasks=["coding"]) for name in names]), **kwargs)


def test_installed_specialist_order_is_stable_and_stage_pin_wins():
    records = {name + ":latest": evidence(name) for name in ("default", "alpha", "zeta")}
    a, b = configured("zeta", "alpha"), configured("alpha", "zeta")
    one = plan_task(a, "/code fix this", "auto", records, observation(), at=AT)
    two = plan_task(b, "/code fix this", "auto", dict(reversed(list(records.items()))), observation(), at=AT)
    assert one.status == two.status == "eligible"
    assert one.stages == two.stages
    assert one.stages["V2_RESPOND"].model == "alpha"
    assert one.stages["V2_EVIDENCE_POLICY"].model == "default"
    pinned = configured("alpha", routes={"V2_RESPOND": ModelSelection(model="zeta")})
    three = plan_task(pinned, "```python\nx=1\n```", "auto", records, observation(), at=AT)
    assert three.stages["V2_RESPOND"].model == "zeta"
    assert "precedence" in three.route_reason


def test_default_fallback_search_offer_and_combined_route_budget():
    settings = configured("missing", "large")
    records = {"default:latest": evidence(), "large:latest": evidence("large", weights=6144)}
    review = plan_task(settings, "write a function", "coding", records, observation(), at=AT)
    assert review.status == "needs_choice"
    assert review.fallback_steps == ["catalog_search", "openai_review", "local_default"]
    assert review.openai_offer
    plan = plan_task(settings, "write a function", "coding", records, observation(), at=AT, fallback="default")
    assert plan.status == "eligible"
    assert plan.stages["V2_RESPOND"].model == "default"
    assert "Combined" not in plan.reasons[0]
    assert "other stage" in plan.routing_exclusions["large"]
    assert "not installed" in plan.routing_exclusions["missing"]
    assert not plan.openai_offer
    blocked = plan_task(settings, "write a function", "coding", records, observation(free=2200), at=AT, fallback="default")
    assert blocked.status == "temporarily_blocked" and blocked.openai_offer
    assert blocked.specialist_offer


def test_remote_host_is_not_measured_as_local_and_never_selected_implicitly():
    remote = AppSettings(ollama_url="https://models.example", selection=ModelSelection(model="remote"))
    assert check(settings=remote).status == "remote"
    assert check(settings=remote).required_memory_mib == 512
    cloud = AppSettings(selection=ModelSelection(provider="openai", model="gpt-5"))
    assert check(settings=cloud).status == "remote"
    with pytest.raises(ValueError, match="local Ollama"):
        SpecialistModel(selection=cloud.selection, tasks=["coding"])
    assert classify_task("can you help", "auto")[0] == "general"
    assert classify_task("/code solve this", "general")[0] == "general"


def test_missing_model_discovery_never_downloads(monkeypatch):
    from prometheist import gui_models
    requests = []
    monkeypatch.setattr(gui_models, "ollama_request", lambda *args, **kwargs: requests.append((args, kwargs)) or {"models": []})
    result = read_model_evidence(AppSettings(), [ModelSelection(model="not-installed")])
    assert result["not-installed:latest"]["installed"] is None
    assert [args[1] for args, _ in requests] == ["/api/tags"]


def test_specialist_catalog_is_fixed_bounded_sorted_and_consent_gated(monkeypatch, tmp_path):
    from prometheist import gui_models
    from prometheist.network_consent import NetworkPurpose, consent_proposal, grant_consent
    from prometheist.environment_contracts import content_digest
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path))
    page = '''<a href="/library/zeta"><p>Coding assistant</p><span class="rounded-md">3b</span></a>
              <a href="/library/alpha"><p>Code generation</p><span class="rounded-md">1.5b</span></a>
              <a href="/library/remote"><p>Coder</p><span class="rounded-md">cloud</span></a>
              <a href="/library/irrelevant"><p>Weather model</p></a>'''
    requests = []
    real_client = httpx.Client
    def handle(request):
        requests.append(request)
        return httpx.Response(200, text=page)
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(PermissionError):
        gui_models.search_specialists("coding")
    assert requests == []
    proposal = consent_proposal(gui_models.CATALOG_ORIGIN, NetworkPurpose.MODEL_CATALOG)
    grant_consent(gui_models.CATALOG_ORIGIN, NetworkPurpose.MODEL_CATALOG, accepted_digest=content_digest(proposal), root=tmp_path)
    result = gui_models.search_specialists("coding")
    assert [item["name"] for item in result["models"]] == ["alpha", "zeta"]
    assert str(requests[0].url) == "https://ollama.com/search?q=coder"
    assert result["openai_offer"]
    assert all(request.method == "GET" for request in requests)
    visual = gui_models.search_specialists("vision")
    assert visual["models"] == []  # cannot trust the remote filter alone
    assert str(requests[-1].url) == "https://ollama.com/search?q=&c=vision"


def test_worker_records_choice_without_starting_cognition(monkeypatch, tmp_path):
    import json
    from prometheist import db, gui_worker, imprinting, model_admission
    settings = configured()
    plan = plan_task(settings, "code task", "coding", {"default:latest": evidence()}, observation(), at=AT)
    assert plan.status == "needs_choice"
    (tmp_path / "job.json").write_text(json.dumps({"action":"chat", "payload":{"text":"code task", "task":"coding"}}))
    monkeypatch.setattr(gui_worker, "job_settings", lambda: settings)
    monkeypatch.setattr(imprinting, "activate_imprint", lambda profile: None)
    monkeypatch.setattr(model_admission, "prepare_task", lambda *args, **kwargs: plan)
    def forbidden():
        raise AssertionError("No cognitive transaction may start while a fallback choice is required")
    monkeypatch.setattr(db, "get_connection", forbidden)
    with pytest.raises(ValueError, match="Choose a fallback"):
        gui_worker.run(tmp_path, tmp_path / "profile.json")
    assert json.loads((tmp_path / "admission.json").read_text())["status"] == "needs_choice"
    assert not (tmp_path / "effective-settings.json").exists()


def test_inventory_outage_yields_reviewable_fallback_instead_of_download(monkeypatch):
    from prometheist import gui_models
    def unavailable(endpoint):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(gui_models, "installed_models", unavailable)
    settings = configured()
    records = read_model_evidence(settings, [settings.selection])
    plan = plan_task(settings, "hello", "general", records, observation(), at=AT)
    assert plan.status == "needs_choice"
    assert plan.assessments[0].status == "unverified"
    assert plan.openai_offer
