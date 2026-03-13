from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
import webbrowser
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai_research_agent.config import ensure_directories, get_settings, normalize_proxy_environment
from ai_research_agent.graph import ResearchAgent
from ai_research_agent.models import ResearchRun, SearchSource, SourceSummary


APP_BG = "#08111f"
CARD_BG = "#101b2f"
CARD_ALT = "#13233c"
INPUT_BG = "#0b1729"
BORDER = "#263956"
TEXT = "#eef3fb"
MUTED = "#94a8c7"
ACCENT = "#e8773d"
ACCENT_DARK = "#c45d2a"
ACCENT_SOFT = "#3a2418"
SUCCESS = "#5fd2a0"

COMMON_OLLAMA_MODELS = [
    "llama3.2:latest",
    "phi3:latest",
    "llama3:latest",
    "mistral:latest",
]


def fetch_ollama_models(base_url: str) -> tuple[list[str], bool]:
    request = Request(f"{base_url.rstrip('/')}/api/tags", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError):
        return COMMON_OLLAMA_MODELS, False

    models = [str(item.get("name", "")).strip() for item in payload.get("models", [])]
    merged: list[str] = []
    seen: set[str] = set()
    for model in models + COMMON_OLLAMA_MODELS:
        if not model or model in seen:
            continue
        seen.add(model)
        merged.append(model)
    return merged or COMMON_OLLAMA_MODELS, True


class ResearchDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        normalize_proxy_environment()
        self.base_settings = get_settings()
        ensure_directories(self.base_settings)

        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.latest_run: ResearchRun | None = None
        self.source_by_id: dict[str, SearchSource] = {}
        self.summary_by_id: dict[str, SourceSummary] = {}

        self.status_var = tk.StringVar(value="Ready.")
        self.runtime_var = tk.StringVar()
        self.report_var = tk.StringVar(value="No report generated yet.")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.api_key_var = tk.StringVar(value=self.base_settings.tavily_api_key)
        self.model_var = tk.StringVar(value=self.base_settings.ollama_model)
        self.show_key_var = tk.BooleanVar(value=False)
        self.api_key_var.trace_add("write", self._on_runtime_input_changed)
        self.model_var.trace_add("write", self._on_runtime_input_changed)

        self.title("SignalDesk")
        self.geometry("1560x980")
        self.minsize(1320, 860)
        self.configure(bg=APP_BG)
        self.style = ttk.Style(self)

        self._configure_styles()
        self._build_layout()
        self._set_default_topic()
        self._load_models()
        self._refresh_runtime(ollama_online=None)
        self.after(120, self._poll_queue)

    def _configure_styles(self) -> None:
        self.style.theme_use("clam")
        self.style.configure("App.TFrame", background=APP_BG)
        self.style.configure("Card.TFrame", background=CARD_BG, borderwidth=0)
        self.style.configure("Title.TLabel", background=CARD_BG, foreground=TEXT, font=("Georgia", 24, "bold"))
        self.style.configure("Kicker.TLabel", background=CARD_BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        self.style.configure("Body.TLabel", background=CARD_BG, foreground=MUTED, font=("Segoe UI", 10))
        self.style.configure("Section.TLabel", background=CARD_BG, foreground=TEXT, font=("Segoe UI", 12, "bold"))
        self.style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            padding=(14, 10),
            font=("Segoe UI", 10, "bold"),
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", ACCENT_DARK), ("disabled", BORDER)],
            foreground=[("disabled", "#d2d8e3")],
        )
        self.style.configure(
            "Secondary.TButton",
            background=CARD_ALT,
            foreground=TEXT,
            borderwidth=0,
            padding=(12, 9),
            font=("Segoe UI", 10),
        )
        self.style.map(
            "Secondary.TButton",
            background=[("active", BORDER), ("disabled", BORDER)],
            foreground=[("disabled", MUTED)],
        )
        self.style.configure(
            "Picker.TCombobox",
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=ACCENT,
            padding=6,
        )
        self.style.map(
            "Picker.TCombobox",
            fieldbackground=[("readonly", INPUT_BG), ("disabled", CARD_ALT)],
            foreground=[("readonly", TEXT), ("disabled", MUTED)],
        )
        self.style.configure(
            "Intel.Treeview",
            background=INPUT_BG,
            foreground=TEXT,
            fieldbackground=INPUT_BG,
            borderwidth=0,
            rowheight=28,
            font=("Segoe UI", 10),
        )
        self.style.map(
            "Intel.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#ffffff")],
        )
        self.style.configure(
            "Intel.Treeview.Heading",
            background=CARD_ALT,
            foreground=TEXT,
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure(
            "App.Horizontal.TProgressbar",
            troughcolor=CARD_ALT,
            background=ACCENT,
            bordercolor=BORDER,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.hero = tk.Frame(self, bg=CARD_BG, padx=30, pady=26, highlightthickness=1)
        self.hero.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        ttk.Label(self.hero, text="Autonomous Web Research", style="Kicker.TLabel").pack(anchor="w")
        ttk.Label(self.hero, text="SignalDesk", style="Title.TLabel").pack(anchor="w", pady=(4, 6))
        ttk.Label(
            self.hero,
            text=(
                "Plan search angles with LangGraph, search the web with Tavily, summarize sources with Ollama, "
                "and produce a report you can review immediately from a native desktop window."
            ),
            style="Body.TLabel",
            wraplength=1180,
            justify="left",
        ).pack(anchor="w")

        badges = tk.Frame(self.hero, bg=CARD_BG)
        badges.pack(anchor="w", pady=(14, 0))
        for text in ["LangGraph", "Tavily Search", "Ollama", "Markdown Reports"]:
            badge = tk.Label(
                badges,
                text=text,
                bg=ACCENT_SOFT,
                fg=TEXT,
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=6,
            )
            badge.pack(side="left", padx=(0, 8))

        content = ttk.Frame(self, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        content.grid_columnconfigure(0, minsize=350)
        content.grid_columnconfigure(1, weight=5)
        content.grid_columnconfigure(2, weight=3)
        content.grid_rowconfigure(0, weight=1)

        self._build_sidebar(content)
        self._build_center_panel(content)
        self._build_intel_panel(content)

        footer = tk.Frame(self, bg=CARD_BG, padx=18, pady=12, highlightthickness=1)
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.progress = ttk.Progressbar(
            footer,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.progress_var,
            style="App.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(0, 8))
        self.footer_label = tk.Label(
            footer,
            textvariable=self.status_var,
            bg=CARD_BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.footer_label.pack(fill="x")

        for frame in [self.hero, footer]:
            frame.configure(highlightbackground=BORDER, highlightcolor=BORDER, highlightthickness=1)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(parent, bg=CARD_BG, padx=1, pady=1, highlightthickness=1)
        shell.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        shell.grid_propagate(False)
        shell.configure(width=350, highlightbackground=BORDER, highlightcolor=BORDER)

        panel = ttk.Frame(shell, style="Card.TFrame", padding=18)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)

        ttk.Label(panel, text="Runtime", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.runtime_label = tk.Label(
            panel,
            textvariable=self.runtime_var,
            bg=CARD_BG,
            fg=MUTED,
            justify="left",
            anchor="w",
            font=("Segoe UI", 10),
            wraplength=280,
        )
        self.runtime_label.grid(row=1, column=0, sticky="ew", pady=(8, 16))

        ttk.Label(panel, text="Tavily API Key", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        key_frame = tk.Frame(panel, bg=CARD_BG)
        key_frame.grid(row=3, column=0, sticky="ew", pady=(8, 10))
        key_frame.grid_columnconfigure(0, weight=1)

        self.api_key_entry = tk.Entry(
            key_frame,
            textvariable=self.api_key_var,
            show="*",
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            highlightthickness=1,
            font=("Segoe UI", 10),
        )
        self.api_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.show_key_button = ttk.Button(
            key_frame,
            text="Show",
            style="Secondary.TButton",
            command=self._toggle_api_key,
        )
        self.show_key_button.grid(row=0, column=1, sticky="e")

        ttk.Label(panel, text="Ollama Model", style="Section.TLabel").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.model_box = ttk.Combobox(
            panel,
            textvariable=self.model_var,
            state="normal",
            values=COMMON_OLLAMA_MODELS,
            style="Picker.TCombobox",
            font=("Segoe UI", 10),
        )
        self.model_box.grid(row=5, column=0, sticky="ew", pady=(8, 0))

        self.refresh_models_button = ttk.Button(
            panel,
            text="Refresh Models",
            style="Secondary.TButton",
            command=self._load_models,
        )
        self.refresh_models_button.grid(row=6, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(panel, text="Latest Report", style="Section.TLabel").grid(row=7, column=0, sticky="w", pady=(18, 0))
        self.report_label = tk.Label(
            panel,
            textvariable=self.report_var,
            bg=CARD_BG,
            fg=MUTED,
            justify="left",
            anchor="w",
            font=("Segoe UI", 10),
            wraplength=280,
        )
        self.report_label.grid(row=8, column=0, sticky="ew", pady=(8, 12))

        self.open_report_button = ttk.Button(
            panel,
            text="Open Report",
            style="Secondary.TButton",
            command=self.open_report,
        )
        self.open_report_button.grid(row=9, column=0, sticky="ew")

        self.open_folder_button = ttk.Button(
            panel,
            text="Open Reports Folder",
            style="Secondary.TButton",
            command=self.open_reports_folder,
        )
        self.open_folder_button.grid(row=10, column=0, sticky="ew", pady=(10, 0))

    def _build_center_panel(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(parent, bg=CARD_BG, padx=1, pady=1, highlightthickness=1)
        shell.grid(row=0, column=1, sticky="nsew")
        shell.configure(highlightbackground=BORDER, highlightcolor=BORDER)

        panel = ttk.Frame(shell, style="Card.TFrame", padding=22)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)

        ttk.Label(panel, text="Research Brief", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.topic_hint = tk.Label(
            panel,
            text="Describe the topic you want researched. The agent will search, summarize, and write the report.",
            bg=CARD_BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.topic_hint.grid(row=1, column=0, sticky="w", pady=(6, 10))

        self.topic_box = tk.Text(
            panel,
            height=5,
            wrap="word",
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=14,
            pady=14,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            highlightthickness=1,
            font=("Segoe UI", 11),
        )
        self.topic_box.grid(row=2, column=0, sticky="ew")

        actions = tk.Frame(panel, bg=CARD_BG)
        actions.grid(row=3, column=0, sticky="new", pady=(12, 12))
        self.run_button = ttk.Button(actions, text="Run Research", style="Accent.TButton", command=self.run_research)
        self.run_button.pack(side="left")
        self.clear_button = ttk.Button(actions, text="Clear Results", style="Secondary.TButton", command=self.reset_results)
        self.clear_button.pack(side="left", padx=(10, 0))

        ttk.Label(panel, text="Report Preview", style="Section.TLabel").grid(row=4, column=0, sticky="w")
        self.report_view = scrolledtext.ScrolledText(
            panel,
            wrap="word",
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=16,
            pady=16,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            highlightthickness=1,
            font=("Consolas", 10),
        )
        self.report_view.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        panel.grid_rowconfigure(5, weight=1)
        self.report_view.insert(
            "1.0",
            "# Report preview\n\nRun a research topic to generate a markdown report here.\n",
        )
        self.report_view.configure(state="disabled")

    def _build_intel_panel(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(parent, bg=CARD_BG, padx=1, pady=1, highlightthickness=1)
        shell.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        shell.configure(highlightbackground=BORDER, highlightcolor=BORDER)

        panel = ttk.Frame(shell, style="Card.TFrame", padding=22)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_rowconfigure(5, weight=2)

        ttk.Label(panel, text="Planned Queries", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.query_list = tk.Listbox(
            panel,
            bg=INPUT_BG,
            fg=TEXT,
            selectbackground=ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            highlightthickness=1,
            font=("Segoe UI", 10),
            height=8,
        )
        self.query_list.grid(row=1, column=0, sticky="nsew", pady=(8, 14))
        panel.grid_rowconfigure(1, weight=1)

        ttk.Label(panel, text="Collected Sources", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        self.source_tree = ttk.Treeview(
            panel,
            style="Intel.Treeview",
            columns=("domain", "score", "title"),
            show="headings",
            height=8,
        )
        self.source_tree.heading("domain", text="Domain")
        self.source_tree.heading("score", text="Score")
        self.source_tree.heading("title", text="Title")
        self.source_tree.column("domain", width=120, anchor="w")
        self.source_tree.column("score", width=60, anchor="center")
        self.source_tree.column("title", width=230, anchor="w")
        self.source_tree.grid(row=3, column=0, sticky="nsew", pady=(8, 14))
        self.source_tree.bind("<<TreeviewSelect>>", self._on_source_selected)
        self.source_tree.bind("<Double-1>", self._open_selected_source)

        ttk.Label(panel, text="Source Detail", style="Section.TLabel").grid(row=4, column=0, sticky="w")
        self.source_detail = scrolledtext.ScrolledText(
            panel,
            wrap="word",
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=14,
            pady=14,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            highlightthickness=1,
            font=("Segoe UI", 10),
        )
        self.source_detail.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        self.source_detail.insert(
            "1.0",
            "Select a source to inspect the title, URL, query, summary, and content excerpt.",
        )
        self.source_detail.configure(state="disabled")

    def _set_default_topic(self) -> None:
        self.topic_box.insert("1.0", "Explain the AI chip market")

    def _load_models(self) -> None:
        models, online = fetch_ollama_models(self.base_settings.ollama_base_url)
        self.model_box["values"] = models
        if self.model_var.get().strip() not in models:
            self.model_var.set(models[0])
        self._refresh_runtime(ollama_online=online)

    def _refresh_runtime(self, ollama_online: bool | None) -> None:
        key_status = "loaded" if self.api_key_var.get().strip() else "missing"
        if ollama_online is None:
            ollama_line = f"Ollama URL: {self.base_settings.ollama_base_url}"
        else:
            ollama_line = f"Ollama: {'online' if ollama_online else 'offline'}"
        self.runtime_var.set(
            "\n".join(
                [
                    ollama_line,
                    f"Model: {self.model_var.get().strip() or self.base_settings.ollama_model}",
                    f"Tavily key: {key_status}",
                    f"Reports: {self.base_settings.reports_dir}",
                ]
            )
        )

    def _toggle_api_key(self) -> None:
        visible = self.show_key_var.get()
        self.show_key_var.set(not visible)
        if visible:
            self.api_key_entry.configure(show="*")
            self.show_key_button.configure(text="Show")
        else:
            self.api_key_entry.configure(show="")
            self.show_key_button.configure(text="Hide")

    def run_research(self) -> None:
        if self.busy:
            return

        topic = self.topic_box.get("1.0", "end").strip()
        if not topic:
            messagebox.showwarning("Research topic", "Enter a research topic first.")
            return

        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Tavily API Key", "Add a Tavily API key before starting the research run.")
            return

        model_name = self.model_var.get().strip() or self.base_settings.ollama_model
        runtime_settings = replace(
            self.base_settings,
            tavily_api_key=api_key,
            ollama_model=model_name,
        )
        self._refresh_runtime(ollama_online=None)
        self._set_busy(True, "Planning and running the research workflow...")
        self.progress_var.set(0.0)

        def worker() -> None:
            try:
                agent = ResearchAgent(settings=runtime_settings)
                run = agent.run(topic, progress_callback=self._queue_progress)
                self.queue.put(("run-success", run))
            except Exception as exc:
                self.queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def reset_results(self) -> None:
        if self.busy:
            return
        self.latest_run = None
        self.source_by_id.clear()
        self.summary_by_id.clear()
        self.report_var.set("No report generated yet.")
        self.status_var.set("Ready.")
        self.progress_var.set(0.0)
        self._replace_text(
            self.report_view,
            "# Report preview\n\nRun a research topic to generate a markdown report here.\n",
        )
        self.query_list.delete(0, "end")
        for item in self.source_tree.get_children():
            self.source_tree.delete(item)
        self._replace_text(
            self.source_detail,
            "Select a source to inspect the title, URL, query, summary, and content excerpt.",
        )

    def open_report(self) -> None:
        if self.latest_run is None or not self.latest_run.report_path:
            messagebox.showinfo("Report", "No report has been generated yet.")
            return
        path = Path(self.latest_run.report_path)
        if not path.exists():
            messagebox.showwarning("Report", "The saved report file could not be found.")
            return
        os.startfile(str(path))  # type: ignore[attr-defined]

    def open_reports_folder(self) -> None:
        os.startfile(str(self.base_settings.reports_dir))  # type: ignore[attr-defined]

    def _on_source_selected(self, _event: tk.Event | None = None) -> None:
        selection = self.source_tree.selection()
        if not selection:
            return
        source_id = selection[0]
        source = self.source_by_id.get(source_id)
        if source is None:
            return
        summary = self.summary_by_id.get(source_id)
        detail = [
            f"{source.title}",
            f"URL: {source.url}",
            f"Query: {source.query}",
            f"Domain: {source.domain}",
            f"Score: {source.score:.3f}",
        ]
        if source.published_date:
            detail.append(f"Published: {source.published_date}")
        if summary is not None:
            detail.extend(["", "Summary", summary.summary])
        detail.extend(["", "Excerpt", source.content or "No excerpt available."])
        self._replace_text(self.source_detail, "\n".join(detail))

    def _open_selected_source(self, _event: tk.Event | None = None) -> None:
        selection = self.source_tree.selection()
        if not selection:
            return
        source = self.source_by_id.get(selection[0])
        if source is not None:
            webbrowser.open(source.url)

    def _poll_queue(self) -> None:
        while True:
            try:
                event, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if event == "run-success":
                self._handle_run_success(payload)
            elif event == "progress":
                self._handle_progress(payload)
            elif event == "error":
                self._handle_error(payload)

        self.after(120, self._poll_queue)

    def _handle_run_success(self, payload: object) -> None:
        if not isinstance(payload, ResearchRun):
            self._handle_error("The desktop app received an invalid run result.")
            return

        self.latest_run = payload
        self.source_by_id = {item.source_id: item for item in payload.sources}
        self.summary_by_id = {item.source_id: item for item in payload.summaries}
        self.report_var.set(payload.report_path)

        self.query_list.delete(0, "end")
        for query in payload.planned_queries:
            self.query_list.insert("end", query)

        for item in self.source_tree.get_children():
            self.source_tree.delete(item)
        for source in payload.sources:
            self.source_tree.insert(
                "",
                "end",
                iid=source.source_id,
                values=(source.domain, f"{source.score:.2f}", source.title),
            )

        self._replace_text(self.report_view, payload.report_markdown or "# Empty report")
        self._replace_text(
            self.source_detail,
            "Select a collected source to inspect its summary and excerpt.",
        )
        self._set_busy(False, f"Research complete. Saved {Path(payload.report_path).name}.")
        self.progress_var.set(100.0)

    def _handle_progress(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        message, value = payload
        self.status_var.set(str(message))
        if isinstance(value, (float, int)):
            bounded = max(0.0, min(float(value), 1.0))
            self.progress_var.set(bounded * 100.0)

    def _handle_error(self, payload: object) -> None:
        self._set_busy(False, str(payload))
        self.progress_var.set(0.0)
        messagebox.showerror("SignalDesk", str(payload))

    def _set_busy(self, busy: bool, status: str) -> None:
        self.busy = busy
        self.status_var.set(status)
        state = "disabled" if busy else "normal"
        self.run_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.model_box.configure(state="disabled" if busy else "normal")
        self.refresh_models_button.configure(state=state)
        self.api_key_entry.configure(state=state)
        self.show_key_button.configure(state=state)
        self.topic_box.configure(state=state)

    def _replace_text(self, widget: scrolledtext.ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value.strip() + "\n")
        widget.configure(state="disabled")

    def _queue_progress(self, message: str, value: float | None) -> None:
        self.queue.put(("progress", (message, value)))

    def _on_runtime_input_changed(self, *_args: object) -> None:
        self._refresh_runtime(ollama_online=None)


def main() -> None:
    app = ResearchDesktopApp()
    app.mainloop()
