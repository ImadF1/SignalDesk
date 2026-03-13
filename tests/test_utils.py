from __future__ import annotations

from ai_research_agent.models import SearchSource
from ai_research_agent.utils import deduplicate_sources, fallback_queries, parse_queries, slugify_topic


def test_slugify_topic_normalizes_words() -> None:
    assert slugify_topic("Explain the AI chip market") == "explain-the-ai-chip-market"


def test_parse_queries_keeps_unique_lines() -> None:
    parsed = parse_queries(
        """
        1. AI chip market overview
        2. AI chip market overview
        - AI chip competition and pricing
        """,
        limit=3,
    )
    assert parsed == [
        "AI chip market overview",
        "AI chip competition and pricing",
    ]


def test_deduplicate_sources_keeps_highest_score() -> None:
    sources = [
        SearchSource("S1", "q", "One", "https://example.com/a", "example.com", 0.41, "A"),
        SearchSource("S2", "q", "Two", "https://example.com/a", "example.com", 0.92, "B"),
        SearchSource("S3", "q", "Three", "https://example.com/b", "example.com", 0.50, "C"),
    ]
    deduped = deduplicate_sources(sources)

    assert [item.url for item in deduped] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert deduped[0].score == 0.92


def test_fallback_queries_returns_three_angles() -> None:
    queries = fallback_queries("AI chip market")

    assert len(queries) == 3
    assert all("AI chip market" in item for item in queries)
