import customtkinter as ctk
from ui import MCleaner, SplashScreen

def main():
    root = ctk.CTk()
    root.withdraw()

    SplashScreen(root)

    def launch():
        for w in root.winfo_children():
            if isinstance(w, ctk.CTkToplevel):
                w.destroy()

        root.deiconify()
        MCleaner(root)

    root.after(1400, launch)
    root.mainloop()

if __name__ == "__main__":
    main()