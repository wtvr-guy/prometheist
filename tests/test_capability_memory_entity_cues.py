from jit_agent.capability_runtime import _deterministic_entity_cues, _merge_entities


def test_deterministic_entity_cues_extract_explicit_names():
    entities = _deterministic_entity_cues(
        "Which Project Kestrel approach conflicts with Docker Compose?",
        "Recall the codename for Project Oriole exactly.",
    )

    assert entities == ["Project Kestrel", "Docker Compose", "Project Oriole"]


def test_deterministic_entity_cues_preserve_singleton_followup_anchor():
    entities = _deterministic_entity_cues(
        "Which of those approaches conflicts with my established Kestrel rule, "
        "and what constraint profile did I give that rule?"
    )

    assert entities == ["Kestrel"]


def test_deterministic_entity_cues_are_bounded_and_deduplicated():
    entities = _deterministic_entity_cues(
        "Project Oriole and Project Oriole are the same textual cue here.",
        "Project Falcon is separate.",
    )

    assert entities == ["Project Oriole", "Project Falcon"]


def test_merge_entities_preserves_planner_entities_before_syntax_cues():
    merged = _merge_entities(
        ["Project Oriole", "VX-ABC123"],
        ["project oriole", "Docker Compose"],
    )

    assert merged == ["Project Oriole", "VX-ABC123", "Docker Compose"]
