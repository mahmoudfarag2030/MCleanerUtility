"""Splash screen window."""

from pathlib import Path

import customtkinter as ctk
from PIL import Image

from .constants import APP_VERSION, BUILD_VERSION, resource_path


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
            y = (screen_h - (h + 60)) // 2

            self.root.geometry(f"{w}x{h+60}+{x}+{y}")

            footer = ctk.CTkFrame(self.root, fg_color="transparent")
            footer.pack(fill="x", side="bottom", pady=(6, 10))

            ctk.CTkLabel(
                footer,
                text=f"v{APP_VERSION} (build {BUILD_VERSION})",
                font=("Segoe UI", 11, "bold"),
            ).pack()
            ctk.CTkLabel(
                footer, text="Initializing cleanup engine...", font=("Segoe UI", 10)
            ).pack()
        else:
            self.root.geometry("360x220")
            ctk.CTkLabel(
                self.root, text="MCleaner", font=("Segoe UI", 26, "bold")
            ).pack(expand=True)

            ctk.CTkLabel(
                self.root, text=f"v{APP_VERSION}", font=("Segoe UI", 11, "bold")
            ).pack(pady=(8, 2))
            ctk.CTkLabel(
                self.root, text="Initializing cleanup engine...", font=("Segoe UI", 10)
            ).pack()

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
