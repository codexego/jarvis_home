"""Tests de detección de consultas visuales."""

from modules.vision.query_matcher import interpret_vision_answer, is_vision_query


def test_spanish_hand_query():
    assert is_vision_query("qué tengo en la mano")


def test_english_hand_query():
    assert is_vision_query("what do I have in my hand")


def test_non_vision_query():
    assert not is_vision_query("enciende la luz")


def test_interpret_hand_answer():
    context = {
        "labels": ["un teléfono móvil", "una taza"],
        "primary_object": "un teléfono móvil",
        "hand_candidates": ["un teléfono móvil"],
        "summary": "un teléfono móvil, una taza",
    }
    answer = interpret_vision_answer("qué tengo en la mano", context)
    assert "teléfono" in answer


def test_interpret_empty():
    answer = interpret_vision_answer("qué ves", {"labels": [], "hand_candidates": []})
    assert "No detecto" in answer
