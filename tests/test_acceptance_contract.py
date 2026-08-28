import inspect

import tests.test_acceptance_conversation_continuity as continuity


def test_continuity_acceptance_does_not_export_keyword_slot_parser():
    assert not hasattr(continuity, "_contains_answer_slots")


def test_continuity_acceptance_scores_final_responder_handoff_not_canned_prose():
    source = inspect.getsource(
        continuity.test_stateless_four_turn_continuity_survives_sessions_and_distractors
    )

    assert source.count("assert_final_responder_has(") == 4
    assert ".strip() ==" not in source
    assert "Return exactly" not in source
    assert "ResponseSurfaceMode.NATURAL_LANGUAGE" in source
    assert "_print_turn(1" in source
    assert "_print_turn(4" in source
    assert "_contains_answer_slots" not in source
