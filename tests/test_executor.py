"""Tests del módulo executor."""

from modules.executor.command_parser import (
    build_executor_actions,
    is_confirmation,
    is_executor_query,
    parse_executor_command,
)
from modules.executor.security import partition_actions, requires_confirmation


def test_open_youtube():
    assert is_executor_query("abre YouTube")
    parsed = parse_executor_command("abre YouTube")
    actions, answer = build_executor_actions(parsed)
    assert actions[0]["type"] == "open_url"
    assert "youtube" in actions[0]["url"]


def test_resume_video():
    parsed = parse_executor_command("reanuda el video")
    actions, _ = build_executor_actions(parsed)
    assert actions[0]["type"] == "resume_video"


def test_write_code_vscode():
    parsed = parse_executor_command("escribe codigo en vs code: print('hola')")
    actions, answer = build_executor_actions(parsed)
    assert any(a["type"] == "type_code" for a in actions)
    assert "vs code" in answer.lower() or "codigo" in answer.lower()


def test_security_whitelisted_url():
    safe, pending = partition_actions(
        [{"type": "open_url", "url": "https://www.youtube.com"}],
        auto_confirm=False,
    )
    assert len(safe) == 1
    assert len(pending) == 0


def test_security_unknown_app_needs_confirm():
    safe, pending = partition_actions(
        [{"type": "open_app", "app": "unknown_app_xyz", "command": "xyz"}],
        auto_confirm=False,
    )
    assert len(safe) == 0
    assert len(pending) == 1


def test_shell_always_needs_confirm():
    assert requires_confirmation({"type": "shell", "command": "rm -rf /"})


def test_voice_confirm():
    assert is_confirmation("si confirmar")
    assert not is_confirmation("abre youtube")


def test_learn_command():
    parsed = parse_executor_command("cuando diga trabajo, abre vscode")
    assert parsed["intent"] == "learn_command"
    assert parsed["trigger"] == "trabajo"
    actions, answer = build_executor_actions(parsed)
    assert not actions
    assert "Aprendido" in answer
