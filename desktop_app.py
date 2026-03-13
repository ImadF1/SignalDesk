from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(ROOT_DIR / ".env")

from ai_research_agent.desktop_ui import main


if __name__ == "__main__":
    main()
