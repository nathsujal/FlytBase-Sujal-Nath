"""
Raven Drone Surveillance GUI
================================
Three-panel interface:
  1. Live Feed   – frames streamed from Perciever as the pipeline runs
  2. Live Logs   – all Python logger output, colour-coded by level
  3. Alerts      – streams alerts.txt live, then shows final threat cards

Usage:
    python gui.py --source path/to/video.mp4 [--detect-interval 5]
"""

import os
import argparse
import logging
import queue
import threading
from pathlib import Path
from tkinter import scrolledtext, messagebox
import tkinter as tk
from tkinter import ttk
from typing import Optional

import cv2
from PIL import Image, ImageTk

from src.utils import get_logger
from src.loaders import DroneFootageLoader
from src.perciever import Perciever
from src.db.postgres import init_schema as init_postgres
from src.db.neo4j import init_schema as init_neo4j
from src.db.postgres import save_frames, save_objects
from src.db.postgres import index_table
from src.vlm import FrameAnalyzer, ObjectAnalyzer
from src.security.agent import run_security_analysis
from src.agent import SecurityAgent

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Theme
# ─────────────────────────────────────────────────────────────────────────────
BG_DARK      = "#0d1117"
BG_PANEL     = "#161b22"
BG_CARD      = "#21262d"
BG_ENTRY     = "#1c2128"
ACCENT       = "#e94560"
ACCENT_BLUE  = "#388bfd"
TEXT_PRIMARY = "#e6edf3"
TEXT_DIM     = "#8b949e"
TEXT_WARN    = "#d29922"
TEXT_GOOD    = "#3fb950"
FONT_MONO    = ("Consolas", 9)
FONT_BODY    = ("Segoe UI", 10)
FONT_HEAD    = ("Segoe UI Semibold", 11)
FONT_SMALL   = ("Segoe UI", 9)

# ─────────────────────────────────────────────────────────────────────────────
# Queue-based log handler  →  feeds Live Logs panel without blocking
# ─────────────────────────────────────────────────────────────────────────────
class QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record):
        try:
            self.q.put_nowait(self.format(record))
        except queue.Full:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Shared frame queue – Perciever pushes BGR frames here
# ─────────────────────────────────────────────────────────────────────────────
_frame_q: queue.Queue = queue.Queue(maxsize=60)


def _patch_perciever():
    """Monkey-patch Perciever.process_frame to push frames into _frame_q."""
    try:
        from src.perciever.perciever import Perciever
        _orig = Perciever.process_frame

        def _patched(self, frame):
            result = _orig(self, frame)
            if result is not None and result.image is not None:
                try:
                    _frame_q.put_nowait(result.image.copy())
                except queue.Full:
                    pass
            return result

        Perciever.process_frame = _patched
    except Exception:
        pass   # src not yet importable – will be by the time pipeline runs


# ─────────────────────────────────────────────────────────────────────────────
# Styled helpers
# ─────────────────────────────────────────────────────────────────────────────
def _label(parent, text, font=FONT_BODY, fg=TEXT_PRIMARY, **kw):
    # Only set bg from parent if the caller didn't supply one explicitly
    kw.setdefault("bg", parent["bg"])
    return tk.Label(parent, text=text, font=font, fg=fg, **kw)

