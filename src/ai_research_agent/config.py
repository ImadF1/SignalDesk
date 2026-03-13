from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass(slots=True, frozen=True)
class Settings:
    tavily_api_key: str
    tavily_topic: str
    tavily_search_depth: str
    tavily_max_results: int
    tavily_timeout: float
    max_search_queries: int
    min_source_count: int
    ollama_base_url: str
    ollama_model: str
    ollama_temperature: float
    ollama_num_predict: int
    reports_dir: Path


def get_settings() -> Settings:
    return Settings(
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        tavily_topic=os.getenv("TAVILY_TOPIC", "general").strip() or "general",
        tavily_search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "advanced").strip() or "advanced",
        tavily_max_results=int(os.getenv("TAVILY_MAX_RESULTS", "5")),
        tavily_timeout=float(os.getenv("TAVILY_TIMEOUT", "60")),
        max_search_queries=int(os.getenv("MAX_SEARCH_QUERIES", "3")),
        min_source_count=int(os.getenv("MIN_SOURCE_COUNT", "5")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:latest").strip() or "llama3.2:latest",
        ollama_temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "900")),
        reports_dir=Path(os.getenv("REPORTS_DIR", str(REPORTS_DIR))),
    )


def ensure_directories(settings: Settings) -> None:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)


def normalize_proxy_environment() -> None:
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    broken_markers = ("127.0.0.1:9", "localhost:9")
    for key in proxy_keys:
        value = os.getenv(key, "")
        if any(marker in value for marker in broken_markers):
            os.environ.pop(key, None)

    existing_no_proxy = os.getenv("NO_PROXY", "").strip()
    local_targets = ["127.0.0.1", "localhost"]
    if existing_no_proxy:
        values = [item.strip() for item in existing_no_proxy.split(",") if item.strip()]
        for target in local_targets:
            if target not in values:
                values.append(target)
        os.environ["NO_PROXY"] = ",".join(values)
    else:
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
