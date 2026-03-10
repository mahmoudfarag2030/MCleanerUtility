import os
import sys
import ctypes
from pathlib import Path

import customtkinter as ctk

from ui import MCleaner, SplashScreen
from cleaners import clean_folder


def run_silent_cleanup():
    folders = [
        Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
        Path(os.path.expandvars(r"%temp%"))
    ]

    for folder in folders:
        try:
            clean_folder(folder, None)
        except Exception as e:
            print(f"Scheduled cleanup error for {folder}: {e}")

    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1)
    except Exception:
        pass

    print("Scheduled cleanup finished")


def launch_gui():
    root = ctk.CTk()
    root.withdraw()

    splash = None

    try:
        splash = SplashScreen(root)
    except Exception:
        splash = None

    app = MCleaner(root)

    def show_main():
        root.deiconify()
        if splash:
            try:
                splash.close()
            except Exception:
                pass

    root.after(2200, show_main)
    root.mainloop()


def main():
    if "--run-silent" in sys.argv or "--run_silent" in sys.argv:
        run_silent_cleanup()
        sys.exit(0)

    launch_gui()


if __name__ == "__main__":
    main()
