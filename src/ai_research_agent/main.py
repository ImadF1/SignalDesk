from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from ai_research_agent.config import normalize_proxy_environment
from ai_research_agent.graph import ResearchAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SignalDesk autonomous research agent")
    parser.add_argument("--topic", type=str, help="Research topic to investigate")
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=24,
        help="How many report lines to print to the terminal preview.",
    )
    return parser


def main() -> None:
    load_dotenv()
    normalize_proxy_environment()
    parser = build_parser()
    args = parser.parse_args()
    console = Console()

    topic = (args.topic or "").strip()
    if not topic:
        topic = console.input("[bold]Research topic[/bold]: ").strip()
    if not topic:
        raise SystemExit("A research topic is required.")

    agent = ResearchAgent()
    console.rule("[bold cyan]SignalDesk[/bold cyan]")
    console.print(f"[bold]Topic:[/bold] {topic}")
    console.print("Running LangGraph workflow: query planning -> Tavily search -> summaries -> final report")

    run = agent.run(topic)

    query_table = Table(title="Search Queries", show_header=True, header_style="bold magenta")
    query_table.add_column("#", width=4)
    query_table.add_column("Query")
    for index, query in enumerate(run.planned_queries, start=1):
        query_table.add_row(str(index), query)
    console.print(query_table)

    source_table = Table(title="Collected Sources", show_header=True, header_style="bold green")
    source_table.add_column("ID", width=5)
    source_table.add_column("Domain", width=26)
    source_table.add_column("Title")
    for source in run.sources[:8]:
        source_table.add_row(source.source_id, source.domain, source.title)
    console.print(source_table)

    report_path = Path(run.report_path)
    console.print(f"[bold]Saved report:[/bold] {report_path}")

    preview_text = "\n".join(run.report_markdown.splitlines()[: args.preview_lines])
    if preview_text.strip():
        console.rule("[bold yellow]Report Preview[/bold yellow]")
        console.print(Markdown(preview_text))


if __name__ == "__main__":
    main()
