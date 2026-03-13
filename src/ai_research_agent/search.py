from __future__ import annotations

from tavily import TavilyClient

from ai_research_agent.config import Settings
from ai_research_agent.models import SearchSource
from ai_research_agent.utils import compact_text, deduplicate_sources, extract_domain


class TavilyResearchSearcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is missing. Add it to your environment or .env file.")
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    def search(self, query: str) -> list[SearchSource]:
        response = self.client.search(
            query=query,
            topic=self.settings.tavily_topic,
            search_depth=self.settings.tavily_search_depth,
            max_results=self.settings.tavily_max_results,
            include_raw_content="markdown",
            include_answer=False,
            timeout=self.settings.tavily_timeout,
        )
        sources: list[SearchSource] = []
        for index, item in enumerate(response.get("results", []), start=1):
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            title = str(item.get("title", "")).strip() or extract_domain(url)
            body = str(item.get("raw_content") or item.get("content") or "").strip()
            sources.append(
                SearchSource(
                    source_id=f"S{index}",
                    query=query,
                    title=title,
                    url=url,
                    domain=extract_domain(url),
                    score=float(item.get("score", 0.0) or 0.0),
                    content=compact_text(body, limit=3200),
                    published_date=item.get("published_date"),
                )
            )
        return sources

    def search_many(self, queries: list[str]) -> list[SearchSource]:
        collected: list[SearchSource] = []
        for query in queries:
            collected.extend(self.search(query))
        deduped = deduplicate_sources(collected)
        for index, source in enumerate(deduped, start=1):
            source.source_id = f"S{index}"
        return deduped
