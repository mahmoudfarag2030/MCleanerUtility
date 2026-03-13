import os
import sys
import threading
import ctypes
import time
import math
from pathlib import Path
from collections import deque
from datetime import datetime

from cleaners import clean_folder, clean_browser_cache as run_browser_clean

import customtkinter as ctk
import psutil
from openpyxl import Workbook
from tkinter import ttk, messagebox, Canvas
from PIL import Image

from installed_apps import get_installed_apps
from helpers import is_admin, format_size, browser_running_improved
from system_tools import CpuSpeedReader, check_basic_tools
from startup_apps import get_startup_apps, toggle_startup_app
from speed_test import run_speed_test


try:
    from scheduler_manager import create_task, delete_task, task_exists
except Exception:
    def create_task(*args, **kwargs):
        return False, "Scheduler module unavailable"

    def delete_task(*args, **kwargs):
        return False, "Scheduler module unavailable"

    def task_exists():
        return False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


PREVIEW_SAMPLE_ROWS = 30
APP_VERSION = "0.9"
CPU_READER_INIT_DELAY_MS = 500


class SplashScreen:
    def __init__(self, parent):
        self.parent = parent
        self.root = ctk.CTkToplevel(parent)
        self.root.overrideredirect(True)
        self.root.configure(fg_color="#101820")

        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        img_full_path = resource_path("MCleaner.png")
        img_path = Path(img_full_path)

        if img_path.exists():
            img = Image.open(img_path).convert("RGBA")
            ratio = img.height / img.width
            w, h = 360, int(360 * ratio)

            self.image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            img_label = ctk.CTkLabel(self.root, image=self.image, text="")
            img_label.pack(fill="both", expand=True)

            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - (h + 60)) // 2  # add extra space for status labels

            self.root.geometry(f"{w}x{h+60}+{x}+{y}")

            footer = ctk.CTkFrame(self.root, fg_color="transparent")
            footer.pack(fill="x", side="bottom", pady=(6, 10))

            ctk.CTkLabel(footer, text=f"v{APP_VERSION}", font=("Segoe UI", 11, "bold")).pack()
            ctk.CTkLabel(footer, text="Initializing cleanup engine...", font=("Segoe UI", 10)).pack()
        else:
            self.root.geometry("360x220")
            ctk.CTkLabel(self.root, text="MCleaner", font=("Segoe UI", 26, "bold")).pack(expand=True)

            ctk.CTkLabel(self.root, text=f"v{APP_VERSION}", font=("Segoe UI", 11, "bold")).pack(pady=(8, 2))
            ctk.CTkLabel(self.root, text="Initializing cleanup engine...", font=("Segoe UI", 10)).pack()

        self.root.attributes("-alpha", 0.0)
        self.fade_in()
        self.root.after(2200, self.close)

    def fade_in(self):
        try:
            a = self.root.attributes("-alpha")
            if a < 1:
                self.root.attributes("-alpha", min(1, a + 0.08))
                self.root.after(40, self.fade_in)
        except Exception:
            pass

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class MCleaner:
    def __init__(self, root):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = root
        self.root.title(f"MCleaner v{APP_VERSION} {'(Administrator)' if is_admin() else '(Standard Mode)'}")
        self.root.geometry("1200x780")
        self.root.minsize(1080, 700)
        self.center_window(1200, 780)

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
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
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

        sidebar = ctk.CTkFrame(main, width=260, corner_radius=20)
        sidebar.pack(side="left", fill="y", padx=14, pady=14)
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="MCleaner", font=("Segoe UI", 30, "bold")).pack(pady=(22, 5))
        ctk.CTkLabel(sidebar, text=f"v{APP_VERSION} • Author: MAF", font=("Segoe UI", 12)).pack(pady=(0, 12))

        buttons = [
            ("⚡ Clean Everything", self.clean_all, 56),
            ("🧹 Preview Windows Temp", self.handle_temp_button, 48),
            ("🧹 Preview User Temp", self.handle_user_temp_button, 48),
            ("🌐 Clean Browser Cache", self.clean_browser_cache, 48),
            ("🗑 Empty Recycle Bin", self.clean_recycle_bin, 48),
            ("⏰ Scheduled Cleanup", self.open_scheduler_window, 48),
            ("📦 Installed Apps", self.show_installed_apps, 48),
            ("🚀 Startup Apps", self.show_startup_apps, 48),
            ("📡 Internet Speed Test", self.run_speed_test_ui, 48),
            ("🔧 Runtime checker", self.check_basic_tools, 48),
            ("📄 Export Report", self.export_excel_report, 48),
        ]

        refs = []
        for text, cmd, h in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                height=h,
                width=220,
                corner_radius=16 if h == 56 else 14,
                fg_color="#1f2937",
                hover_color="#2b6ef6",
                command=cmd
            )
            btn.pack(fill="x", padx=14, pady=6)
            refs.append(btn)

        self.clean_everything_btn, self.temp_button, self.user_temp_button = refs[:3]
        self.sidebar_buttons = refs

        content = ctk.CTkFrame(main)
        content.pack(side="right", fill="both", expand=True, padx=14, pady=14)

        perf = ctk.CTkFrame(content, fg_color="transparent")
        perf.pack(fill="x", pady=10)

        self.cpu_card = self.make_perf_card(perf, "CPU", "#3b82f6")
        self.ram_card = self.make_perf_card(perf, "Memory", "#8b5cf6")
        self.disk_card = self.make_perf_card(perf, "Disk", "#10b981")

        stats = ctk.CTkFrame(content, fg_color="transparent")
        stats.pack(fill="x", pady=8)

        self.card_recoverable = self.make_stat_badge(stats, "Recoverable", "   0.00 MB")
        self.card_deleted = self.make_stat_badge(stats, "Deleted", "0 files")
        self.card_protected = self.make_stat_badge(stats, "Permission Needed", "0 files")

        self.progress = ctk.CTkProgressBar(content)
        self.progress.pack(fill="x", padx=10, pady=10)
        self.progress.set(0)

        table_frame = ctk.CTkFrame(content)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Treeview", background="#111827", foreground="white", fieldbackground="#111827", rowheight=30)
        style.configure("Treeview.Heading", background="#1f2937", foreground="white")
        style.map("Treeview", background=[("selected", "#2563eb")])

        self.table = ttk.Treeview(table_frame, columns=("file", "size", "status"), show="headings")

        for col, width in zip(("file", "size", "status"), (560, 130, 240)):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscroll=scrollbar.set)

        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def make_perf_card(self, parent, title, color):
        frame = ctk.CTkFrame(parent, height=110, corner_radius=16, width=1)
        frame.pack(side="left", fill="both", expand=True, padx=5)
        frame.pack_propagate(False)

        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        value = ctk.CTkLabel(frame, text="0", font=("Segoe UI", 13))
        value.pack(anchor="w", padx=10)

        graph = Canvas(frame, height=40, bg="#1a1a1a", highlightthickness=0)
        graph.pack(fill="x", padx=8, pady=5)

        line_id = graph.create_line(0, 20, 1, 20, fill=color, width=2, smooth=True)

        return {
            "value": value,
            "graph": graph,
            "color": color,
            "line_id": line_id,
        }

    def make_stat_badge(self, parent, title, value):
        frame = ctk.CTkFrame(parent, height=70, corner_radius=18, fg_color="#111827")
        frame.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
        val = ctk.CTkLabel(frame, text=value, font=("Segoe UI", 12))
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
            ghz = self.cpu_reader.read() if self.cpu_reader and hasattr(self.cpu_reader, 'read') else 0
            cores = psutil.cpu_count(logical=True) or 0

            self.cpu_history.append(cpu)
            self.ram_history.append(ram.percent)
            self.disk_history.append(disk.percent)

            self.cpu_card["value"].configure(text=f"{cpu:.0f}% {ghz:.2f} GHz / {cores} threads")
            self.ram_card["value"].configure(text=f"{ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB ({ram.percent:.0f}%)")
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
        self.toggle_preview_clean("temp", Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp", self.temp_button, "🧹 Preview Windows Temp", "🧹 Clean Windows Temp")

    def handle_user_temp_button(self):
        self.toggle_preview_clean("user_temp", Path(os.path.expandvars(r"%temp%")), self.user_temp_button, "🧹 Preview User Temp", "🧹 Clean User Temp")

    def confirm_and_clean(self, folder):
        if self.busy:
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        if not messagebox.askyesno("Confirm Cleanup", f"Remove files in:\n{folder}\n\nContinue?"):
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
            messagebox.showwarning("Browser Open", "Please close Chrome or Edge before cleaning browser cache.")
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
            messagebox.showinfo("Busy", "Another operation is in progress. Please wait.")
            return

        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%"))
        ]

        if not messagebox.askyesno("Confirm Full Cleanup", "Clean all temporary folders and recycle bin?"):
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
                    self.root.after(0, lambda ee=e: self.add_rows_batch([(str(folder), "-", f"Error: {ee}")]))

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

                    result = toggle_startup_app(
                        app_name,
                        enable,
                        registry_name=item[3]
                    )

                    ok = result[0] if isinstance(result, tuple) else bool(result)
                    msg = result[1] if isinstance(result, tuple) and len(result) > 1 else None

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
        win = ctk.CTkToplevel(self.root)
        win.title("Speed Test")
        win.geometry("400x220")

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=16)

        lbl = ctk.CTkLabel(body, text="Running speed test...")
        lbl.pack(pady=(8, 12))

        prog = ctk.CTkProgressBar(body, mode="indeterminate")
        prog.pack(fill="x", pady=(4, 12))
        prog.start()

        def worker():
            res = run_speed_test()

            def finish():
                prog.stop()
                txt = f"Ping: {res['ping']} ms\nDownload: {res['download']} Mbps\nUpload: {res['upload']} Mbps"
                messagebox.showinfo("Speed Test Results", txt)
                win.destroy()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_basic_tools(self):
        self.clear_table()
        self.set_table_headers("Tool", "Status", "Notes")

        try:
            self.add_rows_batch(check_basic_tools())
        except Exception as e:
            self.add_rows_batch([("Runtime Check", "-", f"Error: {e}")])

    def export_excel_report(self):
        fn = f"MCleaner_Report_{datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Deleted Files", self.last_cleaned])
        ws.append(["Recovered MB", f"{self.last_size_mb:.2f}"])
        ws.append(["Permission Needed", self.protected_count])

        try:
            wb.save(fn)
            self.add_rows_batch([(fn, "-", "Saved successfully")])
        except Exception as e:
            self.add_rows_batch([(fn, "-", f"Error: {e}")])

    def open_scheduler_window(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Scheduled Cleanup")
        win.geometry("400x560")
        win.resizable(False, False)
        self.center_window(400, 560, parent=win)
        win.transient(self.root)
        win.lift()
        win.focus_force()
        try:
            win.attributes("-topmost", True)
            win.after(150, lambda: win.attributes("-topmost", False))
        except Exception:
            pass

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=(20, 30))

        ctk.CTkLabel(body, text="Automatic Cleanup Scheduler", font=("Segoe UI", 18, "bold")).pack(pady=(10, 20))

        mode = ctk.StringVar(value="Weekly")

        for option in ["Daily", "Weekly", "Monthly"]:
            ctk.CTkRadioButton(body, text=option, variable=mode, value=option).pack(pady=8)

        status_label = ctk.CTkLabel(body, text=f"Current: {'Active' if task_exists() else 'Not active'}")
        status_label.pack(pady=(18, 18))

        def create_schedule():
            ok, msg = create_task(sys.executable, mode.get())
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(text=f"Current: {'Active' if task_exists() else 'Not active'}")

        def remove_schedule():
            ok, msg = delete_task()
            messagebox.showinfo("Scheduler" if ok else "Scheduler Error", msg)
            status_label.configure(text=f"Current: {'Active' if task_exists() else 'Not active'}")

        ctk.CTkButton(body, text="Create Schedule", width=260, height=44, command=create_schedule).pack(pady=(20, 12))
        ctk.CTkButton(body, text="Remove Schedule", width=260, height=44, fg_color="#991b1b", hover_color="#b91c1c", command=remove_schedule).pack()

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        for w in getattr(self, "sidebar_buttons", []):
            try:
                w.configure(state=state)
            except Exception:
                pass


if __name__ == "__main__":
    if "--run-silent" in sys.argv or "--run_silent" in sys.argv:
        folders = [
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
            Path(os.path.expandvars(r"%temp%"))
        ]

        for folder in folders:
            try:
                clean_folder(folder, None)
            except Exception as e:
                print("Scheduled cleanup error for", folder, e)

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
        except Exception:
            pass

        print("Scheduled cleanup finished")
        sys.exit(0)

    root = ctk.CTk()
    root.withdraw()

    app = MCleaner(root)

    splash = None
    try:
        splash = SplashScreen(root)
    except Exception:
        pass

    def show_main():
        root.deiconify()
        if splash:
            try:
                splash.close()
            except Exception:
                pass

    root.after(2200, show_main)
    root.mainloop()
