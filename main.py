"""Webhook Command Center – main GUI entry point.

A dark-themed Tkinter application with four tabs:

* **Configuration** – set the Discord webhook URLs and schedule options for
  all three poster types.
* **Cybersecurity Writeups** – start/stop the scheduler that posts a random
  cybersecurity writeup to Discord every *N* hours, and send one on demand.
* **Cyber Resources** – start/stop the scheduler that posts a random
  cybersecurity resource to Discord every *N* hours, and send one on demand.
* **Hacking Music** – start/stop the scheduler that posts a random hacking
  music recommendation to Discord every *N* hours, and send one on demand.

Usage::

    python main.py
"""

import threading
from datetime import datetime, timedelta
from tkinter import messagebox
import tkinter as tk

import requests

import config as cfg
import cyber_hook
import resources_hook
import music_hook

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
BG = "#1a1a2e"          # main background
BG2 = "#16213e"         # slightly lighter panels
ACCENT = "#0f3460"      # header / button fill
HIGHLIGHT = "#e94560"   # danger / active accent
GREEN = "#00ff41"       # status / success
TEXT = "#e0e0e0"        # normal text
FONT = ("Consolas", 10)
FONT_B = ("Consolas", 10, "bold")
FONT_LG = ("Consolas", 14, "bold")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dark_button(parent, text, command, *, bg=ACCENT, fg=TEXT, abg=HIGHLIGHT, afg="#ffffff",
                 state="normal", padx=12, pady=5) -> tk.Button:
    """Return a flat-styled Button with hover colours handled by ``activebackground``."""
    btn = tk.Button(
        parent, text=text, command=command,
        font=FONT_B, bg=bg, fg=fg,
        activebackground=abg, activeforeground=afg,
        relief="flat", padx=padx, pady=pady,
        state=state, cursor="hand2",
        disabledforeground="#555555",
    )
    return btn


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class CommandCenter(tk.Tk):
    """Root window for the Webhook Command Center."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Webhook Command Center")
        self.geometry("920x660")
        self.configure(bg=BG)
        self.minsize(720, 520)

        # Load persisted configuration
        self.config_data: dict = cfg.load_config()

        # Cybersecurity scheduler state
        self._cyber_running = False
        self._cyber_thread: threading.Thread | None = None
        self._cyber_stop_event = threading.Event()
        self._cyber_next_post_time: datetime | None = None

        # Resources scheduler state
        self._resources_running = False
        self._resources_thread: threading.Thread | None = None
        self._resources_stop_event = threading.Event()
        self._resources_next_post_time: datetime | None = None

        # Music scheduler state
        self._music_running = False
        self._music_thread: threading.Thread | None = None
        self._music_stop_event = threading.Event()
        self._music_next_post_time: datetime | None = None

        self._build_header()
        self._build_notebook()

        # Start countdown ticker
        self._tick_countdown()

        # Auto-start scheduler if configured
        if self.config_data.get("cyber_auto_start"):
            self.after(500, self._start_cyber)
        if self.config_data.get("resources_auto_start"):
            self.after(600, self._start_resources)
        if self.config_data.get("music_auto_start"):
            self.after(700, self._start_music)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=ACCENT, pady=12)
        header.pack(fill="x")

        tk.Label(
            header, text="⚡  WEBHOOK COMMAND CENTER  ⚡",
            font=("Consolas", 17, "bold"), bg=ACCENT, fg=HIGHLIGHT,
        ).pack(side="left", padx=20)

        self._clock_lbl = tk.Label(header, text="", font=FONT, bg=ACCENT, fg=TEXT)
        self._clock_lbl.pack(side="right", padx=20)
        self._tick_clock()

    def _tick_clock(self) -> None:
        self._clock_lbl.configure(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick_clock)

    # ------------------------------------------------------------------
    # Notebook
    # ------------------------------------------------------------------

    def _build_notebook(self) -> None:
        from tkinter import ttk  # local import to keep top-level clean

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT,
                        padding=[14, 7], font=FONT_B)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=BG)
        style.configure("TSeparator", background=ACCENT)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self._notebook = nb

        cfg_tab = ttk.Frame(nb)
        nb.add(cfg_tab, text="  ⚙  Configuration  ")
        self._build_config_tab(cfg_tab)

        cyber_tab = ttk.Frame(nb)
        nb.add(cyber_tab, text="  🔐  Cybersecurity Writeups  ")
        self._build_cyber_tab(cyber_tab)

        resources_tab = ttk.Frame(nb)
        nb.add(resources_tab, text="  📚  Cyber Resources  ")
        self._build_resources_tab(resources_tab)

        music_tab = ttk.Frame(nb)
        nb.add(music_tab, text="  🎵  Hacking Music  ")
        self._build_music_tab(music_tab)

    # ------------------------------------------------------------------
    # Configuration tab
    # ------------------------------------------------------------------

    def _build_config_tab(self, parent: tk.Widget) -> None:
        # Scrollable canvas wrapper
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # --- Section title ---
        tk.Label(inner, text="CONFIGURATION", font=("Consolas", 13, "bold"),
                 bg=BG, fg=HIGHLIGHT).pack(anchor="w", padx=20, pady=(18, 4))
        self._sep(inner)

        # --- Cybersecurity Webhook block ---
        tk.Label(inner, text="🔐  Cybersecurity Writeup Webhook",
                 font=FONT_B, bg=BG, fg=GREEN).pack(anchor="w", padx=20, pady=(14, 6))

        def _row(lbl_text: str) -> tk.Frame:
            row = tk.Frame(inner, bg=BG)
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=lbl_text, font=FONT, bg=BG, fg=TEXT,
                     width=24, anchor="w").pack(side="left")
            return row

        # Webhook URL
        url_row = _row("Discord Webhook URL:")
        self._cyber_url_var = tk.StringVar(value=self.config_data.get("cyber_webhook_url", ""))
        tk.Entry(
            url_row, textvariable=self._cyber_url_var, width=58,
            bg=BG2, fg=TEXT, insertbackground=TEXT, font=FONT, relief="flat", bd=4,
        ).pack(side="left", fill="x", expand=True)

        # Interval
        interval_row = _row("Post Interval (hours):")
        self._cyber_interval_var = tk.IntVar(
            value=self.config_data.get("cyber_interval_hours", 24)
        )
        tk.Spinbox(
            interval_row, from_=1, to=168, textvariable=self._cyber_interval_var,
            width=6, bg=BG2, fg=TEXT, buttonbackground=ACCENT,
            font=FONT, relief="flat",
        ).pack(side="left")
        tk.Label(interval_row, text="  (1 – 168 h)", font=FONT, bg=BG, fg="#888888").pack(side="left")

        # Auto-start
        autostart_row = _row("Auto-Start on Launch:")
        self._cyber_autostart_var = tk.BooleanVar(
            value=self.config_data.get("cyber_auto_start", False)
        )
        tk.Checkbutton(
            autostart_row, variable=self._cyber_autostart_var,
            bg=BG, fg=TEXT, selectcolor=BG2,
            activebackground=BG, activeforeground=GREEN, font=FONT,
        ).pack(side="left")

        self._sep(inner)

        # --- Cybersecurity Resources Webhook block ---
        tk.Label(inner, text="📚  Cybersecurity Resources Webhook",
                 font=FONT_B, bg=BG, fg=GREEN).pack(anchor="w", padx=20, pady=(14, 6))

        # Webhook URL
        res_url_row = _row("Discord Webhook URL:")
        self._resources_url_var = tk.StringVar(value=self.config_data.get("resources_webhook_url", ""))
        tk.Entry(
            res_url_row, textvariable=self._resources_url_var, width=58,
            bg=BG2, fg=TEXT, insertbackground=TEXT, font=FONT, relief="flat", bd=4,
        ).pack(side="left", fill="x", expand=True)

        # Interval
        res_interval_row = _row("Post Interval (hours):")
        self._resources_interval_var = tk.IntVar(
            value=self.config_data.get("resources_interval_hours", 24)
        )
        tk.Spinbox(
            res_interval_row, from_=1, to=168, textvariable=self._resources_interval_var,
            width=6, bg=BG2, fg=TEXT, buttonbackground=ACCENT,
            font=FONT, relief="flat",
        ).pack(side="left")
        tk.Label(res_interval_row, text="  (1 – 168 h)", font=FONT, bg=BG, fg="#888888").pack(side="left")

        # Auto-start
        res_autostart_row = _row("Auto-Start on Launch:")
        self._resources_autostart_var = tk.BooleanVar(
            value=self.config_data.get("resources_auto_start", False)
        )
        tk.Checkbutton(
            res_autostart_row, variable=self._resources_autostart_var,
            bg=BG, fg=TEXT, selectcolor=BG2,
            activebackground=BG, activeforeground=GREEN, font=FONT,
        ).pack(side="left")

        self._sep(inner)

        # --- Hacking Music Webhook block ---
        tk.Label(inner, text="🎵  Hacking Music Webhook",
                 font=FONT_B, bg=BG, fg=GREEN).pack(anchor="w", padx=20, pady=(14, 6))

        # Webhook URL
        music_url_row = _row("Discord Webhook URL:")
        self._music_url_var = tk.StringVar(value=self.config_data.get("music_webhook_url", ""))
        tk.Entry(
            music_url_row, textvariable=self._music_url_var, width=58,
            bg=BG2, fg=TEXT, insertbackground=TEXT, font=FONT, relief="flat", bd=4,
        ).pack(side="left", fill="x", expand=True)

        # Interval
        music_interval_row = _row("Post Interval (hours):")
        self._music_interval_var = tk.IntVar(
            value=self.config_data.get("music_interval_hours", 24)
        )
        tk.Spinbox(
            music_interval_row, from_=1, to=168, textvariable=self._music_interval_var,
            width=6, bg=BG2, fg=TEXT, buttonbackground=ACCENT,
            font=FONT, relief="flat",
        ).pack(side="left")
        tk.Label(music_interval_row, text="  (1 – 168 h)", font=FONT, bg=BG, fg="#888888").pack(side="left")

        # Auto-start
        music_autostart_row = _row("Auto-Start on Launch:")
        self._music_autostart_var = tk.BooleanVar(
            value=self.config_data.get("music_auto_start", False)
        )
        tk.Checkbutton(
            music_autostart_row, variable=self._music_autostart_var,
            bg=BG, fg=TEXT, selectcolor=BG2,
            activebackground=BG, activeforeground=GREEN, font=FONT,
        ).pack(side="left")

        self._sep(inner)
        save_row = tk.Frame(inner, bg=BG)
        save_row.pack(anchor="w", padx=20, pady=14)

        _dark_button(save_row, "💾  Save Configuration", self._save_config).pack(side="left")

        self._cfg_status_lbl = tk.Label(save_row, text="", bg=BG, fg=GREEN, font=FONT)
        self._cfg_status_lbl.pack(side="left", padx=14)

    def _sep(self, parent: tk.Widget) -> None:
        tk.Frame(parent, bg=ACCENT, height=1).pack(fill="x", padx=20, pady=4)

    def _save_config(self) -> None:
        self.config_data["cyber_webhook_url"] = self._cyber_url_var.get().strip()
        self.config_data["cyber_interval_hours"] = int(self._cyber_interval_var.get())
        self.config_data["cyber_auto_start"] = bool(self._cyber_autostart_var.get())
        self.config_data["resources_webhook_url"] = self._resources_url_var.get().strip()
        self.config_data["resources_interval_hours"] = int(self._resources_interval_var.get())
        self.config_data["resources_auto_start"] = bool(self._resources_autostart_var.get())
        self.config_data["music_webhook_url"] = self._music_url_var.get().strip()
        self.config_data["music_interval_hours"] = int(self._music_interval_var.get())
        self.config_data["music_auto_start"] = bool(self._music_autostart_var.get())
        cfg.save_config(self.config_data)
        self._cfg_status_lbl.configure(text="✓  Saved!")
        self.after(3000, lambda: self._cfg_status_lbl.configure(text=""))

    # ------------------------------------------------------------------
    # Cybersecurity Writeups tab
    # ------------------------------------------------------------------

    def _build_cyber_tab(self, parent: tk.Widget) -> None:
        # --- Status bar ---
        status_bar = tk.Frame(parent, bg=BG2, pady=10)
        status_bar.pack(fill="x", padx=10, pady=(10, 0))

        self._cyber_dot_lbl = tk.Label(status_bar, text="●", font=("Consolas", 15),
                                       bg=BG2, fg="#ff4444")
        self._cyber_dot_lbl.pack(side="left", padx=(15, 4))

        self._cyber_status_lbl = tk.Label(status_bar, text="STOPPED",
                                          font=("Consolas", 12, "bold"), bg=BG2, fg="#ff4444")
        self._cyber_status_lbl.pack(side="left")

        self._cyber_countdown_lbl = tk.Label(status_bar, text="", font=FONT, bg=BG2, fg=TEXT)
        self._cyber_countdown_lbl.pack(side="left", padx=18)

        # --- Buttons ---
        btn_row = tk.Frame(parent, bg=BG, pady=8)
        btn_row.pack(fill="x", padx=10)

        self._start_btn = _dark_button(
            btn_row, "▶  Start", self._start_cyber,
            bg="#1a472a", fg=GREEN, abg="#2d6a4f", afg=GREEN,
        )
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = _dark_button(
            btn_row, "■  Stop", self._stop_cyber,
            bg="#4a1a1a", fg=HIGHLIGHT, abg="#7a2929", afg=HIGHLIGHT, state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(0, 6))

        self._send_now_btn = _dark_button(
            btn_row, "⚡  Send Now", self._send_now,
        )
        self._send_now_btn.pack(side="left")

        # --- Log area ---
        tk.Label(parent, text="Activity Log:", font=FONT_B, bg=BG, fg=TEXT).pack(
            anchor="w", padx=15, pady=(12, 2)
        )

        log_frame = tk.Frame(parent, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._log_text = tk.Text(
            log_frame, bg="#0d1117", fg=GREEN, font=("Consolas", 9),
            relief="flat", bd=0, state="disabled", wrap="word",
        )
        log_sb = tk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        self._log("System initialized. Set your webhook URL in the Configuration tab then press ▶ Start.")

    # ------------------------------------------------------------------
    # Logging helper (thread-safe)
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        def _insert():
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_text.configure(state="normal")
            self._log_text.insert("end", f"[{ts}] {message}\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")

        self.after(0, _insert)

    # ------------------------------------------------------------------
    # Scheduler controls
    # ------------------------------------------------------------------

    def _set_cyber_ui(self, running: bool) -> None:
        self._cyber_running = running
        if running:
            self._cyber_dot_lbl.configure(fg=GREEN)
            self._cyber_status_lbl.configure(text="RUNNING", fg=GREEN)
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
        else:
            self._cyber_dot_lbl.configure(fg="#ff4444")
            self._cyber_status_lbl.configure(text="STOPPED", fg="#ff4444")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._cyber_countdown_lbl.configure(text="")
            self._cyber_next_post_time = None

    def _start_cyber(self) -> None:
        url = self.config_data.get("cyber_webhook_url", "").strip()
        # Also check the live entry widget in case the user hasn't saved yet
        if not url:
            url = self._cyber_url_var.get().strip()

        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL in the Configuration tab and save.",
            )
            return

        if self._cyber_running:
            return

        interval = int(self.config_data.get("cyber_interval_hours", 24))
        self._cyber_stop_event.clear()
        self._cyber_thread = threading.Thread(
            target=self._cyber_loop, args=(url, interval), daemon=True
        )
        self._cyber_thread.start()
        self._set_cyber_ui(True)
        self._log(f"Scheduler started – posting every {interval} hour(s).")

    def _stop_cyber(self) -> None:
        self._cyber_stop_event.set()
        self._set_cyber_ui(False)
        self._log("Scheduler stopped.")

    def _send_now(self) -> None:
        url = self.config_data.get("cyber_webhook_url", "").strip()
        if not url:
            url = self._cyber_url_var.get().strip()
        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL in the Configuration tab and save.",
            )
            return
        threading.Thread(target=self._do_post, args=(url,), daemon=True).start()

    # ------------------------------------------------------------------
    # Background scheduler loop
    # ------------------------------------------------------------------

    def _cyber_loop(self, webhook_url: str, interval_hours: int) -> None:
        """Runs in a daemon thread. Posts immediately, then on a fixed schedule."""
        self._do_post(webhook_url)
        interval_secs = interval_hours * 3600
        self._cyber_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

        while not self._cyber_stop_event.wait(1):
            if datetime.now() >= self._cyber_next_post_time:
                self._do_post(webhook_url)
                self._cyber_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

    def _do_post(self, webhook_url: str) -> None:
        self._log("Fetching a random cybersecurity writeup …")
        try:
            writeup = cyber_hook.fetch_random_writeup(log_callback=self._log)
            if writeup is None:
                self._log("ERROR: No writeups retrieved – check your internet connection.")
                return
            self._log(f"Selected: «{writeup['title']}» [{writeup['source']}]")
            cyber_hook.post_to_discord(webhook_url, writeup)
            self._log(f"✓  Posted successfully: {writeup['title']}")
        except requests.HTTPError as exc:
            self._log(f"ERROR: Discord webhook returned {exc.response.status_code}: {exc}")
        except requests.RequestException as exc:
            self._log(f"ERROR: Network error when posting to Discord: {exc}")
        except Exception as exc:  # noqa: BLE001 – catch-all for unexpected errors
            self._log(f"ERROR (unexpected): {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # Countdown ticker
    # ------------------------------------------------------------------

    def _tick_countdown(self) -> None:
        if self._cyber_running and self._cyber_next_post_time:
            remaining = int((self._cyber_next_post_time - datetime.now()).total_seconds())
            if remaining > 0:
                h, r = divmod(remaining, 3600)
                m, s = divmod(r, 60)
                self._cyber_countdown_lbl.configure(
                    text=f"   Next post in:  {h:02d}:{m:02d}:{s:02d}"
                )
            else:
                self._cyber_countdown_lbl.configure(text="   Posting soon …")
        if self._resources_running and self._resources_next_post_time:
            remaining = int((self._resources_next_post_time - datetime.now()).total_seconds())
            if remaining > 0:
                h, r = divmod(remaining, 3600)
                m, s = divmod(r, 60)
                self._resources_countdown_lbl.configure(
                    text=f"   Next post in:  {h:02d}:{m:02d}:{s:02d}"
                )
            else:
                self._resources_countdown_lbl.configure(text="   Posting soon …")
        if self._music_running and self._music_next_post_time:
            remaining = int((self._music_next_post_time - datetime.now()).total_seconds())
            if remaining > 0:
                h, r = divmod(remaining, 3600)
                m, s = divmod(r, 60)
                self._music_countdown_lbl.configure(
                    text=f"   Next post in:  {h:02d}:{m:02d}:{s:02d}"
                )
            else:
                self._music_countdown_lbl.configure(text="   Posting soon …")
        self.after(1000, self._tick_countdown)

    # ------------------------------------------------------------------
    # Cybersecurity Resources tab
    # ------------------------------------------------------------------

    def _build_resources_tab(self, parent: tk.Widget) -> None:
        # --- Status bar ---
        status_bar = tk.Frame(parent, bg=BG2, pady=10)
        status_bar.pack(fill="x", padx=10, pady=(10, 0))

        self._resources_dot_lbl = tk.Label(status_bar, text="●", font=("Consolas", 15),
                                           bg=BG2, fg="#ff4444")
        self._resources_dot_lbl.pack(side="left", padx=(15, 4))

        self._resources_status_lbl = tk.Label(status_bar, text="STOPPED",
                                              font=("Consolas", 12, "bold"), bg=BG2, fg="#ff4444")
        self._resources_status_lbl.pack(side="left")

        self._resources_countdown_lbl = tk.Label(status_bar, text="", font=FONT, bg=BG2, fg=TEXT)
        self._resources_countdown_lbl.pack(side="left", padx=18)

        # --- Buttons ---
        btn_row = tk.Frame(parent, bg=BG, pady=8)
        btn_row.pack(fill="x", padx=10)

        self._res_start_btn = _dark_button(
            btn_row, "▶  Start", self._start_resources,
            bg="#1a472a", fg=GREEN, abg="#2d6a4f", afg=GREEN,
        )
        self._res_start_btn.pack(side="left", padx=(0, 6))

        self._res_stop_btn = _dark_button(
            btn_row, "■  Stop", self._stop_resources,
            bg="#4a1a1a", fg=HIGHLIGHT, abg="#7a2929", afg=HIGHLIGHT, state="disabled",
        )
        self._res_stop_btn.pack(side="left", padx=(0, 6))

        self._res_send_now_btn = _dark_button(
            btn_row, "⚡  Send Now", self._send_resource_now,
        )
        self._res_send_now_btn.pack(side="left")

        # --- Log area ---
        tk.Label(parent, text="Activity Log:", font=FONT_B, bg=BG, fg=TEXT).pack(
            anchor="w", padx=15, pady=(12, 2)
        )

        log_frame = tk.Frame(parent, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._res_log_text = tk.Text(
            log_frame, bg="#0d1117", fg="#0F3460", font=("Consolas", 9),
            relief="flat", bd=0, state="disabled", wrap="word",
        )
        self._res_log_text.configure(fg="#4da6ff")
        log_sb = tk.Scrollbar(log_frame, orient="vertical", command=self._res_log_text.yview)
        self._res_log_text.configure(yscrollcommand=log_sb.set)
        self._res_log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        self._res_log("System initialized. Set your webhook URL in the Configuration tab then press ▶ Start.")

    def _res_log(self, message: str) -> None:
        def _insert():
            ts = datetime.now().strftime("%H:%M:%S")
            self._res_log_text.configure(state="normal")
            self._res_log_text.insert("end", f"[{ts}] {message}\n")
            self._res_log_text.see("end")
            self._res_log_text.configure(state="disabled")

        self.after(0, _insert)

    def _set_resources_ui(self, running: bool) -> None:
        self._resources_running = running
        if running:
            self._resources_dot_lbl.configure(fg=GREEN)
            self._resources_status_lbl.configure(text="RUNNING", fg=GREEN)
            self._res_start_btn.configure(state="disabled")
            self._res_stop_btn.configure(state="normal")
        else:
            self._resources_dot_lbl.configure(fg="#ff4444")
            self._resources_status_lbl.configure(text="STOPPED", fg="#ff4444")
            self._res_start_btn.configure(state="normal")
            self._res_stop_btn.configure(state="disabled")
            self._resources_countdown_lbl.configure(text="")
            self._resources_next_post_time = None

    def _start_resources(self) -> None:
        url = self.config_data.get("resources_webhook_url", "").strip()
        if not url:
            url = self._resources_url_var.get().strip()
        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL for Cyber Resources in the Configuration tab and save.",
            )
            return
        if self._resources_running:
            return
        interval = int(self.config_data.get("resources_interval_hours", 24))
        self._resources_stop_event.clear()
        self._resources_thread = threading.Thread(
            target=self._resources_loop, args=(url, interval), daemon=True
        )
        self._resources_thread.start()
        self._set_resources_ui(True)
        self._res_log(f"Scheduler started – posting every {interval} hour(s).")

    def _stop_resources(self) -> None:
        self._resources_stop_event.set()
        self._set_resources_ui(False)
        self._res_log("Scheduler stopped.")

    def _send_resource_now(self) -> None:
        url = self.config_data.get("resources_webhook_url", "").strip()
        if not url:
            url = self._resources_url_var.get().strip()
        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL for Cyber Resources in the Configuration tab and save.",
            )
            return
        threading.Thread(target=self._do_resources_post, args=(url,), daemon=True).start()

    def _resources_loop(self, webhook_url: str, interval_hours: int) -> None:
        """Runs in a daemon thread. Posts immediately, then on a fixed schedule."""
        self._do_resources_post(webhook_url)
        interval_secs = interval_hours * 3600
        self._resources_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

        while not self._resources_stop_event.wait(1):
            if datetime.now() >= self._resources_next_post_time:
                self._do_resources_post(webhook_url)
                self._resources_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

    def _do_resources_post(self, webhook_url: str) -> None:
        self._res_log("Fetching a random cybersecurity resource …")
        try:
            resource = resources_hook.fetch_random_resource(log_callback=self._res_log)
            if resource is None:
                self._res_log("ERROR: No resources retrieved – check your internet connection.")
                return
            self._res_log(f"Selected: «{resource['title']}» [{resource['source']}]")
            resources_hook.post_to_discord(webhook_url, resource)
            self._res_log(f"✓  Posted successfully: {resource['title']}")
        except requests.HTTPError as exc:
            self._res_log(f"ERROR: Discord webhook returned {exc.response.status_code}: {exc}")
        except requests.RequestException as exc:
            self._res_log(f"ERROR: Network error when posting to Discord: {exc}")
        except Exception as exc:  # noqa: BLE001 – catch-all for unexpected errors
            self._res_log(f"ERROR (unexpected): {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # Hacking Music tab
    # ------------------------------------------------------------------

    def _build_music_tab(self, parent: tk.Widget) -> None:
        # --- Status bar ---
        status_bar = tk.Frame(parent, bg=BG2, pady=10)
        status_bar.pack(fill="x", padx=10, pady=(10, 0))

        self._music_dot_lbl = tk.Label(status_bar, text="●", font=("Consolas", 15),
                                       bg=BG2, fg="#ff4444")
        self._music_dot_lbl.pack(side="left", padx=(15, 4))

        self._music_status_lbl = tk.Label(status_bar, text="STOPPED",
                                          font=("Consolas", 12, "bold"), bg=BG2, fg="#ff4444")
        self._music_status_lbl.pack(side="left")

        self._music_countdown_lbl = tk.Label(status_bar, text="", font=FONT, bg=BG2, fg=TEXT)
        self._music_countdown_lbl.pack(side="left", padx=18)

        # --- Buttons ---
        btn_row = tk.Frame(parent, bg=BG, pady=8)
        btn_row.pack(fill="x", padx=10)

        self._music_start_btn = _dark_button(
            btn_row, "▶  Start", self._start_music,
            bg="#1a472a", fg=GREEN, abg="#2d6a4f", afg=GREEN,
        )
        self._music_start_btn.pack(side="left", padx=(0, 6))

        self._music_stop_btn = _dark_button(
            btn_row, "■  Stop", self._stop_music,
            bg="#4a1a1a", fg=HIGHLIGHT, abg="#7a2929", afg=HIGHLIGHT, state="disabled",
        )
        self._music_stop_btn.pack(side="left", padx=(0, 6))

        self._music_send_now_btn = _dark_button(
            btn_row, "⚡  Send Now", self._send_music_now,
        )
        self._music_send_now_btn.pack(side="left")

        # --- Log area ---
        tk.Label(parent, text="Activity Log:", font=FONT_B, bg=BG, fg=TEXT).pack(
            anchor="w", padx=15, pady=(12, 2)
        )

        log_frame = tk.Frame(parent, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._music_log_text = tk.Text(
            log_frame, bg="#0d1117", fg="#9B59B6", font=("Consolas", 9),
            relief="flat", bd=0, state="disabled", wrap="word",
        )
        log_sb = tk.Scrollbar(log_frame, orient="vertical", command=self._music_log_text.yview)
        self._music_log_text.configure(yscrollcommand=log_sb.set)
        self._music_log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        self._music_log("System initialized. Set your webhook URL in the Configuration tab then press ▶ Start.")

    def _music_log(self, message: str) -> None:
        def _insert():
            ts = datetime.now().strftime("%H:%M:%S")
            self._music_log_text.configure(state="normal")
            self._music_log_text.insert("end", f"[{ts}] {message}\n")
            self._music_log_text.see("end")
            self._music_log_text.configure(state="disabled")

        self.after(0, _insert)

    def _set_music_ui(self, running: bool) -> None:
        self._music_running = running
        if running:
            self._music_dot_lbl.configure(fg=GREEN)
            self._music_status_lbl.configure(text="RUNNING", fg=GREEN)
            self._music_start_btn.configure(state="disabled")
            self._music_stop_btn.configure(state="normal")
        else:
            self._music_dot_lbl.configure(fg="#ff4444")
            self._music_status_lbl.configure(text="STOPPED", fg="#ff4444")
            self._music_start_btn.configure(state="normal")
            self._music_stop_btn.configure(state="disabled")
            self._music_countdown_lbl.configure(text="")
            self._music_next_post_time = None

    def _start_music(self) -> None:
        url = self.config_data.get("music_webhook_url", "").strip()
        if not url:
            url = self._music_url_var.get().strip()
        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL for Hacking Music in the Configuration tab and save.",
            )
            return
        if self._music_running:
            return
        interval = int(self.config_data.get("music_interval_hours", 24))
        self._music_stop_event.clear()
        self._music_thread = threading.Thread(
            target=self._music_loop, args=(url, interval), daemon=True
        )
        self._music_thread.start()
        self._set_music_ui(True)
        self._music_log(f"Scheduler started – posting every {interval} hour(s).")

    def _stop_music(self) -> None:
        self._music_stop_event.set()
        self._set_music_ui(False)
        self._music_log("Scheduler stopped.")

    def _send_music_now(self) -> None:
        url = self.config_data.get("music_webhook_url", "").strip()
        if not url:
            url = self._music_url_var.get().strip()
        if not url:
            messagebox.showerror(
                "Configuration Error",
                "Please enter a Discord Webhook URL for Hacking Music in the Configuration tab and save.",
            )
            return
        threading.Thread(target=self._do_music_post, args=(url,), daemon=True).start()

    def _music_loop(self, webhook_url: str, interval_hours: int) -> None:
        """Runs in a daemon thread. Posts immediately, then on a fixed schedule."""
        self._do_music_post(webhook_url)
        interval_secs = interval_hours * 3600
        self._music_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

        while not self._music_stop_event.wait(1):
            if datetime.now() >= self._music_next_post_time:
                self._do_music_post(webhook_url)
                self._music_next_post_time = datetime.now() + timedelta(seconds=interval_secs)

    def _do_music_post(self, webhook_url: str) -> None:
        self._music_log("Fetching a random hacking music track …")
        try:
            track = music_hook.fetch_random_track(log_callback=self._music_log)
            if track is None:
                self._music_log("ERROR: No tracks retrieved – check your internet connection.")
                return
            self._music_log(f"Selected: «{track['title']}» [{track['source']}]")
            music_hook.post_to_discord(webhook_url, track)
            self._music_log(f"✓  Posted successfully: {track['title']}")
        except requests.HTTPError as exc:
            self._music_log(f"ERROR: Discord webhook returned {exc.response.status_code}: {exc}")
        except requests.RequestException as exc:
            self._music_log(f"ERROR: Network error when posting to Discord: {exc}")
        except Exception as exc:  # noqa: BLE001 – catch-all for unexpected errors
            self._music_log(f"ERROR (unexpected): {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = CommandCenter()
    app.mainloop()


if __name__ == "__main__":
    main()
