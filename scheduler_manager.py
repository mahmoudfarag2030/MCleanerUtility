def open_scheduler_window(self):
    """
    Premium compact scheduler UI:
    - fixed-width radio cards
    - no clipped text
    - Windows 11 style compact layout
    """

    win = ctk.CTkToplevel(self.root)
    win.title("Scheduled Cleanup")
    win.geometry("390x220")
    win.resizable(False, False)

    try:
        win.transient(self.root)
        win.grab_set()
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(150, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

    # center window
    try:
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()

        sx = main_x + (main_w // 2) - 195
        sy = main_y + (main_h // 2) - 110
        win.geometry(f"390x220+{sx}+{sy}")
    except Exception:
        pass

    body = ctk.CTkFrame(
        win,
        fg_color="#111827",
        corner_radius=16
    )
    body.pack(fill="both", expand=True, padx=12, pady=12)

    ctk.CTkLabel(
        body,
        text="Automatic Cleanup",
        font=("Segoe UI", 15, "bold")
    ).pack(pady=(10, 12))

    mode = ctk.StringVar(value="Weekly")

    # fixed width radio cards
    radio_row = ctk.CTkFrame(body, fg_color="transparent")
    radio_row.pack(fill="x", padx=10)

    for option in ["Daily", "Weekly", "Monthly"]:
        card = ctk.CTkFrame(
            radio_row,
            width=115,
            height=42,
            fg_color="#1f2937",
            corner_radius=12
        )
        card.pack(side="left", padx=4)
        card.pack_propagate(False)

        rb = ctk.CTkRadioButton(
            card,
            text=option,
            variable=mode,
            value=option,
            font=("Segoe UI", 11)
        )
        rb.place(relx=0.5, rely=0.5, anchor="center")

    status_text_var = ctk.StringVar(value="Active" if task_exists() else "Not active")

    status_lbl = ctk.CTkLabel(
        body,
        text=f"Current: {status_text_var.get()}",
        font=("Segoe UI", 10)
    )
    status_lbl.pack(pady=(14, 10))

    def refresh_status():
        status_text_var.set("Active" if task_exists() else "Not active")
        status_lbl.configure(text=f"Current: {status_text_var.get()}")

    def create_schedule():
        exe_path = sys.executable
        ok, msg = create_task(exe_path, mode.get())

        if ok:
            messagebox.showinfo("Scheduler", msg)
        else:
            messagebox.showerror("Scheduler", msg)

        refresh_status()

    def remove_schedule():
        ok, msg = delete_task()

        if ok:
            messagebox.showinfo("Scheduler", msg)
        else:
            messagebox.showerror("Scheduler", msg)

        refresh_status()

    btn_row = ctk.CTkFrame(body, fg_color="transparent")
    btn_row.pack(pady=(4, 10))

    ctk.CTkButton(
        btn_row,
        text="Create",
        width=150,
        height=36,
        corner_radius=12,
        command=create_schedule
    ).pack(side="left", padx=6)

    ctk.CTkButton(
        btn_row,
        text="Remove",
        width=150,
        height=36,
        corner_radius=12,
        fg_color="#991b1b",
        hover_color="#b91c1c",
        command=remove_schedule
    ).pack(side="left", padx=6)

    def _on_close():
        try:
            win.grab_release()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", _on_close)