from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from ai_research_agent.config import Settings
from ai_research_agent.models import SearchSource, SourceSummary
from ai_research_agent.utils import compact_text, fallback_queries, parse_queries


class OllamaResearchWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.ollama_temperature,
            num_predict=settings.ollama_num_predict,
        )

    def plan_queries(self, topic: str) -> list[str]:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a research planning assistant. Generate focused web search queries "
                        "that will help gather authoritative sources for a research report. "
                        "Return only short query lines, one per line, with no commentary."
                    ),
                ),
                (
                    "human",
                    (
                        "Topic: {topic}\n"
                        "Create {count} search queries that cover overview, market structure, "
                        "competition, trends, and risks."
                    ),
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        raw_output = chain.invoke({"topic": topic, "count": self.settings.max_search_queries})
        queries = parse_queries(raw_output, self.settings.max_search_queries)
        return queries or fallback_queries(topic)[: self.settings.max_search_queries]

    def summarize_source(self, topic: str, source: SearchSource) -> SourceSummary:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You summarize a single web source for a research agent. "
                        "Produce a compact summary with the most important market facts only. "
                        "Keep it under 120 words and avoid filler."
                    ),
                ),
                (
                    "human",
                    (
                        "Research topic: {topic}\n"
                        "Source ID: {source_id}\n"
                        "Title: {title}\n"
                        "URL: {url}\n"
                        "Content:\n{content}"
                    ),
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        summary = chain.invoke(
            {
                "topic": topic,
                "source_id": source.source_id,
                "title": source.title,
                "url": source.url,
                "content": compact_text(source.content, limit=2200),
            }
        ).strip()
        return SourceSummary(
            source_id=source.source_id,
            title=source.title,
            url=source.url,
            domain=source.domain,
            summary=summary,
        )

    def write_report(self, topic: str, summaries: list[SourceSummary]) -> str:
        summary_packet = "\n\n".join(
            [
                (
                    f"{item.source_id}\n"
                    f"Title: {item.title}\n"
                    f"URL: {item.url}\n"
                    f"Summary: {item.summary}"
                )
                for item in summaries
            ]
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an autonomous research analyst. Write a structured markdown report "
                        "grounded only in the provided source summaries. Use citation markers like "
                        "[S1], [S2], and include a final Sources section with the URLs. "
                        "If evidence is weak or conflicting, state that explicitly."
                    ),
                ),
                (
                    "human",
                    (
                        "Research topic: {topic}\n\n"
                        "Source summaries:\n{summary_packet}\n\n"
                        "Write a concise but recruiter-quality report with these sections:\n"
                        "# Title\n"
                        "## Executive Summary\n"
                        "## Market Structure\n"
                        "## Key Trends\n"
                        "## Competitive Landscape\n"
                        "## Risks And Unknowns\n"
                        "## Bottom Line\n"
                        "## Sources"
                    ),
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke({"topic": topic, "summary_packet": summary_packet}).strip()