def _darken(hex_color: str) -> str:
    """Darken a hex color by ~15% for hover effect."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    r, g, b = int(r * 0.85), int(g * 0.85), int(b * 0.85)
    return f"#{r:02x}{g:02x}{b:02x}"

def _btn(parent, text, cmd, fg="white", bg=ACCENT, **kw):
    b = tk.Label(parent, text=text, fg=fg, bg=bg,
                 font=FONT_BODY, padx=10, pady=4,
                 cursor="hand2", relief="flat", **kw)
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.config(bg=_darken(bg)))
    b.bind("<Leave>",    lambda e: b.config(bg=bg))
    return b

def _section_label(parent, text):
    """Returns the header frame so callers can pack extra widgets into it."""
    f = tk.Frame(parent, bg=BG_PANEL)
    f.pack(fill="x")
    tk.Frame(f, bg=ACCENT, width=3).pack(side="left", fill="y")
    _label(f, f"  {text}", font=FONT_HEAD, fg=TEXT_PRIMARY,
           bg=BG_PANEL).pack(side="left", pady=6)
    return f


# Main window
class App(tk.Tk):
    def __init__(self, source: str, detect_interval: int):
        super().__init__()

        self.title("Drone Footage Security Analysis Dashboard")
        self.configure(bg=BG_DARK)
        self.geometry("1440x880")
        self.minsize(1000, 640)

        # Runtime state
        self._source = source
        self._detect_interval = detect_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._log_q: queue.Queue = queue.Queue()
        self._alerts_file = Path("alerts.txt")
        self._alerts_pos = 0        # byte position already consumed
        self._photo_ref = None     # prevent GC of current PhotoImage

        # Wire up logging
        logging.getLogger().addHandler(QueueLogHandler(self._log_q))

        self._build_ui()
        self._tick_logs()
        self._tick_video()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self._source and Path(self._source).exists():
            self._autoload_video()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()

        root_pw = ttk.PanedWindow(self, orient="horizontal")
        root_pw.pack(fill="both", expand=True, padx=6, pady=(4, 0))

        # Left column: video (top) + logs (bottom)
        left_pw = ttk.PanedWindow(root_pw, orient="vertical")
        root_pw.add(left_pw, weight=55)
        self._build_video(left_pw)
        self._build_logs(left_pw)

        # Right column: alerts
        right = tk.Frame(root_pw, bg=BG_PANEL)
        root_pw.add(right, weight=45)
        self._build_alerts(right)

        self._build_statusbar()

    # ── Top bar ──────────────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, pady=7, padx=12)
        bar.pack(fill="x")

        _label(bar, "⬡ Raven", font=("Segoe UI Semibold", 14),
               fg=ACCENT, bg=BG_PANEL).pack(side="left", padx=(0, 18))

        _label(bar, "Source:", fg=TEXT_DIM, bg=BG_PANEL,
               font=FONT_SMALL).pack(side="left")
        src_text = self._source if self._source else "—  (pass --source <path>)"
        _label(bar, src_text, fg=TEXT_PRIMARY, bg=BG_PANEL,
               font=FONT_MONO).pack(side="left", padx=(4, 20))

        _label(bar, "Detect every:", fg=TEXT_DIM, bg=BG_PANEL,
               font=FONT_SMALL).pack(side="left")
        self._interval_var = tk.IntVar(value=self._detect_interval)
        tk.Spinbox(bar, from_=1, to=60, textvariable=self._interval_var,
                   width=4, bg=BG_ENTRY, fg=TEXT_PRIMARY,
                   buttonbackground=BG_CARD, relief="flat",
                   font=FONT_BODY).pack(side="left", padx=(4, 2))
        _label(bar, "frames", fg=TEXT_DIM, bg=BG_PANEL,
               font=FONT_SMALL).pack(side="left")

        self._stop_btn = _btn(bar, "■  Stop", self._stop, bg="#3d3d3d")
        self._stop_btn.pack(side="right", padx=(4, 0))
        self._stop_btn.config(state="disabled")

        self._run_btn = _btn(bar, "▶  Run Pipeline", self._run, bg=ACCENT)
        self._run_btn.pack(side="right", padx=(0, 4))

    # ── Video panel ──────────────────────────────────────────────────────────
    def _build_video(self, parent):
        outer = tk.Frame(parent, bg=BG_PANEL)
        parent.add(outer, weight=3)

        # ── Player state ──
        self._frame_buffer: list = []   # all received BGR frames in arrival order
        self._play_idx      = 0
        self._player_paused = False
        self._player_speed  = 1.0
        self._player_after_id = None

        hdr = _section_label(outer, "LIVE FEED")
        self._feed_badge_var = tk.StringVar(value="⬤ LIVE")
        tk.Label(hdr, textvariable=self._feed_badge_var,
                fg=ACCENT, bg=BG_PANEL, font=FONT_SMALL).pack(side="right", padx=8)

        self._canvas = tk.Canvas(outer, bg="#000000", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=6, pady=(2, 0))
        self._canvas.create_text(
            8, 8, anchor="nw",
            text="Waiting for pipeline…",
            fill=TEXT_DIM, font=FONT_BODY, tags="placeholder",
        )

        # ── Scrubber ──
        scrub_row = tk.Frame(outer, bg=BG_PANEL)
        scrub_row.pack(fill="x", padx=6, pady=(4, 0))

        self._frame_lbl_var = tk.StringVar(value="0 / 0")
        tk.Label(scrub_row, textvariable=self._frame_lbl_var,
                fg=TEXT_DIM, bg=BG_PANEL, font=FONT_SMALL,
                width=12, anchor="w").pack(side="left")

        self._scrubber = ttk.Scale(scrub_row, from_=0, to=0,
                                orient="horizontal", command=self._on_scrub)
        self._scrubber.pack(fill="x", expand=True, side="left", padx=4)

        # ── Controls ──
        ctrl = tk.Frame(outer, bg=BG_PANEL)
        ctrl.pack(fill="x", padx=6, pady=(4, 6))

        def cbtn(txt, cmd, w=3):
            b = tk.Label(
                ctrl, text=txt, width=w,
                bg=BG_CARD, fg=TEXT_PRIMARY,
                font=("Segoe UI", 12),
                cursor="hand2", pady=2,
                relief="flat",
            )
            b.pack(side="left", padx=2)

            # Hover highlight
            b.bind("<Enter>",    lambda e: b.config(bg=BG_ENTRY))
            b.bind("<Leave>",    lambda e: b.config(bg=BG_CARD))
            b.bind("<Button-1>", lambda e: cmd())
            return b

        cbtn("⏮", self._player_restart)
        cbtn("⏪", self._player_step_back)
        self._pp_btn = cbtn("⏸", self._player_toggle_pause)
        cbtn("⏩", self._player_step_fwd)
        cbtn("⏭", self._player_goto_end)
        cbtn("🔄", self._player_replay)

        tk.Label(ctrl, text="  Speed:", fg=TEXT_DIM, bg=BG_PANEL,
                font=FONT_SMALL).pack(side="left", padx=(12, 2))
        self._speed_var = tk.StringVar(value="1×")
        spd = ttk.Combobox(ctrl, textvariable=self._speed_var,
                        values=["0.25×", "0.5×", "1×", "2×", "4×"],
                        width=5, state="readonly")
        spd.pack(side="left")
        spd.bind("<<ComboboxSelected>>", self._on_speed_change)

        self._loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Loop", variable=self._loop_var,
                    bg=BG_PANEL, fg=TEXT_DIM, selectcolor=BG_CARD,
                    activebackground=BG_PANEL, activeforeground=TEXT_PRIMARY,
                    font=FONT_SMALL, relief="flat").pack(side="left", padx=(12, 0))

    def _render_bgr(self, bgr):
        cw = self._canvas.winfo_width()  or 800
        ch = self._canvas.winfo_height() or 480
        h, w = bgr.shape[:2]
        scale = min(cw / w, ch / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        rgb   = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(
            Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS)
        )
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")
        self._photo_ref = photo

    def _player_show_idx(self, idx: int):
        if not self._frame_buffer:
            return
        idx = max(0, min(idx, len(self._frame_buffer) - 1))
        self._play_idx = idx
        self._render_bgr(self._frame_buffer[idx])
        total = len(self._frame_buffer)
        self._frame_lbl_var.set(f"{idx + 1} / {total}")
        self._scrubber.config(to=max(0, total - 1))
        self._scrubber.set(idx)

    def _player_tick(self):
        if self._player_paused:
            return
        if not self._frame_buffer:
            self._player_after_id = self.after(50, self._player_tick)
            return
        next_idx = self._play_idx + 1
        if next_idx >= len(self._frame_buffer):
            if self._loop_var.get():
                next_idx = 0
            else:
                self._player_paused = True
                self._pp_btn.config(text="▶")
                return
        self._player_show_idx(next_idx)
        delay = max(1, int(33 / self._player_speed))
        self._player_after_id = self.after(delay, self._player_tick)

    def _player_start(self):
        if self._player_after_id:
            self.after_cancel(self._player_after_id)
            self._player_after_id = None
        self._player_paused = False
        self._pp_btn.config(text="⏸")
        self._player_tick()

    def _player_toggle_pause(self):
        if self._player_paused:
            self._player_start()
        else:
            self._player_paused = True
            self._pp_btn.config(text="▶")

    def _player_restart(self):
        self._player_show_idx(0)
        self._player_start()

    def _player_goto_end(self):
        if self._frame_buffer:
            self._player_show_idx(len(self._frame_buffer) - 1)
        self._player_paused = True
        self._pp_btn.config(text="▶")

    def _player_step_fwd(self):
        self._player_paused = True
        self._pp_btn.config(text="▶")
        self._player_show_idx(self._play_idx + 1)

    def _player_step_back(self):
        self._player_paused = True
        self._pp_btn.config(text="▶")
        self._player_show_idx(self._play_idx - 1)

    def _player_replay(self):
        self._player_show_idx(0)
        self._player_start()

    def _on_scrub(self, val):
        idx = int(float(val))
        if idx != self._play_idx:
            self._player_show_idx(idx)

    def _on_speed_change(self, _=None):
        try:
            self._player_speed = float(self._speed_var.get().replace("×", ""))
        except ValueError:
            self._player_speed = 1.0

    def _tick_video(self):
        new_frames = []
        try:
            while True:
                new_frames.append(_frame_q.get_nowait())
        except queue.Empty:
            pass

        if new_frames:
            was_empty = not self._frame_buffer
            self._frame_buffer.extend(new_frames)
            total = len(self._frame_buffer)
            self._scrubber.config(to=max(0, total - 1))
            self._frame_lbl_var.set(f"{self._play_idx + 1} / {total}")

            if self._running:
                # Pipeline is active — track the live edge
                if not self._player_paused:
                    self._player_show_idx(total - 1)
                self._feed_badge_var.set("⬤ LIVE")
            elif was_empty:
                # First frames from autoload — kick off replay
                self._feed_badge_var.set("▶ REPLAY")
                self._player_show_idx(0)
                self._player_start()
            # If not running and not was_empty: user is scrubbing, leave them alone

        self.after(33, self._tick_video)

    def _show_frame(self, bgr):
        """Compatibility shim."""
        self._render_bgr(bgr)

    def _autoload_video(self):
        source = Path(self._source)

        def _reader():
            if source.is_file():
                self._autoload_from_video(source)
            elif source.is_dir():
                self._autoload_from_frames(source)
            else:
                logger.warning("Autoload: source not found — %s", source)

        threading.Thread(target=_reader, daemon=True).start()

    def _autoload_from_video(self, source: Path):
        """Raw video → _frame_q."""
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            logger.warning("Autoload: could not open video %s", source)
            return
        logger.info("Autoload: reading video %s", source.name)
        while not self._running:
            ok, frame = cap.read()
            if not ok:
                break
            try:
                _frame_q.put(frame, timeout=0.5)
            except queue.Full:
                pass
        cap.release()
        logger.info("Autoload: video reader done")

    def _autoload_from_frames(self, source: Path):
        """Image directory → _frame_q, sorted same way as DroneFootageLoader."""
        paths = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            paths.extend(source.glob(ext))

        # Match DroneFootageLoader's sort: by mtime, newest-first
        paths = sorted(paths, key=lambda p: p.stat().st_mtime)

        if not paths:
            logger.warning("Autoload: no images found in %s", source)
            return

        logger.info("Autoload: reading %d frames from directory %s", len(paths), source.name)
        for p in paths:
            if self._running:          # pipeline started — hand off to Perciever
                logger.info("Autoload: pipeline started, stopping frame reader")
                break
            frame = cv2.imread(str(p))
            if frame is None:
                continue
            try:
                _frame_q.put(frame, timeout=0.5)
            except queue.Full:
                pass
        logger.info("Autoload: frame directory reader done")

    # ── Log panel ────────────────────────────────────────────────────────────
    def _build_logs(self, parent):
        outer = tk.Frame(parent, bg=BG_PANEL)
        parent.add(outer, weight=1)

        hdr = _section_label(outer, "LIVE LOGS")
        _btn(hdr, "Clear", self._clear_logs, bg=BG_CARD,
             fg=TEXT_DIM).pack(side="right", padx=8, pady=2)

        self._log_box = scrolledtext.ScrolledText(
            outer, bg=BG_DARK, fg=TEXT_GOOD,
            font=FONT_MONO, relief="flat", wrap="word",
            state="disabled", height=9,
        )
        self._log_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        for tag, colour in (
            ("DEBUG",    TEXT_DIM),
            ("INFO",     TEXT_GOOD),
            ("WARNING",  TEXT_WARN),
            ("ERROR",    ACCENT),
            ("CRITICAL", ACCENT),
        ):
            self._log_box.tag_config(tag, foreground=colour)

    def _tick_logs(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                tag = next(
                    (t for t in ("DEBUG", "WARNING", "ERROR", "CRITICAL") if t in msg),
                    "INFO",
                )
                self._log_box.config(state="normal")
                self._log_box.insert("end", msg + "\n", tag)
                self._log_box.see("end")
                self._log_box.config(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._tick_logs)

    def _clear_logs(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    # ── Alerts panel ─────────────────────────────────────────────────────────
    def _build_alerts(self, parent):
        _section_label(parent, "ALERTS & THREATS")

        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Tab 1 – raw stream
        tab_stream = tk.Frame(nb, bg=BG_PANEL)
        nb.add(tab_stream, text="  Stream  ")
        self._alert_box = scrolledtext.ScrolledText(
            tab_stream, bg=BG_DARK, fg=TEXT_WARN,
            font=FONT_MONO, relief="flat", wrap="word", state="disabled",
        )
        self._alert_box.pack(fill="both", expand=True)

        # Tab 2 – threat cards
        tab_cards = tk.Frame(nb, bg=BG_PANEL)
        nb.add(tab_cards, text="  Threat Cards  ")

        self._cards_canvas = tk.Canvas(tab_cards, bg=BG_PANEL,
                                       highlightthickness=0)
        vsb = ttk.Scrollbar(tab_cards, orient="vertical",
                            command=self._cards_canvas.yview)
        self._cards_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._cards_canvas.pack(fill="both", expand=True)

        self._cards_frame = tk.Frame(self._cards_canvas, bg=BG_PANEL)
        _win_id = self._cards_canvas.create_window(
            (0, 0), window=self._cards_frame, anchor="nw",
        )

        def _on_frame_configure(e):
            self._cards_canvas.configure(
                scrollregion=self._cards_canvas.bbox("all")
            )

        def _on_canvas_configure(e):
            self._cards_canvas.itemconfig(_win_id, width=e.width)

        self._cards_frame.bind("<Configure>", _on_frame_configure)
        self._cards_canvas.bind("<Configure>", _on_canvas_configure)

    def _start_alert_poll(self):
        self._alerts_pos = 0
        self._poll_alerts()

    def _poll_alerts(self):
        if self._alerts_file.exists():
            size = self._alerts_file.stat().st_size
            if size > self._alerts_pos:
                with open(self._alerts_file, "r") as f:
                    f.seek(self._alerts_pos)
                    chunk = f.read()
                self._alerts_pos = size
                self._alert_box.config(state="normal")
                self._alert_box.insert("end", chunk)
                self._alert_box.see("end")
                self._alert_box.config(state="disabled")

        if self._running:
            self.after(1500, self._poll_alerts)

    def _finalise_alerts(self):
        if not self._alerts_file.exists():
            return
        with open(self._alerts_file, "r") as f:
            content = f.read()

        # Refresh stream tab
        self._alert_box.config(state="normal")
        self._alert_box.delete("1.0", "end")
        self._alert_box.insert("end", content)
        self._alert_box.config(state="disabled")

        self._render_cards(content)

    def _on_perciever_complete(self):
        """
        Called on main thread immediately after Perciever.process_all() finishes.
        alerts.txt is guaranteed fully written at this point.
        """
        # Flush any remaining content into the Stream tab
        self._poll_alerts()

        # Mark byte position so future polls don't re-read the same content
        if self._alerts_file.exists():
            self._alerts_pos = self._alerts_file.stat().st_size

        # Render threat cards immediately — don't wait for pipeline to finish
        self._finalise_alerts()

        logger.info("Alerts panel loaded from Perciever output")

    def _on_pipeline_complete(self):
        """
        Called on main thread after all 5 pipeline steps finish.
        Cleans up running state and status bar.
        """
        self._running = False
        self._run_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._set_status("Pipeline finished.", busy=False)

    def _render_cards(self, content: str):
        for w in self._cards_frame.winfo_children():
            w.destroy()

        # Split on === separator lines
        segments, current = [], []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and set(stripped) == {"="}:
                if current:
                    segments.append("\n".join(current).strip())
                    current = []
            else:
                current.append(line)
        if current:
            segments.append("\n".join(current).strip())

        cards = [s for s in segments
                 if any(k in s for k in ("DETECTED", "LIFECYCLE", "Object ID"))]

        if not cards:
            _label(self._cards_frame,
                   "No threats or tracks parsed yet.",
                   fg=TEXT_DIM).pack(pady=20)
            return

        for seg in cards:
            self._make_card(seg)

    def _make_card(self, text: str):
        is_threat = "DETECTED" in text
        border    = ACCENT if is_threat else TEXT_GOOD
        icon      = "🚨" if is_threat else "🚗"
        lines     = [l for l in text.splitlines() if l.strip()]

        card = tk.Frame(self._cards_frame, bg=BG_CARD)
        card.pack(fill="x", padx=8, pady=5)

        tk.Frame(card, bg=border, width=4).pack(side="left", fill="y")

        body = tk.Frame(card, bg=BG_CARD, padx=12, pady=10)
        body.pack(fill="both", expand=True, side="left")

        title = lines[0] if lines else "—"
        _label(body, f"{icon}  {title}", font=FONT_HEAD,
               fg=TEXT_PRIMARY, bg=BG_CARD, anchor="w",
               wraplength=480).pack(fill="x")

        for line in lines[1:]:
            colour = ACCENT if "DETECTED" in line else TEXT_DIM
            _label(body, line, font=FONT_MONO, fg=colour, bg=BG_CARD,
                   anchor="w", wraplength=480).pack(fill="x", pady=1)

    # ── Status bar ───────────────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, pady=4)
        bar.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(
            value="Ready — press  ▶ Run Pipeline  to start."
        )
        tk.Label(bar, textvariable=self._status_var, fg=TEXT_DIM,
                 bg=BG_PANEL, font=FONT_SMALL).pack(side="left", padx=10)

        self._pbar = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self._pbar.pack(side="right", padx=10)

    def _set_status(self, msg: str, busy=False):
        self._status_var.set(msg)
        if busy:
            self._pbar.start(10)
        else:
            self._pbar.stop()

    # ── Pipeline lifecycle ────────────────────────────────────────────────────
    def _run(self):
        if not self._source:
            messagebox.showwarning(
                "No source",
                "Pass --source <path> when launching the GUI.\n\n"
                "Example:\n  python gui.py --source footage/clip.mp4",
            )
            return

        if not Path(self._source).exists():
            messagebox.showerror("Path not found",
                                 f"Does not exist:\n{self._source}")
            return

        if self._running:
            return

        # Reset panels
        self._clear_logs()
        self._alert_box.config(state="normal")
        self._alert_box.delete("1.0", "end")
        self._alert_box.config(state="disabled")
        for w in self._cards_frame.winfo_children():
            w.destroy()
        if self._alerts_file.exists():
            self._alerts_file.unlink()

        _patch_perciever()

        self._running = True
        self._run_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._set_status(
            f"Running pipeline  ·  {Path(self._source).name}  "
            f"·  detect every {self._interval_var.get()} frames",
            busy=True,
        )
        self._start_alert_poll()

        self._thread = threading.Thread(
            target=self._worker,
            args=(self._source, self._interval_var.get()),
            daemon=True,
        )
        self._thread.start()
        self.after(400, self._watch_thread)

    def _worker(self, source: str, detect_interval: int):
        try:
            # Step 1: Load footage
            logger.info("Step 1: Loading Footage")
            loader = DroneFootageLoader(source)
            logger.info(f"Loaded {len(loader)} frames")
            
            # Step 2: Run perception (detection + tracking)
            logger.info("Step 2: Running Perception Pipeline")
            perciever = Perciever(frames=loader.frames, detect_interval=detect_interval)
            perciever.process_all()
            
            logger.info(f"Processed {len(perciever.frames)} frames")
            logger.info(f"Detected {len(perciever.objects)} unique objects")

            self.after(0, self._on_perciever_complete)
            
            # Step 3: Store to database
            logger.info("Step 3: Storing to Database")
            save_frames(perciever.frames)
            save_objects(list(perciever.objects.values()))
            logger.info("Data saved to PostgreSQL")

            # Step 4: Run VLM
            logger.info("Step 4: Running VLM")
            frame_analyzer = FrameAnalyzer()
            object_analyzer = ObjectAnalyzer()
            frame_analyzer.process(perciever.frames)
            object_analyzer.process(perciever.objects.values(), perciever.frames)
            logger.info("VLM analysis complete")

            # Step 5: Run Security Analysis
            logger.info("Step 5: Running Security Analysis")
            tracks, threats = run_security_analysis()
            logger.info("Security analysis complete")

            self.after(0, self._on_pipeline_complete)

        except Exception as exc:
            logging.getLogger("GUI").error(
                "Pipeline crashed: %s", exc, exc_info=True
            )

    def _watch_thread(self):
        if self._thread and not self._thread.is_alive():
            if self._running:
                # pipeline crashed before _on_pipeline_complete fired
                self._running = False
                self._run_btn.config(state="normal")
                self._stop_btn.config(state="disabled")
                self._set_status("Pipeline finished (watchdog).", busy=False)
                self._finalise_alerts()
        else:
            self.after(400, self._watch_thread)

    def _stop(self):
        self._running = False
        self._run_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._set_status(
            "Stop requested — will finish current pipeline step.", busy=False
        )

    def _on_close(self):
        self._running = False
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Raven Drone Surveillance GUI")
    parser.add_argument("--source", "-s", default="",
                        help="Path to video file or frames directory")
    parser.add_argument("--detect-interval", "-d", type=int, default=5,
                        help="Run detection every N frames (default: 5)")
    args = parser.parse_args()

    App(source=args.source, detect_interval=args.detect_interval).mainloop()


if __name__ == "__main__":
    main()