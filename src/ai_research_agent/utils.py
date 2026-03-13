from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from ai_research_agent.models import SearchSource


def slugify_topic(topic: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.strip().lower()).strip("-")
    return slug or "research-topic"


def report_filename(topic: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{slugify_topic(topic)}.md"


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return domain.removeprefix("www.")


def compact_text(value: str, limit: int = 2600) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def fallback_queries(topic: str) -> list[str]:
    return [
        f"{topic} market overview",
        f"{topic} market size competitors trends",
        f"{topic} risks outlook investment landscape",
    ]


def parse_queries(raw_text: str, limit: int) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        cleaned = cleaned.strip('"')
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(cleaned)
        if len(queries) >= limit:
            break
    return queries


def deduplicate_sources(sources: list[SearchSource], limit: int | None = None) -> list[SearchSource]:
    ranked = sorted(sources, key=lambda item: item.score, reverse=True)
    unique: list[SearchSource] = []
    seen_urls: set[str] = set()
    for source in ranked:
        key = source.url.rstrip("/")
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append(source)
        if limit is not None and len(unique) >= limit:
            break
    return unique
