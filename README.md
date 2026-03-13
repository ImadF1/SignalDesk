# SignalDesk

SignalDesk is an autonomous research agent that takes a topic, searches the web with Tavily, summarizes the best sources with Ollama, and writes a final markdown report using a LangGraph workflow.

Example input:

```text
Explain the AI chip market
```

What the agent does:

1. plans targeted search queries
2. searches the web with Tavily
3. collects and deduplicates sources
4. summarizes each source with Ollama
5. writes a final research report

## Features

- shows real agent orchestration with `LangGraph`
- uses live web search instead of static prompts
- demonstrates source grounding and report synthesis
- runs locally with `Ollama`
- produces reusable markdown reports
- now includes a native desktop app for topic input, live progress, source inspection, and report preview

## Stack

- Python
- LangGraph
- Ollama
- Tavily API
- Rich CLI
- Tkinter desktop UI

## Pipeline

```text
Query
  -> Query Planning
  -> Search
  -> Collect Sources
  -> LLM Summaries
  -> Final Report
```

## Project Structure

```text
signaldesk/
├─ desktop_app.py
├─ run_desktop.ps1
├─ src/ai_research_agent/
│  ├─ config.py
│  ├─ desktop_ui.py
│  ├─ graph.py
│  ├─ llm.py
│  ├─ main.py
│  ├─ models.py
│  ├─ search.py
│  └─ utils.py
├─ tests/
├─ reports/
├─ .env.example
├─ pyproject.toml
├─ requirements.txt
└─ run_agent.ps1
```

## Setup

1. Create a virtual environment.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. Start Ollama and pull a chat model.

```powershell
ollama serve
ollama pull llama3.2:latest
```

4. Add your Tavily key.

```powershell
Copy-Item .env.example .env
```

Then set:

```text
TAVILY_API_KEY=your_key_here
```

## Run

Interactive:

```powershell
python -m ai_research_agent.main
```

One-shot:

```powershell
python -m ai_research_agent.main --topic "Explain the AI chip market"
```

PowerShell launcher:

```powershell
.\run_agent.ps1 -Topic "Explain the AI chip market"
```

Desktop app:

```powershell
.\run_desktop.ps1
```

The desktop app lets you:

- enter the research topic in a native window
- paste the Tavily API key at runtime
- choose the Ollama model
- watch workflow progress live
- inspect planned queries and collected sources
- read the generated markdown report without leaving the app

SignalDesk works well for:

- market research briefs
- trend analysis
- competitor landscape reports
- fast topic explainers with cited sources

## Output

Each run writes a markdown report to `reports/` with:

- executive summary
- market structure
- trends
- competitive landscape
- risks and unknowns
- bottom line
- source links

## Environment Variables

- `TAVILY_API_KEY`
- `TAVILY_TOPIC`
- `TAVILY_SEARCH_DEPTH`
- `TAVILY_MAX_RESULTS`
- `TAVILY_TIMEOUT`
- `MAX_SEARCH_QUERIES`
- `MIN_SOURCE_COUNT`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TEMPERATURE`
- `OLLAMA_NUM_PREDICT`

## Notes

- The project uses `TavilyClient.search(...)` for retrieval.
- The workflow is built with `StateGraph` from LangGraph.
- The report is grounded in retrieved source summaries rather than a single raw prompt.
- If Tavily returns too few sources, the agent automatically expands the search with fallback queries.
- The launch scripts automatically ignore a broken local proxy such as `127.0.0.1:9` when present.
