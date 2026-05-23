import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import ai_source_helpers


def test_extract_title_candidates_from_source_titles_deduplicates():
    out = ai_source_helpers._extract_title_candidates_from_source_titles(
        character_name="Mina",
        sources=[
            {"title": "Sky Story | Mina", "snippet": ""},
            {"title": "Moon Tale - Hero Story", "snippet": ""},
            {"title": "Moon Tale", "snippet": ""},
        ],
        limit=5,
    )

    assert out == ["Sky Story", "Moon Tale", "Hero Story"]


def test_merge_fanfic_with_base_personality_keeps_both_sections():
    out = ai_source_helpers._merge_fanfic_with_base_personality(
        fanfic_personality="- fanfic",
        base_personality="- base",
    )

    assert "【二次創作モード補完】" in out
    assert "【元の性格設定】" in out
