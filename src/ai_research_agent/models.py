from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


@dataclass(slots=True)
class SearchSource:
    source_id: str
    query: str
    title: str
    url: str
    domain: str
    score: float
    content: str
    published_date: str | None = None


@dataclass(slots=True)
class SourceSummary:
    source_id: str
    title: str
    url: str
    domain: str
    summary: str


@dataclass(slots=True)
class ResearchRun:
    topic: str
    planned_queries: list[str]
    sources: list[SearchSource] = field(default_factory=list)
    summaries: list[SourceSummary] = field(default_factory=list)
    report_markdown: str = ""
    report_path: str = ""


class ResearchState(TypedDict, total=False):
    topic: str
    planned_queries: list[str]
    search_attempts: int
    sources: list[SearchSource]
    summaries: list[SourceSummary]
    report_markdown: str
    report_path: str
