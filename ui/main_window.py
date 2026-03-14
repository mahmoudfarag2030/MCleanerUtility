"""Main application window."""

import ctypes
import math
import os
import re
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import psutil
from tkinter import Canvas, messagebox, ttk

from cleaners import clean_folder, clean_browser_cache as run_browser_clean
from installed_apps import get_installed_apps_detailed
from helpers import browser_running_improved, format_size, is_admin
from scheduler_manager import create_task, delete_task, task_exists
from speed_test import run_speed_test
from startup_apps import get_startup_apps, toggle_startup_app
from system_tools import CpuSpeedReader, check_basic_tools

from .constants import (
    APP_VERSION,
    BUILD_VERSION,
    CPU_READER_INIT_DELAY_MS,
    PREVIEW_SAMPLE_ROWS,
)


THEME = {
    "bg": "#0f1115",
    "sidebar": "#111620",
    "surface": "#151a25",
    "surface_alt": "#10141d",
    "card": "#151a25",
    "card_border": "#232b3d",
    "text": "#e5e7eb",
    "muted": "#98a2b3",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "table_header": "#1b2230",
    "table_row": "#111827",
    "table_row_alt": "#0f1624",
    "progress_bg": "#1f2937",
}

FONT_SCALE = 1.0
UI_SCALE = 0.38
WINDOW_SCALE = 0.9
CARD_GAP_MULT = 1.1
BUTTON_SCALE = 1.5625


def ui_font(size, weight="normal"):
    scaled = max(9, int(size * FONT_SCALE))
    return ("Segoe UI", scaled, weight)


