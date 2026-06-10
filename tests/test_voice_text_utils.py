"""Tests de limpieza de texto de voz."""

from modules.voice.text_utils import clean_command_text


def test_removes_wake_word_prefix():
    assert clean_command_text("Jarvis enciende la luz") == "enciende la luz"


def test_removes_wake_word_with_punctuation():
    assert clean_command_text("jarvis, what time is it") == "what time is it"


def test_empty_after_wake_only():
    assert clean_command_text("Jarvis") == ""


def test_normalizes_whitespace():
    assert clean_command_text("jarvis   turn   on   lights") == "turn on lights"
