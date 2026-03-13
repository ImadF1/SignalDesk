from __future__ import annotations

from pathlib import Path
from typing import Callable

from langgraph.graph import END, START, StateGraph

from ai_research_agent.config import Settings, ensure_directories, get_settings
from ai_research_agent.llm import OllamaResearchWriter
from ai_research_agent.models import ResearchRun, ResearchState, SearchSource
from ai_research_agent.search import TavilyResearchSearcher
from ai_research_agent.utils import deduplicate_sources, fallback_queries, report_filename


ProgressCallback = Callable[[str, float | None], None]


class ResearchAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        ensure_directories(self.settings)
        self.searcher = TavilyResearchSearcher(self.settings)
        self.writer = OllamaResearchWriter(self.settings)
        self._progress_callback: ProgressCallback | None = None
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        builder.add_node("plan_queries", self._plan_queries)
        builder.add_node("search_web", self._search_web)
        builder.add_node("expand_search", self._expand_search)
        builder.add_node("summarize_sources", self._summarize_sources)
        builder.add_node("write_report", self._write_report)

        builder.add_edge(START, "plan_queries")
        builder.add_edge("plan_queries", "search_web")
        builder.add_conditional_edges(
            "search_web",
            self._route_after_search,
            {
                "expand_search": "expand_search",
                "summarize_sources": "summarize_sources",
            },
        )
        builder.add_edge("expand_search", "summarize_sources")
        builder.add_edge("summarize_sources", "write_report")
        builder.add_edge("write_report", END)
        return builder.compile()

    def run(self, topic: str, progress_callback: ProgressCallback | None = None) -> ResearchRun:
        self._progress_callback = progress_callback
        normalized_topic = topic.strip()
        self._notify("Starting research workflow...", 0.02)
        try:
            final_state = self.graph.invoke({"topic": normalized_topic})
            self._notify("Research complete.", 1.0)
            return ResearchRun(
                topic=normalized_topic,
                planned_queries=final_state.get("planned_queries", []),
                sources=final_state.get("sources", []),
                summaries=final_state.get("summaries", []),
                report_markdown=final_state.get("report_markdown", ""),
                report_path=final_state.get("report_path", ""),
            )
        finally:
            self._progress_callback = None

    def _plan_queries(self, state: ResearchState) -> ResearchState:
        topic = state["topic"]
        self._notify("Planning search queries...", 0.10)
        queries = self.writer.plan_queries(topic)
        return {"planned_queries": queries, "search_attempts": 1}

    def _search_web(self, state: ResearchState) -> ResearchState:
        queries = state.get("planned_queries", [])
        self._notify(f"Searching the web across {len(queries)} query angle(s)...", 0.28)
        sources = self.searcher.search_many(queries)
        self._notify(f"Collected {len(sources)} unique source(s).", 0.48)
        return {"sources": sources}

    def _route_after_search(self, state: ResearchState) -> str:
        if len(state.get("sources", [])) < self.settings.min_source_count:
            return "expand_search"
        return "summarize_sources"

    def _expand_search(self, state: ResearchState) -> ResearchState:
        topic = state["topic"]
        existing_sources = list(state.get("sources", []))
        self._notify("Too few sources found. Expanding search coverage...", 0.56)
        extra_queries = fallback_queries(topic)
        extra_sources = self.searcher.search_many(extra_queries)
        merged = self._renumber_sources(existing_sources + extra_sources)
        planned_queries = list(dict.fromkeys(state.get("planned_queries", []) + extra_queries))
        self._notify(f"Expanded search to {len(merged)} source(s).", 0.64)
        return {
            "planned_queries": planned_queries,
            "search_attempts": int(state.get("search_attempts", 1)) + 1,
            "sources": merged,
        }

    def _summarize_sources(self, state: ResearchState) -> ResearchState:
        topic = state["topic"]
        sources = state.get("sources", [])[: max(self.settings.min_source_count, 6)]
        summaries = []
        for index, source in enumerate(sources, start=1):
            progress = 0.66 + (0.20 * (index / max(len(sources), 1)))
            self._notify(f"Summarizing source {index}/{len(sources)}: {source.domain}", progress)
            summaries.append(self.writer.summarize_source(topic, source))
        return {"summaries": summaries, "sources": sources}

    def _write_report(self, state: ResearchState) -> ResearchState:
        topic = state["topic"]
        summaries = state.get("summaries", [])
        self._notify("Writing the final report...", 0.90)
        if not summaries:
            report_markdown = (
                f"# {topic}\n\n"
                "## Executive Summary\n"
                "The agent could not collect enough usable sources to produce a grounded report.\n\n"
                "## Bottom Line\n"
                "Add a valid Tavily API key, confirm internet access, and try a broader topic.\n\n"
                "## Sources\n"
                "No sources collected."
            )
        else:
            report_markdown = self.writer.write_report(topic, summaries)
        output_path = self._save_report(topic, report_markdown)
        self._notify(f"Saved report to {output_path.name}.", 0.98)
        return {
            "report_markdown": report_markdown,
            "report_path": str(output_path),
        }

    def _save_report(self, topic: str, report_markdown: str) -> Path:
        output_path = self.settings.reports_dir / report_filename(topic)
        output_path.write_text(report_markdown + "\n", encoding="utf-8")
        return output_path

    def _renumber_sources(self, sources: list[SearchSource]) -> list[SearchSource]:
        deduped = deduplicate_sources(sources)
        for index, item in enumerate(deduped, start=1):
            item.source_id = f"S{index}"
        return deduped

    def _notify(self, message: str, value: float | None) -> None:
        if self._progress_callback is not None:
            self._progress_callback(message, value)
