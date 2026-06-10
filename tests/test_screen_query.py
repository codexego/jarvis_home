"""Tests de comandos de pantalla."""

from modules.screen.query_matcher import (
    build_screen_actions,
    is_screen_query,
    parse_screen_command,
)


def test_play_video_query():
    assert is_screen_query("reproduce el video")
    parsed = parse_screen_command("reproduce el video")
    assert parsed["intent"] == "play_video"


def test_search_video_query():
    q = "busca el video que tenga la frase python tutorial"
    assert is_screen_query(q)
    parsed = parse_screen_command(q)
    assert parsed["intent"] == "search_video"
    assert "python" in (parsed.get("phrase") or "").lower()


def test_non_screen_query():
    assert not is_screen_query("enciende la luz")


def test_build_play_actions():
    parsed = {"intent": "play_video", "phrase": None, "query": "reproduce el video"}
    analysis = {
        "elements": [],
        "text_lines": [],
        "context": {
            "play_target": {
                "type": "button",
                "label": "Play",
                "bbox": [100, 100, 50, 50],
                "center": [125, 125],
            },
            "scale": 1.0,
        },
    }
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    actions, answer = build_screen_actions(parsed, analysis, monitor)
    assert actions[0]["type"] == "click"
    assert "Reproduciendo" in answer