class MCleaner:
    def __init__(self, root):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        try:
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)
        except Exception:
            pass

        self.root = root
        self.root.configure(fg_color=THEME["bg"])
        try:
            self.root.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass
        self.root.title(
            f"MCleaner v{APP_VERSION} (build {BUILD_VERSION}) {'(Administrator)' if is_admin() else '(Standard Mode)'}"
        )

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        scale = 1.0
        if hasattr(ctk, "get_widget_scaling"):
            try:
                scale = float(ctk.get_widget_scaling()) or 1.0
            except Exception:
                scale = 1.0
        elif hasattr(ctk, "get_scaling"):
            try:
                scale = float(ctk.get_scaling()) or 1.0
            except Exception:
                scale = 1.0

        available_height = screen_height - 50

        target_width = min(int(screen_width * 0.9), 1280)
        target_height = min(int(available_height * 0.9), 820)

        target_width = max(target_width, 1024)
        target_height = max(target_height, 640)

        if screen_width < 1080 or available_height < 700:
            target_width = int(screen_width * 0.95)
            target_height = int(available_height * 0.95)

        target_width = max(int(target_width / scale), 720)
        target_height = max(int(target_height / scale), 520)

        min_width = max(int(900 / scale), 680)
        min_height = max(int(600 / scale), 480)

        target_width = max(int(target_width * WINDOW_SCALE), 740)
        target_height = max(int(target_height * WINDOW_SCALE), 560)
        min_width = max(int(min_width * WINDOW_SCALE), 640)
        min_height = max(int(min_height * WINDOW_SCALE), 460)

        # Start at minimum scale by default
        target_width = min_width
        target_height = min_height
        self.root.geometry(f"{target_width}x{target_height}")
        self.root.minsize(min_width, min_height)
        self.center_window(target_width, target_height)

        self.ui_scale = scale
        self.window_width = target_width
        self.window_height = target_height

        self.preview_ready = {"temp": False, "user_temp": False}
        self.badge_frames = []
        self.busy = False
        self.cpu_reader = None
        self.current_view = None
        self.installed_app_map = {}
        self.action_table_visible = False
        self.action_column_id = "#1"
        self.row_counter = 0
        self.action_table = None
        self.action_hover_id = None
        self.action_selected_id = None
        self.perf_cards = []
        self.stat_cards = []
        self._resize_job = None
        self._last_size = (0, 0)

        self.cpu_history = deque([0] * 80, maxlen=80)
        self.ram_history = deque([0] * 80, maxlen=80)
        self.disk_history = deque([0] * 80, maxlen=80)

        self.reset_stats()
        self._build_ui()

        self.root.after(CPU_READER_INIT_DELAY_MS, self.init_cpu_reader)
        self.root.after(300, self.update_dashboard)
        self.animate_badges()
        self.root.bind("<Configure>", self.on_resize)

    def reset_stats(self):
        self.last_cleaned = 0
        self.last_size_mb = 0.0
        self.protected_count = 0

    def center_window(self, width, height, parent=None):
        win = parent if parent is not None else self.root
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        available_h = screen_h - 50
        x = (screen_w - width) // 2
        y = (available_h - height) // 2
        y = max(0, y)
        win.geometry(f"{width}x{height}+{x}+{y}")

    def init_cpu_reader(self):
        try:
            self.cpu_reader = CpuSpeedReader()
        except Exception:
            self.cpu_reader = None

    def set_table_headers(self, h1="File", h2="Size", h3="Status", h4=None):
        try:
            self.table.heading("file", text=h1)
            self.table.heading("size", text=h2)
            self.table.heading("status", text=h3)
            if self.action_table:
                self.action_table.heading("action", text=h4 if h4 is not None else "")
        except Exception:
            pass

    def _build_ui(self):
        main = ctk.CTkFrame(self.root, fg_color=THEME["bg"])
        main.pack(fill="both", expand=True)

        scale = getattr(self, "ui_scale", 1.0)
        outer_pad = max(3, int(18 * UI_SCALE))
        section_gap = max(3, int(16 * UI_SCALE))
        small_screen = self.window_width <= 1366

        base_sidebar = 250 if not small_screen else 220
        sidebar_width = max(160, int(base_sidebar * UI_SCALE))

        sidebar = ctk.CTkFrame(
            main,
            width=sidebar_width,
            corner_radius=max(10, int(18 * UI_SCALE)),
            fg_color=THEME["sidebar"],
            border_width=1,
            border_color=THEME["card_border"],
        )
        sidebar.pack(side="left", fill="y", padx=outer_pad, pady=outer_pad)
        sidebar.pack_propagate(False)

        title_font = ui_font(26, "bold") if not small_screen else ui_font(22, "bold")
        meta_font = ui_font(11) if not small_screen else ui_font(10)
        section_font = ui_font(10, "bold")

        ctk.CTkLabel(
            sidebar, text="MCleaner", font=title_font, text_color=THEME["text"]
        ).pack(pady=(max(4, int(18 * UI_SCALE)), max(2, int(6 * UI_SCALE))))
        ctk.CTkLabel(
            sidebar,
            text=f"v{APP_VERSION} (build {BUILD_VERSION})",
            font=meta_font,
            text_color=THEME["muted"],
        ).pack(pady=(0, max(2, int(8 * UI_SCALE))))

        def add_section(label_text):
            ctk.CTkLabel(
                sidebar,
                text=label_text.upper(),
                font=section_font,
                text_color=THEME["muted"],
                anchor="w",
            ).pack(
                fill="x",
                padx=max(4, int(16 * UI_SCALE)),
                pady=(max(4, int(14 * UI_SCALE)), max(2, int(6 * UI_SCALE))),
            )

        def nav_button(text, cmd, primary=False):
            fg = THEME["accent"] if primary else THEME["surface_alt"]
            hover = THEME["accent_hover"] if primary else "#1a2230"
            base_font = 12 if primary else 11
            btn_font = ui_font(int(base_font * 1.2), "bold") if primary else ui_font(int(base_font * 1.2))
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=cmd,
                height=max(
                    22,
                    int(
                        (36 if not small_screen else 32)
                        * UI_SCALE
                        * BUTTON_SCALE
                        * 1.2
                        * 1.1
                    ),
                ),
                corner_radius=max(5, int(12 * UI_SCALE)),
                fg_color=fg,
                hover_color=hover,
                text_color="#ffffff",
                border_width=1,
                border_color=THEME["card_border"] if not primary else fg,
                font=btn_font,
                anchor="center",
            )
            btn.pack(
                fill="x",
                padx=max(4, int(14 * UI_SCALE)),
                pady=max(2, int(6 * UI_SCALE)),
            )
            return btn

        add_section("Core")
        btn_clean = nav_button("Clean All", self.clean_all, primary=True)
        btn_prev_temp = nav_button("Preview Windows Temp", self.handle_temp_button)
        btn_prev_user = nav_button("Preview User Temp", self.handle_user_temp_button)
        nav_button("Clean Browser Cache", self.clean_browser_cache)
        nav_button("Empty Recycle Bin", self.clean_recycle_bin)
        nav_button("Scheduled Cleanup", self.open_scheduler_window)

        add_section("Apps and Startup")
        nav_button("Installed Apps", self.show_installed_apps)
        nav_button("Startup Apps", self.show_startup_apps)

        add_section("Tools")
        nav_button("Internet Speed Test", self.run_speed_test_ui)
        nav_button("Runtime Checker", self.check_basic_tools)
        # Export report removed per request

        self.clean_everything_btn = btn_clean
        self.temp_button = btn_prev_temp
        self.user_temp_button = btn_prev_user
        self.sidebar_buttons = [
            w for w in sidebar.winfo_children() if isinstance(w, ctk.CTkButton)
        ]

        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(0, outer_pad),
            pady=outer_pad,
        )
        content.grid_rowconfigure(0, weight=0)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(content, fg_color="transparent")
        top.grid(row=0, column=0, sticky="new", pady=(0, max(1, int(section_gap * 0.5))))

        header = ctk.CTkFrame(top, fg_color="transparent")
        header.pack(fill="x", pady=(0, max(1, int(section_gap * 0.5))))

        ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ui_font(20, "bold"),
            text_color=THEME["text"],
        ).pack(side="left")

        # Export report removed per request

        perf = ctk.CTkFrame(top, fg_color="transparent")
        perf.pack(fill="x", pady=(0, max(1, int(section_gap * 0.5))))

        perf_title_font = ui_font(11, "bold")
        perf_value_font = ui_font(13)

        self.cpu_card = self.make_perf_card(
            perf, "CPU", THEME["accent"], perf_title_font, perf_value_font
        )
        self.ram_card = self.make_perf_card(
            perf, "Memory", "#8b5cf6", perf_title_font, perf_value_font
        )
        self.disk_card = self.make_perf_card(
            perf, "Disk", "#22c55e", perf_title_font, perf_value_font
        )

        stats = ctk.CTkFrame(top, fg_color="transparent")
        stats.pack(fill="x", pady=(0, max(1, int(section_gap * 0.5))))

        badge_title_font = ui_font(10, "bold")
        badge_value_font = ui_font(12)

        self.card_recoverable = self.make_stat_badge(
            stats,
            "Recoverable",
            "0.00 MB",
            badge_title_font,
            badge_value_font,
        )
        self.card_deleted = self.make_stat_badge(
            stats,
            "Deleted",
            "0 files",
            badge_title_font,
            badge_value_font,
        )
        self.card_protected = self.make_stat_badge(
            stats,
            "Permission Needed",
            "0 files",
            badge_title_font,
            badge_value_font,
        )

        self.progress = ctk.CTkProgressBar(
            top,
            height=max(5, int(12 * UI_SCALE)),
            fg_color=THEME["progress_bg"],
            progress_color=THEME["accent"],
            corner_radius=max(4, int(8 * UI_SCALE)),
        )
        self.progress.pack(fill="x", pady=(0, max(1, int(section_gap * 0.5))))
        self.progress.set(0)

        self._build_table(content, scale, small_screen)

    def _build_table(self, content, scale, small_screen):
        table_frame = ctk.CTkFrame(
            content,
            fg_color=THEME["surface"],
            corner_radius=max(6, int(16 * UI_SCALE)),
            border_width=1,
            border_color=THEME["card_border"],
        )
        table_frame.grid(row=1, column=0, sticky="nsew")
        self.table_frame = table_frame

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        row_height = max(10, int(30 * UI_SCALE * 1.2))
        table_font = ui_font(11)
        heading_font = ui_font(11, "bold")
        self.action_width = max(54, int((110 if not small_screen else 90) * UI_SCALE))

        style.configure(
            "Treeview",
            background=THEME["table_row"],
            foreground=THEME["text"],
            fieldbackground=THEME["table_row"],
            rowheight=row_height,
            font=table_font,
            bordercolor=THEME["card_border"],
        )
        style.configure(
            "Treeview.Heading",
            background=THEME["table_header"],
            foreground=THEME["text"],
            font=heading_font,
            bordercolor=THEME["card_border"],
        )
        style.map("Treeview", background=[("selected", THEME["accent"])])

        list_frame = ctk.CTkFrame(table_frame, fg_color="transparent")
        self.table = ttk.Treeview(
            list_frame, columns=("file", "size", "status"), show="headings"
        )

        def update_table_columns(event=None):
            try:
                frame_width = self.table_frame.winfo_width()
                if frame_width > 200:
                    scrollbar_w = 18
                    action_w = max(120, int(frame_width * 0.18))
                    self.action_width = action_w
                    if self.action_table_visible and self.action_table:
                        self.action_table.column("action", width=action_w, stretch=False)
                        self.action_frame.configure(
                            width=action_w + max(6, int(12 * UI_SCALE))
                        )

                    available = max(200, frame_width - action_w - scrollbar_w - 12)
                    min_file = 150 if not small_screen else 120
                    min_size = 60 if not small_screen else 50
                    min_status = 90 if not small_screen else 80
                    file_width = max(min_file, int(available * 0.55))
                    size_width = max(min_size, int(available * 0.16))
                    status_width = max(min_status, available - file_width - size_width)
                    self.table.column("file", width=file_width)
                    self.table.column("size", width=size_width)
                    self.table.column("status", width=status_width)
            except Exception:
                pass

        self.table.bind("<Configure>", update_table_columns)
        self.table.bind("<<TreeviewSelect>>", self.on_table_select, add="+")

        initial_widths = {
            "file": 200 if not small_screen else 150,
            "size": 80 if not small_screen else 60,
            "status": 120 if not small_screen else 100,
        }

        for col in ("file", "size", "status"):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=initial_widths[col])

        self.table.tag_configure("even", background=THEME["table_row"])
        self.table.tag_configure("odd", background=THEME["table_row_alt"])
        self.table.tag_configure("muted", foreground=THEME["muted"])

        action_style = "Action.Treeview"
        style.configure(
            action_style,
            background=THEME["table_row"],
            foreground=THEME["text"],
            fieldbackground=THEME["table_row"],
            rowheight=row_height,
            font=heading_font,
        )
        style.configure(
            "Action.Treeview.Heading",
            background=THEME["table_header"],
            foreground=THEME["text"],
            font=heading_font,
        )
        style.map(action_style, background=[("selected", THEME["table_row"])])

        self.action_frame = ctk.CTkFrame(
            table_frame,
            width=self.action_width + max(6, int(12 * UI_SCALE)),
            fg_color=THEME["surface"],
            corner_radius=max(6, int(16 * UI_SCALE)),
            border_width=1,
            border_color=THEME["card_border"],
        )
        self.action_frame.pack_propagate(False)

        self.action_table = ttk.Treeview(
            self.action_frame,
            columns=("action",),
            show="headings",
            style=action_style,
            selectmode="none",
        )
        self.action_table.heading("action", text="")
        self.action_table.column("action", width=self.action_width, anchor="center")
        self.action_table.tag_configure(
            "action", background="#1f2a44", foreground="#ffffff"
        )
        self.action_table.tag_configure(
            "action_hover", background=THEME["accent_hover"], foreground="#ffffff"
        )
        self.action_table.tag_configure(
            "action_selected", background=THEME["accent"], foreground="#ffffff"
        )
        try:
            self.action_table.configure(cursor="hand2")
        except Exception:
            pass
        self.action_table.bind("<Button-1>", self.on_action_click, add="+")
        self.action_table.bind("<Motion>", self.on_action_motion, add="+")
        self.action_table.bind("<Leave>", self.on_action_leave, add="+")
        self.action_table.pack(
            fill="both",
            expand=True,
            padx=max(2, int(6 * UI_SCALE)),
            pady=max(2, int(6 * UI_SCALE)),
        )

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.on_scrollbar
        )
        self.table.configure(yscroll=scrollbar.set)
        self.action_table.configure(yscroll=scrollbar.set)

        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_columnconfigure(1, weight=0)
        table_frame.grid_columnconfigure(2, weight=0)
        table_frame.grid_rowconfigure(0, weight=1)

        list_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(max(2, int(8 * UI_SCALE)), max(2, int(4 * UI_SCALE))),
            pady=max(2, int(8 * UI_SCALE)),
        )
        self.table.pack(side="left", fill="both", expand=True)
        self.action_frame.grid(
            row=0,
            column=1,
            sticky="ns",
            padx=(max(2, int(4 * UI_SCALE)), max(3, int(8 * UI_SCALE))),
            pady=max(2, int(8 * UI_SCALE)),
        )
        scrollbar.grid(row=0, column=2, sticky="ns", pady=max(2, int(8 * UI_SCALE)))

        self.bind_table_scroll()
        self.show_action_column(False)

    def make_perf_card(self, parent, title, color, title_font, value_font):
        card_gap = max(3, int(6 * UI_SCALE * CARD_GAP_MULT))
        frame = ctk.CTkFrame(
            parent,
            corner_radius=max(6, int(16 * UI_SCALE)),
            fg_color=THEME["card"],
            border_width=1,
            border_color=THEME["card_border"],
            height=64,
        )
        frame.pack(side="left", fill="both", expand=True, padx=card_gap)
        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame, text=title, font=title_font, text_color=THEME["muted"]
        ).pack(
            anchor="w",
            padx=max(4, int(14 * UI_SCALE)),
            pady=(max(3, int(12 * UI_SCALE)), max(1, int(2 * UI_SCALE))),
        )
        value = ctk.CTkLabel(
            frame, text="0", font=value_font, text_color=THEME["text"]
        )
        value.pack(anchor="w", padx=max(4, int(14 * UI_SCALE)))

        graph = Canvas(
            frame,
            height=max(10, int(22 * UI_SCALE)),
            bg=THEME["surface_alt"],
            highlightthickness=0,
        )
        graph.pack(
            fill="x",
            padx=max(3, int(12 * UI_SCALE)),
            pady=(max(2, int(8 * UI_SCALE)), max(2, int(8 * UI_SCALE))),
        )

        line_id = graph.create_line(0, 12, 1, 12, fill=color, width=2, smooth=True)

        self.perf_cards.append((frame, graph))
        return {"value": value, "graph": graph, "color": color, "line_id": line_id}

    def make_stat_badge(self, parent, title, value, title_font, value_font):
        card_gap = max(3, int(6 * UI_SCALE * CARD_GAP_MULT))
        frame = ctk.CTkFrame(
            parent,
            corner_radius=max(6, int(16 * UI_SCALE)),
            fg_color=THEME["card"],
            border_width=1,
            border_color=THEME["card_border"],
            height=64,
        )
        frame.pack(side="left", fill="x", expand=True, padx=card_gap)
        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame, text=title, font=title_font, text_color=THEME["muted"]
        ).pack(pady=(max(2, int(8 * UI_SCALE)), max(1, int(2 * UI_SCALE))))
        val = ctk.CTkLabel(
            frame, text=value, font=value_font, text_color=THEME["text"]
        )
        val.pack(pady=(0, max(2, int(8 * UI_SCALE))))

        self.badge_frames.append((frame, val))
        self.stat_cards.append(frame)
        return val

    def draw_graph(self, canvas, data, color, line_id):
        try:
            canvas.update_idletasks()
            w = canvas.winfo_width()
            h = canvas.winfo_height()

            if w < 10 or h < 5:
                return

            step = w / max(len(data) - 1, 1)
            pts = []
            for i, v in enumerate(data):
                x = i * step
                y = h - (max(0, min(100, v)) / 100 * h)
                pts.extend((x, y))

            canvas.coords(line_id, *pts)
        except Exception:
            pass

    def animate_badges(self, phase=0):
        for i, (frame, _) in enumerate(self.badge_frames):
            factor = 1 + 0.03 * math.sin(phase + i)
            base = 0x15
            c = int(base * factor)
            try:
                frame.configure(fg_color=f"#{c:02x}{0x1c:02x}{0x29:02x}")
            except Exception:
                pass
        self.root.after(160, lambda: self.animate_badges(phase + 0.25))

    def on_resize(self, event=None):
        try:
            if self._resize_job:
                self.root.after_cancel(self._resize_job)
            self._resize_job = self.root.after(120, self._apply_resize)
        except Exception:
            pass

    def _apply_resize(self):
        try:
            self._resize_job = None
            if not self.perf_cards and not self.stat_cards:
                return

            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if (w, h) == self._last_size:
                return
            self._last_size = (w, h)

            height = max(60, int(h * 0.12 * 1.2))
            graph_h = max(10, int(height * 0.2))
            for frame, graph in self.perf_cards:
                try:
                    frame.configure(height=height)
                    graph.configure(height=graph_h)
                except Exception:
                    pass

            for frame in self.stat_cards:
                try:
                    frame.configure(height=height)
                except Exception:
                    pass

        except Exception:
            pass

    def update_dashboard(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            ghz = (
                self.cpu_reader.read()
                if self.cpu_reader and hasattr(self.cpu_reader, "read")
                else 0
            )
            cores = psutil.cpu_count(logical=True) or 0

            self.cpu_history.append(cpu)
            self.ram_history.append(ram.percent)
            self.disk_history.append(disk.percent)

            self.cpu_card["value"].configure(
                text=f"{cpu:.0f}% {ghz:.2f} GHz / {cores} threads"
            )
            self.ram_card["value"].configure(
                text=f"{ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB ({ram.percent:.0f}%)"
            )
            self.disk_card["value"].configure(text=f"{disk.percent:.0f}% used")

            for card, hist in (
                (self.cpu_card, self.cpu_history),
                (self.ram_card, self.ram_history),
                (self.disk_card, self.disk_history),
            ):
                self.draw_graph(card["graph"], hist, card["color"], card["line_id"])
        except Exception:
            pass

        self.root.after(1000, self.update_dashboard)

    def add_rows_batch(self, rows, muted=False):
        for idx, r in enumerate(rows):
            try:
                row_id = f"r{self.row_counter}"
                self.row_counter += 1
                tag = "muted" if muted else ("even" if idx % 2 == 0 else "odd")
                self.table.insert("", "end", iid=row_id, values=r[:3], tags=(tag,))
                if self.action_table_visible and self.action_table:
                    action_text = r[3] if len(r) > 3 else ""
                    self.action_table.insert(
                        "",
                        "end",
                        iid=row_id,
                        values=(action_text,),
                        tags=("action",),
                    )
            except Exception:
                pass

    def show_action_column(self, show: bool):
        self.action_table_visible = bool(show)
        try:
            if not self.action_table or not self.action_frame:
                return
            if show:
                self.action_table.heading("action", text="Uninstall")
                self.action_table.column("action", width=self.action_width, stretch=True)
                self.action_frame.configure(
                    width=self.action_width + max(6, int(12 * UI_SCALE))
                )
            else:
                self.action_table.heading("action", text="")
                self.action_table.column("action", width=0, stretch=False)
                self.action_frame.configure(width=0)
        except Exception:
            pass

    def set_view(self, view_name):
        self.current_view = view_name
        if view_name != "installed_apps":
            self.installed_app_map = {}
            self.show_action_column(False)
        else:
            self.show_action_column(True)

    def bind_table_scroll(self):
        def _on_mousewheel(event):
            delta = -1 * int(event.delta / 120) if event.delta else 0
            if delta == 0:
                return
            self.table.yview_scroll(delta, "units")
            if self.action_table_visible and self.action_table:
                self.action_table.yview_scroll(delta, "units")
            return "break"

        def _on_linux_scroll(event):
            delta = -1 if event.num == 4 else 1
            self.table.yview_scroll(delta, "units")
            if self.action_table_visible and self.action_table:
                self.action_table.yview_scroll(delta, "units")
            return "break"

        for widget in (self.table, self.action_table):
            if not widget:
                continue
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>", _on_linux_scroll, add="+")
            widget.bind("<Button-5>", _on_linux_scroll, add="+")

    def on_scrollbar(self, *args):
        self.table.yview(*args)
        if self.action_table_visible and self.action_table:
            self.action_table.yview(*args)

    def on_action_click(self, event):
        if self.current_view != "installed_apps":
            return

        col = self.action_table.identify_column(event.x)
        if col != self.action_column_id:
            return

        row_id = self.action_table.identify_row(event.y)
        if not row_id:
            return "break"

        # Sync selection to main table
        try:
            self.table.selection_set(row_id)
            self.table.focus(row_id)
            self.on_table_select(None)
        except Exception:
            pass

        values = self.table.item(row_id).get("values", [])
        if not values or len(values) < 3:
            return "break"

        key = (values[0], values[1], values[2])
        app = self.installed_app_map.get(key)
        if not app:
            messagebox.showwarning("Uninstall", "Uninstall data not available.")
            return "break"

        self.uninstall_app(app)
        return "break"

    def on_action_motion(self, event):
        if not self.action_table or not self.action_table_visible:
            return

        row_id = self.action_table.identify_row(event.y)
        if row_id == self.action_hover_id:
            return

        if self.action_hover_id:
            try:
                self.action_table.item(self.action_hover_id, tags=("action",))
            except Exception:
                pass

        self.action_hover_id = row_id
        if row_id:
            try:
                self.action_table.item(row_id, tags=("action_hover",))
            except Exception:
                pass

    def on_action_leave(self, event):
        if not self.action_table:
            return
        if self.action_hover_id:
            try:
                self.action_table.item(self.action_hover_id, tags=("action",))
            except Exception:
                pass
        self.action_hover_id = None

    def on_table_select(self, event):
        if not self.action_table or not self.action_table_visible:
            return

        selected = self.table.selection()
        if not selected:
            if self.action_selected_id:
                try:
                    self.action_table.item(self.action_selected_id, tags=("action",))
                except Exception:
                    pass
            self.action_selected_id = None
            return

        row_id = selected[0]
        if self.action_selected_id and self.action_selected_id != row_id:
            try:
                self.action_table.item(self.action_selected_id, tags=("action",))
            except Exception:
                pass

        self.action_selected_id = row_id
        try:
            self.action_table.item(row_id, tags=("action_selected",))
        except Exception:
            pass

    def clear_table(self):
        for row in list(self.table.get_children()):
            try:
                self.table.delete(row)
            except Exception:
                pass
        if self.action_table:
            for row in list(self.action_table.get_children()):
                try:
                    self.action_table.delete(row)
                except Exception:
                    pass
        self.row_counter = 0

    def show_empty_state(self, message):
        self.clear_table()
        self.add_rows_batch([(message, "", "", "")], muted=True)

    def update_stats(self):
        try:
            self.card_deleted.configure(text=f"{self.last_cleaned} files")
            self.card_recoverable.configure(text=f"{self.last_size_mb:.2f} MB")
            self.card_protected.configure(text=f"{self.protected_count} files")
            self.progress.set(0)
        except Exception:
            pass

    def set_progress(self, value: float):
        try:
            v = max(0.0, min(1.0, float(value)))
            self.progress.set(v)
        except Exception:
            pass

    def preview_files(self, folder: Path):
        self.set_view(None)
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        rows, total = [], 0
        try:
            i = 0
            for root_dir, _, files in os.walk(folder):
                for fname in files:
                    if i >= PREVIEW_SAMPLE_ROWS:
                        break
                    try:
                        path = Path(root_dir) / fname
                        size = path.stat().st_size
                        total += size
                        rows.append((path.name, format_size(size), "Ready to clean"))
                        i += 1
                    except Exception:
                        continue
                if i >= PREVIEW_SAMPLE_ROWS:
                    break
        except Exception:
            pass

        if rows:
            self.add_rows_batch(rows)
        else:
            self.show_empty_state("No items found in preview.")
        self.card_recoverable.configure(text=f"{total/(1024**2):.2f} MB (sample)")

    def toggle_preview_clean(self, key, folder, button, preview_text, clean_text):
        if not self.preview_ready.get(key, False):
            self.preview_files(folder)
            button.configure(text=clean_text)
        else:
            self.confirm_and_clean(folder)
            button.configure(text=preview_text)
        self.preview_ready[key] = not self.preview_ready.get(key, False)

    def handle_temp_button(self):
        self.toggle_preview_clean(
            "temp",
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            self.temp_button,
            "Preview Windows Temp",
            "Clean Windows Temp",
        )

    def handle_user_temp_button(self):
        self.toggle_preview_clean(
            "user_temp",
            Path(os.path.expandvars(r"%temp%")),
            self.user_temp_button,
            "Preview User Temp",
            "Clean User Temp",
        )

    def confirm_and_clean(self, folder):
        self.set_view(None)
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        if not messagebox.askyesno(
            "Confirm Cleanup", f"Remove files in:\n{folder}\n\nContinue?"
        ):
            return

        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            try:
                clean_folder(folder, self)
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def clean_browser_cache(self):
        self.set_view(None)
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()

        if browser_running_improved():
            messagebox.showwarning(
                "Browser Open",
                "Please close Chrome or Edge before cleaning browser cache.",
            )
            return

        self.reset_stats()
        self.set_busy(True)

        def worker():
            try:
                run_browser_clean(self)
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def clean_recycle_bin(self):
        self.set_view(None)
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.set_busy(True)

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            self.add_rows_batch([("Recycle Bin", "-", "Emptied successfully")])
        except Exception as e:
            self.add_rows_batch([("Recycle Bin", "-", f"Error: {e}")], muted=True)
        finally:
            self.update_stats()
            self.set_busy(False)

    def clean_all(self):
        self.set_view(None)
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%")),
        ]

        if not messagebox.askyesno(
            "Confirm Full Cleanup", "Clean all temporary folders and recycle bin?"
        ):
            return

        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.reset_stats()
        self.set_busy(True)

        def worker():
            for folder in folders:
                try:
                    clean_folder(folder, self, unlock=False)
                except Exception as e:
                    self.root.after(
                        0,
                        lambda ee=e: self.add_rows_batch(
                            [(str(folder), "-", f"Error: {ee}")]
                        ),
                    )

            try:
                ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            except Exception:
                pass

            self.root.after(0, self.update_stats)
            self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def show_installed_apps(self):
        self.set_view("installed_apps")
        self.clear_table()
        self.set_table_headers("Application", "Version", "Publisher", "Uninstall")

        try:
            apps = get_installed_apps_detailed()
            if not apps:
                self.show_empty_state("No installed apps found.")
                return

            rows = [(a["name"], a["version"], a["publisher"], "Uninstall") for a in apps]
            self.add_rows_batch(rows)

            app_map = {}
            for app in apps:
                key = (app["name"], app["version"], app["publisher"])
                if key not in app_map:
                    app_map[key] = app
            self.installed_app_map = app_map
            self.on_table_select(None)
        except Exception as e:
            self.show_empty_state(f"Installed Apps error: {e}")

    def normalize_uninstall_cmd(self, cmd):
        cmd = (cmd or "").strip()
        if not cmd:
            return ""

        if re.search(r"\bmsiexec(\.exe)?\b", cmd, flags=re.IGNORECASE):
            if not re.search(r"\s/([xX])\b", cmd):
                cmd = re.sub(r"\s/([iI])\b", " /X", cmd, count=1)

        return cmd

    def uninstall_app(self, app):
        name = app.get("name", "this application")
        uninstall = app.get("uninstall", "")
        quiet_uninstall = app.get("quiet_uninstall", "")

        cmd = uninstall or quiet_uninstall
        if not cmd:
            messagebox.showwarning(
                "Uninstall", f"No uninstall command found for:\n{name}"
            )
            return

        cmd = self.normalize_uninstall_cmd(cmd)

        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            messagebox.showerror("Uninstall", f"Failed to start: {e}")

    def show_startup_apps(self):
        self.set_view("startup_apps")
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        try:
            self.table.unbind("<Double-1>")
        except Exception:
            pass

        self.clear_table()
        self.set_table_headers("Application", "Status", "Source")

        try:
            apps = get_startup_apps()

            if not apps:
                self.show_empty_state("No startup apps found.")
                return

            visible_rows = [(a[0], a[1], a[2]) for a in apps]
            self.add_rows_batch(visible_rows)

            startup_map = {a[0]: a for a in apps}

            def toggle_selected(event):
                try:
                    row_id = self.table.identify_row(event.y)
                    if not row_id:
                        return

                    values = self.table.item(row_id).get("values", [])
                    if not values:
                        return

                    app_name = values[0]
                    item = startup_map.get(app_name)
                    if not item:
                        return

                    enable = item[1].lower() == "disabled"
                    result = toggle_startup_app(app_name, enable, registry_name=item[3])

                    ok = result[0] if isinstance(result, tuple) else bool(result)
                    msg = (
                        result[1]
                        if isinstance(result, tuple) and len(result) > 1
                        else None
                    )

                    if ok:
                        self.show_startup_apps()
                    else:
                        messagebox.showwarning("Startup Apps", msg or "Toggle failed")

                except Exception as e:
                    messagebox.showerror("Startup Apps", f"Toggle failed: {e}")

            self.table.bind("<Double-1>", toggle_selected)

        except Exception as e:
            self.show_empty_state(f"Startup Apps error: {e}")

    def run_speed_test_ui(self):
        self.set_view(None)
        win = ctk.CTkToplevel(self.root)
        win.title("Speed Test")
        win_w = 260
        win_h = 160
        win.geometry(f"{win_w}x{win_h}")
        self.center_window(win_w, win_h, parent=win)
        win.transient(self.root)
        win.lift()
        win.focus_force()
        try:
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
        except Exception:
            pass

        self.set_busy(True)
        try:
            win.grab_set()
        except Exception:
            pass

        def on_close():
            try:
                win.grab_release()
            except Exception:
                pass
            self.set_busy(False)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        body = ctk.CTkFrame(win, fg_color=THEME["surface"], corner_radius=16)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            body, text="Running speed test...", font=ui_font(12, "bold")
        ).pack(pady=(14, 10))

        prog = ctk.CTkProgressBar(
            body, mode="indeterminate", height=10, progress_color=THEME["accent"]
        )
        prog.pack(fill="x", padx=12, pady=(0, 10))
        prog.start()

        def worker():
            res = run_speed_test()

            def finish():
                prog.stop()
                txt = (
                    f"Ping: {res['ping']} ms\n"
                    f"Download: {res['download']} Mbps\n"
                    f"Upload: {res['upload']} Mbps"
                )
                messagebox.showinfo("Speed Test Results", txt)
                on_close()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_basic_tools(self):
        self.set_view(None)
        self.clear_table()
        self.set_table_headers("Tool", "Status", "Notes")

        try:
            self.add_rows_batch(check_basic_tools())
        except Exception as e:
            self.show_empty_state(f"Runtime Check error: {e}")

    # Export report removed per request

    def open_scheduler_window(self):
        self.set_view(None)
        win = ctk.CTkToplevel(self.root)
        win.title("Scheduled Cleanup")
        win_w = 260
        win_h = 340
        win.geometry(f"{win_w}x{win_h}")
        win.resizable(False, False)
        self.center_window(win_w, win_h, parent=win)
        win.transient(self.root)
        win.lift()
        win.focus_force()
        try:
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
        except Exception:
            pass

        body = ctk.CTkFrame(win, fg_color=THEME["surface"], corner_radius=16)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            body,
            text="Automatic Cleanup Scheduler",
            font=ui_font(14, "bold"),
            text_color=THEME["text"],
        ).pack(pady=(10, 12))

        mode = ctk.StringVar(value="Weekly")
        for option in ["Daily", "Weekly", "Monthly"]:
            ctk.CTkRadioButton(
                body,
                text=option,
                variable=mode,
                value=option,
                fg_color=THEME["accent"],
            ).pack(pady=4)

        status_label = ctk.CTkLabel(
            body,
            text=f"Current: {'Active' if task_exists() else 'Not active'}",
            text_color=THEME["muted"],
        )
        status_label.pack(pady=(10, 12))

        def create_schedule():
            ok, msg = create_task(sys.executable, mode.get())
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(
                text=f"Current: {'Active' if task_exists() else 'Not active'}"
            )

        def remove_schedule():
            ok, msg = delete_task()
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(
                text=f"Current: {'Active' if task_exists() else 'Not active'}"
            )

        ctk.CTkButton(
            body,
            text="Create Schedule",
            height=max(22, int(32 * BUTTON_SCALE)),
            corner_radius=10,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            command=create_schedule,
        ).pack(pady=(8, 6), fill="x", padx=10)
        ctk.CTkButton(
            body,
            text="Remove Schedule",
            height=max(22, int(32 * BUTTON_SCALE)),
            corner_radius=10,
            fg_color=THEME["surface_alt"],
            hover_color="#1a2230",
            border_width=1,
            border_color=THEME["card_border"],
            command=remove_schedule,
        ).pack(pady=(0, 6), fill="x", padx=10)

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for w in getattr(self, "sidebar_buttons", []):
            try:
                w.configure(state=state)
            except Exception:
                pass
