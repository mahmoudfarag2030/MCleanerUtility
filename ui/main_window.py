"""Main application window."""

import ctypes
import math
import os
import sys
import threading
from collections import deque
from pathlib import Path

import customtkinter as ctk
import psutil
from tkinter import Canvas, messagebox, ttk

from cleaners import clean_folder, clean_browser_cache as run_browser_clean
from installed_apps import get_installed_apps
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

UI_DENSITY = 0.75
WINDOW_HEIGHT_DENSITY = 0.7
WINDOW_WIDTH_DENSITY = 0.85


class MCleaner:
    def __init__(self, root):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = root
        self.root.title(
            f"MCleaner v{APP_VERSION} (build {BUILD_VERSION}) {'(Administrator)' if is_admin() else '(Standard Mode)'}"
        )
        
        # Calculate responsive window size based on screen resolution
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Track UI scaling to compensate for high-DPI scaling (e.g., 125%, 150%).
        # Some customtkinter versions lack get_widget_scaling; fall back safely.
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

        # Account for taskbar (approximately 50 pixels)
        available_height = screen_height - 50

        # Use 90% of available screen size, but cap at reasonable maximums
        target_width = min(
            int(screen_width * 0.9 * WINDOW_WIDTH_DENSITY),
            int(1200 * WINDOW_WIDTH_DENSITY),
        )
        target_height = min(
            int(available_height * 0.9 * WINDOW_HEIGHT_DENSITY),
            int(780 * WINDOW_HEIGHT_DENSITY),
        )

        # Ensure minimum usable size
        target_width = max(target_width, int(1080 * WINDOW_WIDTH_DENSITY))
        target_height = max(target_height, int(700 * WINDOW_HEIGHT_DENSITY))

        # If available screen is smaller than our minimum, use 95% of available size
        if screen_width < 1080 or available_height < 700:
            target_width = int(screen_width * 0.95 * WINDOW_WIDTH_DENSITY)
            target_height = int(available_height * 0.95 * WINDOW_HEIGHT_DENSITY)

        # Scale down on high-DPI displays to prevent overly large UI
        target_width = max(int(target_width / scale), 640)
        target_height = max(int(target_height / scale), 360)

        min_width = max(int(1080 * WINDOW_WIDTH_DENSITY / scale), 640)
        min_height = max(int(700 * WINDOW_HEIGHT_DENSITY / scale), 360)

        self.root.geometry(f"{target_width}x{target_height}")
        self.root.minsize(min_width, min_height)
        self.center_window(target_width, target_height)

        # Store values for responsive layouts
        self.ui_scale = scale
        self.window_width = target_width
        self.window_height = target_height

        self.preview_ready = {"temp": False, "user_temp": False}
        self.badge_frames = []
        self.busy = False
        self.cpu_reader = None

        self.cpu_history = deque([0] * 80, maxlen=80)
        self.ram_history = deque([0] * 80, maxlen=80)
        self.disk_history = deque([0] * 80, maxlen=80)

        self.reset_stats()
        self._build_ui()

        self.root.after(CPU_READER_INIT_DELAY_MS, self.init_cpu_reader)
        self.root.after(300, self.update_dashboard)
        self.animate_badges()

    def reset_stats(self):
        self.last_cleaned = 0
        self.last_size_mb = 0.0
        self.protected_count = 0

    def center_window(self, width, height, parent=None):
        """Center a window on the screen or relative to a parent window."""
        win = parent if parent is not None else self.root
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        
        # Account for taskbar (typically 40-50 pixels at bottom)
        # Use available height minus a margin for taskbar
        available_h = screen_h - 50
        
        x = (screen_w - width) // 2
        y = (available_h - height) // 2
        
        # Ensure y is not negative (for very small screens)
        y = max(0, y)
        
        win.geometry(f"{width}x{height}+{x}+{y}")

    def init_cpu_reader(self):
        try:
            self.cpu_reader = CpuSpeedReader()
        except Exception:
            self.cpu_reader = None

    def set_table_headers(self, h1="File", h2="Size", h3="Status"):
        try:
            self.table.heading("file", text=h1)
            self.table.heading("size", text=h2)
            self.table.heading("status", text=h3)
        except Exception:
            pass

    def _build_ui(self):
        main = ctk.CTkFrame(self.root)
        main.pack(fill="both", expand=True)

        # Determine current effective window width (fallback to screen size)
        win_width = getattr(self, "window_width", self.root.winfo_screenwidth())
        scale = getattr(self, "ui_scale", 1.0)
        small_screen = win_width <= 1366
        density = UI_DENSITY

        # Compact padding for smaller screens (reduces whitespace between elements)
        outer_base = 10 if not small_screen else 6
        inner_base = 6 if not small_screen else 4
        button_padx_base = 12 if not small_screen else 10
        button_pady_base = 5 if not small_screen else 4

        outer_pad = max(2, int(outer_base * density / scale))
        inner_pad = max(2, int(inner_base * density / scale))
        button_padx = max(4, int(button_padx_base * density / scale))
        button_pady = max(2, int(button_pady_base * density / scale))

        # Calculate responsive sidebar width
        if small_screen:
            sidebar_width = max(180, min(240, int(win_width * 0.20)))
        else:
            sidebar_width = max(200, min(280, int(win_width * 0.22)))

        sidebar = ctk.CTkFrame(main, width=sidebar_width, corner_radius=20)
        sidebar.pack(side="left", fill="y", padx=outer_pad, pady=outer_pad)
        sidebar.pack_propagate(False)

        # Adjust font sizes and button heights for small screens and high-DPI scaling
        base_title = 24 if small_screen else 30
        base_version = 10 if small_screen else 12
        base_button_main = 50 if small_screen else 56
        base_button_secondary = 42 if small_screen else 48

        title_font = ("Segoe UI", max(10, int(base_title / scale)), "bold")
        version_font = ("Segoe UI", max(8, int(base_version / scale)))
        button_main_height = max(24, int(base_button_main * density / scale))
        button_secondary_height = max(22, int(base_button_secondary * density / scale))

        ctk.CTkLabel(sidebar, text="MCleaner", font=title_font).pack(
            pady=(max(4, int(18 * density / scale)), max(2, int(4 * density / scale)))
        )
        ctk.CTkLabel(
            sidebar,
            text=f"v{APP_VERSION} (build {BUILD_VERSION}) • Author: MAF",
            font=version_font,
            wraplength=sidebar_width - 24,
            justify="left",
            anchor="w",
        ).pack(pady=(0, max(3, int(10 * density / scale))))

        if small_screen:
            buttons = [
                ("⚡ Clean All", self.clean_all, button_main_height),
                ("🧹 Preview Temp", self.handle_temp_button, button_secondary_height),
                ("🧹 User Temp", self.handle_user_temp_button, button_secondary_height),
                ("🌐 Clean Cache", self.clean_browser_cache, button_secondary_height),
                ("🗑 Empty Bin", self.clean_recycle_bin, button_secondary_height),
                ("⏰ Scheduler", self.open_scheduler_window, button_secondary_height),
                ("📦 Installed", self.show_installed_apps, button_secondary_height),
                ("🚀 Startup", self.show_startup_apps, button_secondary_height),
                ("📡 Speed Test", self.run_speed_test_ui, button_secondary_height),
                ("🔧 Runtime", self.check_basic_tools, button_secondary_height),
            ]
        else:
            buttons = [
                ("⚡ Clean Everything", self.clean_all, button_main_height),
                ("🧹 Preview Windows Temp", self.handle_temp_button, button_secondary_height),
                ("🧹 Preview User Temp", self.handle_user_temp_button, button_secondary_height),
                ("🌐 Clean Browser Cache", self.clean_browser_cache, button_secondary_height),
                ("🗑 Empty Recycle Bin", self.clean_recycle_bin, button_secondary_height),
                ("⏰ Scheduled Cleanup", self.open_scheduler_window, button_secondary_height),
                ("📦 Installed Apps", self.show_installed_apps, button_secondary_height),
                ("🚀 Startup Apps", self.show_startup_apps, button_secondary_height),
                ("📡 Internet Speed Test", self.run_speed_test_ui, button_secondary_height),
                ("🔧 Runtime checker", self.check_basic_tools, button_secondary_height),
            ]

        refs = []
        for text, cmd, h in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                height=h,
                corner_radius=16 if h == button_main_height else 14,
                fg_color="#1f2937",
                hover_color="#2b6ef6",
                command=cmd,
            )
            btn.pack(fill="x", padx=button_padx, pady=button_pady)
            refs.append(btn)

        self.clean_everything_btn, self.temp_button, self.user_temp_button = refs[:3]
        self.sidebar_buttons = refs

        content = ctk.CTkFrame(main)
        content.pack(
            side="right",
            fill="both",
            expand=True,
            padx=outer_pad,
            pady=outer_pad,
        )

        # Determine sizes for performance cards and stat badges based on scale
        perf_card_height = max(60, int(110 * density / scale))
        stat_badge_height = max(38, int(70 * density / scale))
        perf_title_font = ("Segoe UI", max(10, int(11 / scale)), "bold")
        perf_value_font = ("Segoe UI", max(10, int(13 / scale)))
        stat_title_font = ("Segoe UI", max(9, int(10 / scale)), "bold")
        stat_value_font = ("Segoe UI", max(10, int(12 / scale)))

        self.card_frame_padx = max(3, int(5 * density / scale))
        self.card_label_padx = max(6, int(10 * density / scale))
        self.card_label_pady = (
            max(2, int(8 * density / scale)),
            max(1, int(2 * density / scale)),
        )
        self.card_graph_padx = max(4, int(8 * density / scale))
        self.card_graph_pady = max(2, int(5 * density / scale))
        self.graph_height = max(18, int(40 * density / scale))

        self.badge_padx = max(3, int(5 * density / scale))
        self.badge_label_pady = (
            max(2, int(8 * density / scale)),
            max(1, int(2 * density / scale)),
        )

        perf = ctk.CTkFrame(content, fg_color="transparent")
        perf.pack(fill="x", pady=inner_pad)

        self.cpu_card = self.make_perf_card(
            perf,
            "CPU",
            "#3b82f6",
            perf_card_height,
            perf_title_font,
            perf_value_font,
            graph_height=self.graph_height,
        )
        self.ram_card = self.make_perf_card(
            perf,
            "Memory",
            "#8b5cf6",
            perf_card_height,
            perf_title_font,
            perf_value_font,
            graph_height=self.graph_height,
        )
        self.disk_card = self.make_perf_card(
            perf,
            "Disk",
            "#10b981",
            perf_card_height,
            perf_title_font,
            perf_value_font,
            graph_height=self.graph_height,
        )

        stats = ctk.CTkFrame(content, fg_color="transparent")
        stats.pack(fill="x", pady=inner_pad)

        self.card_recoverable = self.make_stat_badge(
            stats,
            "Recoverable",
            "   0.00 MB",
            stat_badge_height,
            stat_title_font,
            stat_value_font,
        )
        self.card_deleted = self.make_stat_badge(
            stats,
            "Deleted",
            "0 files",
            stat_badge_height,
            stat_title_font,
            stat_value_font,
        )
        self.card_protected = self.make_stat_badge(
            stats,
            "Permission Needed",
            "0 files",
            stat_badge_height,
            stat_title_font,
            stat_value_font,
        )

        self.progress = ctk.CTkProgressBar(content)
        self.progress.pack(fill="x", padx=inner_pad, pady=inner_pad)
        self.progress.set(0)

        table_frame = ctk.CTkFrame(content)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        row_height = max(14, int(30 * density / scale))
        table_font = ("Segoe UI", max(9, int(10 / scale)))
        heading_font = ("Segoe UI", max(9, int(10 / scale)), "bold")

        style.configure(
            "Treeview",
            background="#111827",
            foreground="white",
            fieldbackground="#111827",
            rowheight=row_height,
            font=table_font,
        )
        style.configure(
            "Treeview.Heading",
            background="#1f2937",
            foreground="white",
            font=heading_font,
        )
        style.map("Treeview", background=[("selected", "#2563eb")])

        self.table = ttk.Treeview(
            table_frame, columns=("file", "size", "status"), show="headings"
        )

        # Make table columns responsive to window size
        def update_table_columns(event=None):
            try:
                table_width = self.table.winfo_width()
                if table_width > 100:  # Only update if table has been sized
                    if small_screen:
                        min_file, min_size, min_status = 150, 60, 100
                    else:
                        min_file, min_size, min_status = 200, 80, 120

                    # Allocate space proportionally: file (55%), size (16%), status (29%)
                    file_width = max(min_file, int(table_width * 0.55))
                    size_width = max(min_size, int(table_width * 0.16))
                    status_width = max(min_status, table_width - file_width - size_width)

                    self.table.column("file", width=file_width)
                    self.table.column("size", width=size_width)
                    self.table.column("status", width=status_width)
            except Exception:
                pass

        self.table.bind("<Configure>", update_table_columns)

        # Set initial column widths (will be updated after layout)
        initial_widths = {
            "file": 200 if not small_screen else 150,
            "size": 80 if not small_screen else 60,
            "status": 120 if not small_screen else 100,
        }

        for col in ("file", "size", "status"):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=initial_widths[col])

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.table.yview
        )
        self.table.configure(yscroll=scrollbar.set)

        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def make_perf_card(
        self,
        parent,
        title,
        color,
        height=110,
        title_font=("Segoe UI", 11, "bold"),
        value_font=("Segoe UI", 13),
        graph_height=40,
    ):
        frame = ctk.CTkFrame(parent, height=height, corner_radius=16, width=1)
        frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=getattr(self, "card_frame_padx", 5),
        )
        frame.pack_propagate(False)

        label_padx = getattr(self, "card_label_padx", 10)
        label_pady = getattr(self, "card_label_pady", (8, 2))
        graph_padx = getattr(self, "card_graph_padx", 8)
        graph_pady = getattr(self, "card_graph_pady", 5)

        ctk.CTkLabel(frame, text=title, font=title_font).pack(
            anchor="w",
            padx=label_padx,
            pady=label_pady,
        )
        value = ctk.CTkLabel(frame, text="0", font=value_font)
        value.pack(anchor="w", padx=label_padx)

        graph = Canvas(frame, height=graph_height, bg="#1a1a1a", highlightthickness=0)
        graph.pack(fill="x", padx=graph_padx, pady=graph_pady)

        mid = max(1, int(graph_height / 2))
        line_id = graph.create_line(0, mid, 1, mid, fill=color, width=2, smooth=True)

        return {
            "value": value,
            "graph": graph,
            "color": color,
            "line_id": line_id,
        }

    def make_stat_badge(
        self,
        parent,
        title,
        value,
        height=70,
        title_font=("Segoe UI", 10, "bold"),
        value_font=("Segoe UI", 12),
    ):
        frame = ctk.CTkFrame(parent, height=height, corner_radius=18, fg_color="#111827")
        frame.pack(side="left", fill="x", expand=True, padx=getattr(self, "badge_padx", 5))

        ctk.CTkLabel(frame, text=title, font=title_font).pack(
            pady=getattr(self, "badge_label_pady", (8, 2))
        )
        val = ctk.CTkLabel(frame, text=value, font=value_font)
        val.pack()

        self.badge_frames.append((frame, val))
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
            factor = 1 + 0.05 * math.sin(phase + i)
            c = int(17 * factor)
            try:
                frame.configure(fg_color=f"#{c:02x}{24:02x}{39:02x}")
            except Exception:
                pass

        self.root.after(140, lambda: self.animate_badges(phase + 0.25))

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

    def add_rows_batch(self, rows):
        for r in rows:
            try:
                self.table.insert("", "end", values=r[:3])
            except Exception:
                pass

    def clear_table(self):
        for row in list(self.table.get_children()):
            try:
                self.table.delete(row)
            except Exception:
                pass

    def update_stats(self):
        try:
            self.card_deleted.configure(text=f"{self.last_cleaned} files")
            self.card_recoverable.configure(text=f"{self.last_size_mb:.2f} MB")
            self.card_protected.configure(text=f"{self.protected_count} files")
            self.progress.set(0)
        except Exception:
            pass

    def set_progress(self, value: float):
        """Update the progress bar (expects a value between 0 and 1)."""
        try:
            v = max(0.0, min(1.0, float(value)))
            self.progress.set(v)
        except Exception:
            pass

    def preview_files(self, folder: Path):
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

        self.add_rows_batch(rows)
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
            "🧹 Preview Windows Temp",
            "🧹 Clean Windows Temp",
        )

    def handle_user_temp_button(self):
        self.toggle_preview_clean(
            "user_temp",
            Path(os.path.expandvars(r"%temp%")),
            self.user_temp_button,
            "🧹 Preview User Temp",
            "🧹 Clean User Temp",
        )

    def confirm_and_clean(self, folder):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
            return

        if not messagebox.askyesno(
            "Confirm Cleanup",
            f"Remove files in:\n{folder}\n\nContinue?",
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
        self.set_table_headers("File", "Size", "Status")
        self.clear_table()
        self.set_busy(True)

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
            self.add_rows_batch([("Recycle Bin", "-", "Emptied successfully")])
        except Exception as e:
            self.add_rows_batch([("Recycle Bin", "-", f"Error: {e}")])
        finally:
            self.update_stats()
            self.set_busy(False)

    def clean_all(self):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
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
        self.clear_table()
        self.set_table_headers("Application", "Version", "Publisher")

        try:
            apps = get_installed_apps()
            self.add_rows_batch(apps if apps else [("No applications found", "-", "-")])
        except Exception as e:
            self.add_rows_batch([("Installed Apps", "-", f"Error: {e}")])

    def show_startup_apps(self):
        if self.busy:
            messagebox.showinfo(
                "Busy", "Another operation is in progress. Please wait."
            )
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
                self.add_rows_batch([("No startup apps found", "-", "-")])
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
            self.add_rows_batch([("Startup Apps", "-", f"Error: {e}")])

    def run_speed_test_ui(self):
        density = UI_DENSITY
        win = ctk.CTkToplevel(self.root)
        win.title("Speed Test")
        win_w = max(220, int(400 * density))
        win_h = max(140, int(220 * density))
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

        # Prevent the user from interacting with the main window during the speed test.
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

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=max(8, int(16 * density)), pady=max(8, int(16 * density)))

        lbl = ctk.CTkLabel(body, text="Running speed test...")
        lbl.pack(pady=(max(4, int(8 * density)), max(6, int(12 * density))))

        prog = ctk.CTkProgressBar(body, mode="indeterminate")
        prog.pack(fill="x", pady=(max(2, int(4 * density)), max(6, int(12 * density))))
        prog.start()

        def worker():
            res = run_speed_test()

            def finish():
                prog.stop()
                txt = f"Ping: {res['ping']} ms\nDownload: {res['download']} Mbps\nUpload: {res['upload']} Mbps"
                messagebox.showinfo("Speed Test Results", txt)
                on_close()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_basic_tools(self):
        self.clear_table()
        self.set_table_headers("Tool", "Status", "Notes")

        try:
            self.add_rows_batch(check_basic_tools())
        except Exception as e:
            self.add_rows_batch([("Runtime Check", "-", f"Error: {e}")])

    def open_scheduler_window(self):
        density = UI_DENSITY
        win = ctk.CTkToplevel(self.root)
        win.title("Scheduled Cleanup")
        win_w = max(240, int(400 * density))
        win_h = max(300, int(560 * density))
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

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(
            fill="both",
            expand=True,
            padx=max(12, int(25 * density)),
            pady=(max(10, int(20 * density)), max(14, int(30 * density))),
        )

        ctk.CTkLabel(
            body, text="Automatic Cleanup Scheduler", font=("Segoe UI", 18, "bold")
        ).pack(pady=(max(6, int(10 * density)), max(10, int(20 * density))))

        mode = ctk.StringVar(value="Weekly")

        for option in ["Daily", "Weekly", "Monthly"]:
            ctk.CTkRadioButton(body, text=option, variable=mode, value=option).pack(
                pady=max(4, int(8 * density))
            )

        status_label = ctk.CTkLabel(
            body, text=f"Current: {'Active' if task_exists() else 'Not active'}"
        )
        status_label.pack(pady=(max(10, int(18 * density)), max(10, int(18 * density))))

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

        btn_w = max(180, int(260 * density))
        btn_h = max(24, int(44 * density))
        ctk.CTkButton(
            body, text="Create Schedule", width=btn_w, height=btn_h, command=create_schedule
        ).pack(pady=(max(10, int(20 * density)), max(6, int(12 * density))))
        ctk.CTkButton(
            body,
            text="Remove Schedule",
            width=btn_w,
            height=btn_h,
            fg_color="#991b1b",
            hover_color="#b91c1c",
            command=remove_schedule,
        ).pack()

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for w in getattr(self, "sidebar_buttons", []):
            try:
                w.configure(state=state)
            except Exception:
                pass
