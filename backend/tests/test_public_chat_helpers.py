import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app import public_chat_helpers


def test_public_chat_helpers_are_available_via_main():
    assert main._contains_public_chat_r18_hint("R18") is True
    assert main._trim_public_character_intro("abcdef", max_chars=4) == "abc…"


def test_public_chat_r18_hint_detects_keywords():
    assert public_chat_helpers._contains_public_chat_r18_hint("R18 romance") is True
    assert public_chat_helpers._contains_public_chat_r18_hint("全年齢") is False


def test_trim_public_character_intro_adds_ellipsis():
    assert public_chat_helpers._trim_public_character_intro("abcdef", max_chars=4) == "abc…"
