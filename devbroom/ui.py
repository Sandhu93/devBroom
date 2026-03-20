from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cleanup import delete_tree
from .models import NODE_MODULES_NAME, VENV_KIND, ScanTarget
from .scanner import human_size, iter_scan_targets


APP_TITLE = "DevBroom"
APP_SUBTITLE = "Developer Space Cleaner"
WINDOW_SIZE = "1100x680"
WINDOW_MIN_SIZE = (800, 500)
CHECKED_MARK = "[x]"
UNCHECKED_MARK = "[ ]"


class Palette:
    bg = "#13131f"
    fg = "#cdd6f4"
    accent = "#89b4fa"
    danger = "#f38ba8"
    warning = "#fab387"
    success = "#a6e3a1"
    header_bg = "#11111b"
    select_bg = "#313244"
    toolbar_bg = "#0d0d1a"
    muted = "#6c7086"
    button_bg = "#313244"
    row_even = "#1e1e2e"


def preferred_ui_fonts() -> tuple[str, str]:
    if os.name == "nt":
        return "Segoe UI", "Consolas"
    return "TkDefaultFont", "TkFixedFont"


class DevBroomApp(tk.Tk):
    COL_CHECK = "Selected"
    COL_TYPE = "Type"
    COL_SIZE = "Size"
    COL_PATH = "Path"

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} - {APP_SUBTITLE}")
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN_SIZE)
        self.configure(bg=Palette.bg)

        self._items: dict[str, ScanTarget] = {}
        self._row_tags: dict[str, str] = {}
        self._checked: set[str] = set()
        self._stop_event = threading.Event()
        self._scanning = False
        self._sort_state = {"key": "size", "descending": True}

        self._path_var = tk.StringVar(value=str(Path.home()))
        self._status_var = tk.StringVar(value="Choose a directory and click Scan.")
        self._summary_var = tk.StringVar(value="")
        self._show_node = tk.BooleanVar(value=True)
        self._show_venv = tk.BooleanVar(value=True)
        self._ui_font, self._mono_font = preferred_ui_fonts()

        self._build_ui()
        self._apply_styles()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=Palette.toolbar_bg, pady=10)
        header.pack(fill="x")

        tk.Label(
            header,
            text=APP_TITLE,
            font=(self._ui_font, 20, "bold"),
            bg=Palette.toolbar_bg,
            fg=Palette.accent,
        ).pack(side="left", padx=18)
        tk.Label(
            header,
            text=APP_SUBTITLE,
            font=(self._ui_font, 11),
            bg=Palette.toolbar_bg,
            fg=Palette.muted,
        ).pack(side="left", pady=6)

        toolbar = tk.Frame(self, bg=Palette.bg, pady=8)
        toolbar.pack(fill="x", padx=12)

        tk.Label(
            toolbar,
            text="Scan directory:",
            bg=Palette.bg,
            fg=Palette.fg,
            font=(self._ui_font, 10),
        ).pack(side="left")

        path_entry = tk.Entry(
            toolbar,
            textvariable=self._path_var,
            width=52,
            bg=Palette.row_even,
            fg=Palette.fg,
            insertbackground=Palette.fg,
            relief="flat",
            font=(self._mono_font, 10),
        )
        path_entry.pack(side="left", padx=(6, 4), ipady=4)

        self._btn_browse = self._make_button(toolbar, "Browse", self._browse, Palette.button_bg)
        self._btn_browse.pack(side="left", padx=3)

        self._btn_scan = self._make_button(
            toolbar,
            "Scan",
            self._start_scan,
            Palette.accent,
            fg=Palette.header_bg,
        )
        self._btn_scan.pack(side="left", padx=3)

        self._btn_stop = self._make_button(toolbar, "Stop", self._stop_scan, "#585b70")
        self._btn_stop.pack(side="left", padx=3)
        self._btn_stop.config(state="disabled")

        separator = tk.Frame(toolbar, bg="#45475a", width=1)
        separator.pack(side="left", fill="y", padx=10, pady=2)

        tk.Checkbutton(
            toolbar,
            text=NODE_MODULES_NAME,
            variable=self._show_node,
            command=self._apply_filter,
            bg=Palette.bg,
            fg=Palette.accent,
            selectcolor=Palette.row_even,
            activebackground=Palette.bg,
            font=(self._ui_font, 9),
        ).pack(side="left", padx=4)
        tk.Checkbutton(
            toolbar,
            text="venv/.venv",
            variable=self._show_venv,
            command=self._apply_filter,
            bg=Palette.bg,
            fg=Palette.success,
            selectcolor=Palette.row_even,
            activebackground=Palette.bg,
            font=(self._ui_font, 9),
        ).pack(side="left", padx=4)

        self._progress = ttk.Progressbar(self, mode="indeterminate", style="Scan.Horizontal.TProgressbar")
        self._progress.pack(fill="x", padx=12, pady=(0, 2))

        tk.Label(
            self,
            textvariable=self._status_var,
            anchor="w",
            bg=Palette.bg,
            fg=Palette.muted,
            font=(self._ui_font, 9),
        ).pack(fill="x", padx=14)

        tree_frame = tk.Frame(self, bg=Palette.bg)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=6)

        columns = (self.COL_CHECK, self.COL_TYPE, self.COL_SIZE, self.COL_PATH)
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Dev.Treeview",
            selectmode="browse",
        )

        self._tree.heading(self.COL_CHECK, text="All", command=self._toggle_all)
        self._tree.heading(self.COL_TYPE, text="Type")
        self._tree.heading(self.COL_SIZE, text="Size", command=lambda: self._sort("size"))
        self._tree.heading(self.COL_PATH, text="Path", command=lambda: self._sort("path"))

        self._tree.column(self.COL_CHECK, width=70, stretch=False, anchor="center")
        self._tree.column(self.COL_TYPE, width=130, stretch=False, anchor="center")
        self._tree.column(self.COL_SIZE, width=110, stretch=False, anchor="e")
        self._tree.column(self.COL_PATH, width=800, stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree.bind("<Button-1>", self._on_tree_click)

        bottom = tk.Frame(self, bg=Palette.toolbar_bg, pady=8)
        bottom.pack(fill="x")

        self._sel_all_btn = self._make_button(bottom, "Select All", self._select_all, Palette.button_bg)
        self._sel_all_btn.pack(side="left", padx=(14, 4))

        self._desel_btn = self._make_button(bottom, "Deselect All", self._deselect_all, Palette.button_bg)
        self._desel_btn.pack(side="left", padx=4)

        tk.Label(
            bottom,
            textvariable=self._summary_var,
            bg=Palette.toolbar_bg,
            fg=Palette.warning,
            font=(self._ui_font, 10, "bold"),
        ).pack(side="left", padx=18)

        self._del_btn = self._make_button(
            bottom,
            "Delete Selected",
            self._delete_selected,
            Palette.danger,
            fg=Palette.header_bg,
            font=(self._ui_font, 10, "bold"),
        )
        self._del_btn.pack(side="right", padx=14)
        self._del_btn.config(state="disabled")

    def _apply_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Dev.Treeview",
            background=Palette.row_even,
            foreground=Palette.fg,
            fieldbackground=Palette.row_even,
            rowheight=26,
            font=(self._mono_font, 9),
        )
        style.configure(
            "Dev.Treeview.Heading",
            background=Palette.header_bg,
            foreground=Palette.accent,
            font=(self._ui_font, 9, "bold"),
            relief="flat",
        )
        style.map(
            "Dev.Treeview",
            background=[("selected", Palette.select_bg)],
            foreground=[("selected", Palette.fg)],
        )
        style.configure(
            "Scan.Horizontal.TProgressbar",
            troughcolor=Palette.bg,
            background=Palette.accent,
            thickness=4,
        )

        self._tree.tag_configure("node", background="#1a2744", foreground=Palette.accent)
        self._tree.tag_configure("venv", background="#1a2d1a", foreground=Palette.success)
        self._tree.tag_configure("checked_node", background="#243a5e", foreground=Palette.fg)
        self._tree.tag_configure("checked_venv", background="#254225", foreground=Palette.fg)

    def _make_button(self, parent: tk.Misc, text: str, command, bg: str, fg: str | None = None, font=None) -> tk.Button:
        fg = fg or Palette.fg
        font = font or (self._ui_font, 9)
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            font=font,
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
            activebackground=bg,
            activeforeground=fg,
        )
        button.bind("<Enter>", lambda _event: button.config(bg=self._lighten(bg)))
        button.bind("<Leave>", lambda _event: button.config(bg=bg))
        return button

    @staticmethod
    def _lighten(hex_color: str) -> str:
        try:
            red = min(255, int(hex_color[1:3], 16) + 25)
            green = min(255, int(hex_color[3:5], 16) + 25)
            blue = min(255, int(hex_color[5:7], 16) + 25)
            return f"#{red:02x}{green:02x}{blue:02x}"
        except Exception:
            return hex_color

    def _browse(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._path_var.get())
        if directory:
            self._path_var.set(directory)

    def _start_scan(self) -> None:
        root = Path(self._path_var.get().strip()).expanduser()
        if not root.is_dir():
            messagebox.showerror("Invalid path", f"Not a directory:\n{root}")
            return
        if self._scanning:
            return

        self._clear_results()
        self._stop_event.clear()
        self._scanning = True
        self._btn_scan.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._progress.start(12)
        self._status_var.set(f"Scanning {root} ...")

        threading.Thread(target=self._scan_thread, args=(root,), daemon=True).start()

    def _clear_results(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._items.clear()
        self._row_tags.clear()
        self._checked.clear()
        self._update_summary()

    def _scan_thread(self, root: Path) -> None:
        count = 0

        def on_found(target: ScanTarget) -> None:
            nonlocal count
            count += 1
            if self.winfo_exists():
                self.after(0, self._add_row, target)
                self.after(0, self._status_var.set, f"Found {count} folder(s) ...")

        for target in iter_scan_targets(root, self._stop_event):
            if self._stop_event.is_set():
                break
            on_found(target)

        if self.winfo_exists():
            self.after(0, self._scan_done, count)

    def _scan_done(self, count: int) -> None:
        self._scanning = False
        self._progress.stop()
        self._btn_scan.config(state="normal")
        self._btn_stop.config(state="disabled")
        status = "Scan stopped." if self._stop_event.is_set() else "Scan complete."
        self._status_var.set(f"{status} Found {count} folder(s).")
        self._update_summary()

    def _stop_scan(self) -> None:
        self._stop_event.set()

    def _add_row(self, target: ScanTarget) -> None:
        tag = "node" if target.kind == NODE_MODULES_NAME else "venv"
        label = NODE_MODULES_NAME if target.kind == NODE_MODULES_NAME else "virtualenv"
        iid = self._tree.insert(
            "",
            "end",
            values=(UNCHECKED_MARK, label, human_size(target.size), str(target.path)),
            tags=(tag,),
        )
        self._items[iid] = target
        self._row_tags[iid] = tag
        self._apply_filter_to_item(iid)

    def _apply_filter_to_item(self, iid: str) -> None:
        target = self._items[iid]
        show_item = (target.kind == NODE_MODULES_NAME and self._show_node.get()) or (
            target.kind == VENV_KIND and self._show_venv.get()
        )
        if show_item:
            if iid not in self._tree.get_children():
                self._tree.reattach(iid, "", "end")
        else:
            if iid in self._checked:
                self._toggle_row(iid)
            if iid in self._tree.get_children():
                self._tree.detach(iid)

    def _on_tree_click(self, event) -> None:
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        if self._tree.identify_column(event.x) != "#1":
            return
        iid = self._tree.identify_row(event.y)
        if iid:
            self._toggle_row(iid)

    def _toggle_row(self, iid: str) -> None:
        if iid not in self._items:
            return

        values = list(self._tree.item(iid, "values"))
        if iid in self._checked:
            self._checked.remove(iid)
            values[0] = UNCHECKED_MARK
            new_tag = self._row_tags[iid]
        else:
            self._checked.add(iid)
            values[0] = CHECKED_MARK
            new_tag = "checked_node" if self._row_tags[iid] == "node" else "checked_venv"

        self._tree.item(iid, values=values, tags=(new_tag,))
        self._update_summary()

    def _toggle_all(self) -> None:
        visible_ids = self._tree.get_children()
        if not visible_ids:
            return
        if all(iid in self._checked for iid in visible_ids):
            self._deselect_all()
        else:
            self._select_all()

    def _select_all(self) -> None:
        for iid in self._tree.get_children():
            if iid not in self._checked:
                self._toggle_row(iid)

    def _deselect_all(self) -> None:
        for iid in list(self._checked):
            if iid in self._items:
                self._toggle_row(iid)

    def _apply_filter(self) -> None:
        for iid in list(self._items):
            self._apply_filter_to_item(iid)
        self._update_summary()

    def _sort(self, key: str) -> None:
        if self._sort_state["key"] == key:
            descending = not self._sort_state["descending"]
        else:
            descending = key == "size"
        self._sort_state = {"key": key, "descending": descending}

        sortable = []
        for iid in self._tree.get_children():
            target = self._items[iid]
            value = target.size if key == "size" else str(target.path).casefold()
            sortable.append((value, iid))

        sortable.sort(reverse=descending)
        for index, (_, iid) in enumerate(sortable):
            self._tree.move(iid, "", index)

    def _update_summary(self) -> None:
        if not self._checked:
            self._summary_var.set("")
            self._del_btn.config(state="disabled")
            return

        total_size = sum(self._items[iid].size for iid in self._checked if iid in self._items)
        count = len([iid for iid in self._checked if iid in self._items])
        self._summary_var.set(f"{count} selected | {human_size(total_size)} will be freed")
        self._del_btn.config(state="normal")

    def _delete_selected(self) -> None:
        selected_ids = [iid for iid in self._checked if iid in self._items]
        if not selected_ids:
            return

        total_size = sum(self._items[iid].size for iid in selected_ids)
        count = len(selected_ids)
        confirmed = messagebox.askyesno(
            "Confirm deletion",
            (
                f"You are about to permanently delete {count} folder(s) "
                f"({human_size(total_size)}).\n\n"
                f"{NODE_MODULES_NAME}: restore with npm install / pnpm install / yarn install\n"
                "venv/.venv: recreate and reinstall requirements as needed\n\n"
                "This cannot be undone. Proceed?"
            ),
            icon="warning",
        )
        if not confirmed:
            return

        deleted = 0
        freed_bytes = 0
        failures: list[str] = []

        for iid in selected_ids:
            target = self._items[iid]
            try:
                delete_tree(target.path)
            except Exception as exc:
                failures.append(f"{target.path}\n  - {exc}")
                continue

            freed_bytes += target.size
            deleted += 1
            self._tree.delete(iid)
            del self._items[iid]
            del self._row_tags[iid]
            self._checked.discard(iid)

        message = f"Deleted {deleted} folder(s). Reclaimed {human_size(freed_bytes)}."
        if failures:
            message += f"\n\n{len(failures)} deletion(s) failed:\n" + "\n".join(failures)
            messagebox.showwarning("Partial success", message)
        else:
            messagebox.showinfo("Done", message)

        self._update_summary()
        remaining_bytes = sum(target.size for target in self._items.values())
        self._status_var.set(
            f"Deleted {deleted} folder(s). {len(self._items)} remaining ({human_size(remaining_bytes)})."
        )

    def _on_close(self) -> None:
        self._stop_event.set()
        self.destroy()
