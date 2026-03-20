from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import format_targets_table, write_json_report, write_text_report
from .cleanup import delete_tree
from .models import NODE_MODULES_NAME, VENV_KIND, ScanTarget
from .scanner import human_size, iter_scan_targets
from .settings import AppSettings, save_settings


APP_TITLE = "DevBroom"
APP_SUBTITLE = "Clean dependency folders without touching project code."
WINDOW_SIZE = "1160x760"
WINDOW_MIN_SIZE = (900, 620)
CHECKED_MARK = "☑"
UNCHECKED_MARK = "☐"


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    surface_alt: str
    surface_muted: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_soft: str
    success: str
    danger: str
    danger_text: str
    progress_trough: str
    node_bg: str
    node_fg: str
    venv_bg: str
    venv_fg: str
    checked_node_bg: str
    checked_venv_bg: str
    selection_bg: str
    button_bg: str
    button_text: str
    field_bg: str


LIGHT_THEME = Theme(
    name="light",
    bg="#f3f4f6",
    surface="#ffffff",
    surface_alt="#f8fafc",
    surface_muted="#eef2f7",
    border="#d8e0ea",
    text="#18212b",
    text_muted="#64748b",
    accent="#0f766e",
    accent_soft="#d9f3ef",
    success="#1d7a46",
    danger="#b9384d",
    danger_text="#ffffff",
    progress_trough="#e5e7eb",
    node_bg="#e6f4f1",
    node_fg="#0f766e",
    venv_bg="#edf6e8",
    venv_fg="#2f6e3f",
    checked_node_bg="#cbe9e3",
    checked_venv_bg="#d8ebd2",
    selection_bg="#dbeafe",
    button_bg="#ecf2f8",
    button_text="#213547",
    field_bg="#f8fafc",
)


DARK_THEME = Theme(
    name="dark",
    bg="#0f1720",
    surface="#15202b",
    surface_alt="#1b2836",
    surface_muted="#223244",
    border="#2a3b4d",
    text="#e8eef5",
    text_muted="#9ab0c3",
    accent="#59c4b8",
    accent_soft="#173a40",
    success="#8dd39e",
    danger="#e35d75",
    danger_text="#fff7f8",
    progress_trough="#203041",
    node_bg="#163740",
    node_fg="#7adbd0",
    venv_bg="#1d3723",
    venv_fg="#9dddac",
    checked_node_bg="#20505c",
    checked_venv_bg="#285032",
    selection_bg="#29435c",
    button_bg="#243445",
    button_text="#e8eef5",
    field_bg="#101923",
)


def preferred_ui_fonts() -> tuple[str, str]:
    if os.name == "nt":
        return "Segoe UI", "Consolas"
    return "TkDefaultFont", "TkFixedFont"


class DevBroomApp(tk.Tk):
    COL_CHECK = "Pick"
    COL_TYPE = "Type"
    COL_SIZE = "Size"
    COL_PATH = "Path"

    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN_SIZE)
        settings = settings or AppSettings()

        self._items: dict[str, ScanTarget] = {}
        self._row_tags: dict[str, str] = {}
        self._checked: set[str] = set()
        self._stop_event = threading.Event()
        self._scanning = False
        self._sort_state = {"key": "size", "descending": True}
        self._ignored_paths = list(dict.fromkeys(settings.ignored_paths))

        default_path = settings.last_path.strip() or str(Path.home())
        theme_name = settings.theme if settings.theme in {"light", "dark"} else "dark"

        self._path_var = tk.StringVar(value=default_path)
        self._status_var = tk.StringVar(value="Choose a directory and start a scan.")
        self._summary_var = tk.StringVar(value="No folders selected")
        self._found_var = tk.StringVar(value="0 folders found")
        self._visible_total_var = tk.StringVar(value="0 B visible")
        self._ignored_var = tk.StringVar(value=self._ignored_summary_text())
        self._show_node = tk.BooleanVar(value=True)
        self._show_venv = tk.BooleanVar(value=True)
        self._theme_name = tk.StringVar(value=theme_name)
        self._ui_font, self._mono_font = preferred_ui_fonts()
        self._theme = LIGHT_THEME if theme_name == "light" else DARK_THEME

        self._build_ui()
        self._apply_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.configure(bg=self._theme.bg)

        self._header = tk.Frame(self, padx=24, pady=20)
        self._header.pack(fill="x")

        self._title_block = tk.Frame(self._header)
        self._title_block.pack(side="left", fill="x", expand=True)

        self._title_label = tk.Label(
            self._title_block,
            text=APP_TITLE,
            font=(self._ui_font, 22, "bold"),
            anchor="w",
        )
        self._title_label.pack(anchor="w")

        self._subtitle_label = tk.Label(
            self._title_block,
            text=APP_SUBTITLE,
            font=(self._ui_font, 10),
            anchor="w",
        )
        self._subtitle_label.pack(anchor="w", pady=(4, 0))

        self._theme_btn = tk.Button(
            self._header,
            text="Light Mode",
            command=self._toggle_theme,
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            font=(self._ui_font, 9, "bold"),
        )
        self._theme_btn.pack(side="right")

        self._summary_card = tk.Frame(self, padx=24, pady=18, highlightthickness=1)
        self._summary_card.pack(fill="x", padx=24)

        self._summary_top = tk.Frame(self._summary_card)
        self._summary_top.pack(fill="x")

        self._summary_label = tk.Label(
            self._summary_top,
            textvariable=self._summary_var,
            font=(self._ui_font, 13, "bold"),
            anchor="w",
        )
        self._summary_label.pack(side="left")

        self._found_label = tk.Label(
            self._summary_top,
            textvariable=self._found_var,
            font=(self._ui_font, 10),
            anchor="e",
        )
        self._found_label.pack(side="right")

        self._visible_total_label = tk.Label(
            self._summary_top,
            textvariable=self._visible_total_var,
            font=(self._ui_font, 10),
            anchor="e",
        )
        self._visible_total_label.pack(side="right", padx=(0, 18))

        self._status_label = tk.Label(
            self._summary_card,
            textvariable=self._status_var,
            font=(self._ui_font, 10),
            anchor="w",
            pady=6,
        )
        self._status_label.pack(fill="x", pady=(6, 0))

        self._progress = ttk.Progressbar(self, mode="indeterminate", style="Scan.Horizontal.TProgressbar")
        self._progress.pack(fill="x", padx=24, pady=(14, 0))

        self._controls_card = tk.Frame(self, padx=18, pady=16, highlightthickness=1)
        self._controls_card.pack(fill="x", padx=24, pady=(18, 14))

        self._controls_top = tk.Frame(self._controls_card)
        self._controls_top.pack(fill="x")

        self._scan_label = tk.Label(
            self._controls_top,
            text="Root directory",
            font=(self._ui_font, 9, "bold"),
        )
        self._scan_label.pack(side="left")

        self._ignored_label = tk.Label(
            self._controls_top,
            textvariable=self._ignored_var,
            font=(self._ui_font, 9),
        )
        self._ignored_label.pack(side="left", padx=(16, 0))

        self._filters_wrap = tk.Frame(self._controls_top)
        self._filters_wrap.pack(side="right")

        self._node_filter = tk.Checkbutton(
            self._filters_wrap,
            text=NODE_MODULES_NAME,
            variable=self._show_node,
            command=self._apply_filter,
            font=(self._ui_font, 9),
            padx=8,
        )
        self._node_filter.pack(side="left", padx=(0, 6))

        self._venv_filter = tk.Checkbutton(
            self._filters_wrap,
            text="virtualenvs",
            variable=self._show_venv,
            command=self._apply_filter,
            font=(self._ui_font, 9),
            padx=8,
        )
        self._venv_filter.pack(side="left")

        self._controls_row = tk.Frame(self._controls_card)
        self._controls_row.pack(fill="x", pady=(12, 0))

        self._path_entry = tk.Entry(
            self._controls_row,
            textvariable=self._path_var,
            relief="flat",
            font=(self._mono_font, 10),
            insertwidth=1,
        )
        self._path_entry.pack(side="left", fill="x", expand=True, ipady=9)

        self._btn_browse = self._make_button(self._controls_row, "Browse", self._browse)
        self._btn_browse.pack(side="left", padx=(10, 8))

        self._btn_scan = self._make_button(self._controls_row, "Scan", self._start_scan, accent=True)
        self._btn_scan.pack(side="left", padx=(0, 8))

        self._btn_stop = self._make_button(self._controls_row, "Stop", self._stop_scan)
        self._btn_stop.pack(side="left")
        self._btn_stop.config(state="disabled")

        self._btn_ignore = self._make_button(self._controls_row, "Ignore Folder", self._add_ignored_path)
        self._btn_ignore.pack(side="left", padx=(10, 8))

        self._btn_clear_ignores = self._make_button(self._controls_row, "Clear Ignores", self._clear_ignored_paths)
        self._btn_clear_ignores.pack(side="left")

        self._results_card = tk.Frame(self, padx=0, pady=0, highlightthickness=1)
        self._results_card.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        self._results_top = tk.Frame(self._results_card, padx=18, pady=16)
        self._results_top.pack(fill="x")

        self._results_title = tk.Label(
            self._results_top,
            text="Cleanup Candidates",
            font=(self._ui_font, 11, "bold"),
        )
        self._results_title.pack(side="left")

        self._actions_wrap = tk.Frame(self._results_top)
        self._actions_wrap.pack(side="right")

        self._sel_all_btn = self._make_button(self._actions_wrap, "Select All", self._select_all)
        self._sel_all_btn.pack(side="left", padx=(0, 8))

        self._desel_btn = self._make_button(self._actions_wrap, "Clear", self._deselect_all)
        self._desel_btn.pack(side="left", padx=(0, 8))

        self._del_btn = self._make_button(
            self._actions_wrap,
            "Delete Selected",
            self._delete_selected,
            danger=True,
        )
        self._del_btn.pack(side="left")
        self._del_btn.config(state="disabled")

        self._preview_btn = self._make_button(self._actions_wrap, "Preview", self._preview_results)
        self._preview_btn.pack(side="left", padx=(8, 0))

        self._export_btn = self._make_button(self._actions_wrap, "Export", self._export_results)
        self._export_btn.pack(side="left", padx=(8, 0))

        self._table_frame = tk.Frame(self._results_card, padx=18, pady=0)
        self._table_frame.pack(fill="both", expand=True, pady=(0, 18))

        columns = (self.COL_CHECK, self.COL_TYPE, self.COL_SIZE, self.COL_PATH)
        self._tree = ttk.Treeview(
            self._table_frame,
            columns=columns,
            show="headings",
            style="Dev.Treeview",
            selectmode="browse",
        )

        self._tree.heading(self.COL_CHECK, text="All", command=self._toggle_all)
        self._tree.heading(self.COL_TYPE, text="Type")
        self._tree.heading(self.COL_SIZE, text="Size", command=lambda: self._sort("size"))
        self._tree.heading(self.COL_PATH, text="Path", command=lambda: self._sort("path"))

        self._tree.column(self.COL_CHECK, width=82, stretch=False, anchor="center")
        self._tree.column(self.COL_TYPE, width=140, stretch=False, anchor="center")
        self._tree.column(self.COL_SIZE, width=110, stretch=False, anchor="e")
        self._tree.column(self.COL_PATH, width=820, stretch=True)

        vsb = ttk.Scrollbar(self._table_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self._table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self._table_frame.rowconfigure(0, weight=1)
        self._table_frame.columnconfigure(0, weight=1)

        self._tree.bind("<Button-1>", self._on_tree_click)

    def _make_button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        accent: bool = False,
        danger: bool = False,
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            font=(self._ui_font, 9, "bold"),
        )
        button._is_accent = accent
        button._is_danger = danger
        button.bind("<Enter>", lambda _event, btn=button: self._refresh_button(btn, hovered=True))
        button.bind("<Leave>", lambda _event, btn=button: self._refresh_button(btn, hovered=False))
        return button

    def _toggle_theme(self) -> None:
        self._theme_name.set("light" if self._theme.name == "dark" else "dark")
        self._theme = LIGHT_THEME if self._theme_name.get() == "light" else DARK_THEME
        self._apply_theme()
        self._save_preferences()

    def _apply_theme(self) -> None:
        theme = self._theme
        self.configure(bg=theme.bg)
        self._theme_btn.config(text="Dark Mode" if theme.name == "light" else "Light Mode")

        for frame in (
            self._header,
            self._title_block,
            self._summary_card,
            self._summary_top,
            self._controls_card,
            self._controls_top,
            self._controls_row,
            self._filters_wrap,
            self._results_card,
            self._results_top,
            self._actions_wrap,
            self._table_frame,
        ):
            frame.config(bg=theme.surface)

        self._header.config(bg=theme.bg)
        self._title_block.config(bg=theme.bg)
        self._summary_card.config(bg=theme.surface, highlightbackground=theme.border, highlightcolor=theme.border)
        self._controls_card.config(bg=theme.surface, highlightbackground=theme.border, highlightcolor=theme.border)
        self._results_card.config(bg=theme.surface, highlightbackground=theme.border, highlightcolor=theme.border)
        self._table_frame.config(bg=theme.surface)

        self._title_label.config(bg=theme.bg, fg=theme.text)
        self._subtitle_label.config(bg=theme.bg, fg=theme.text_muted)
        self._summary_label.config(bg=theme.surface, fg=theme.text)
        self._found_label.config(bg=theme.surface, fg=theme.text_muted)
        self._visible_total_label.config(bg=theme.surface, fg=theme.text_muted)
        self._status_label.config(bg=theme.surface, fg=theme.text_muted)
        self._scan_label.config(bg=theme.surface, fg=theme.text_muted)
        self._ignored_label.config(bg=theme.surface, fg=theme.text_muted)
        self._results_title.config(bg=theme.surface, fg=theme.text)

        self._path_entry.config(
            bg=theme.field_bg,
            fg=theme.text,
            insertbackground=theme.text,
            disabledbackground=theme.field_bg,
            disabledforeground=theme.text_muted,
        )

        self._node_filter.config(
            bg=theme.surface,
            fg=theme.text,
            activebackground=theme.surface,
            activeforeground=theme.text,
            selectcolor=theme.surface_alt,
        )
        self._venv_filter.config(
            bg=theme.surface,
            fg=theme.text,
            activebackground=theme.surface,
            activeforeground=theme.text,
            selectcolor=theme.surface_alt,
        )

        self._refresh_all_buttons()
        self._apply_styles()

    def _refresh_all_buttons(self) -> None:
        for button in (
            self._theme_btn,
            self._btn_browse,
            self._btn_scan,
            self._btn_stop,
            self._btn_ignore,
            self._btn_clear_ignores,
            self._sel_all_btn,
            self._desel_btn,
            self._del_btn,
            self._preview_btn,
            self._export_btn,
        ):
            self._refresh_button(button, hovered=False)

    def _refresh_button(self, button: tk.Button, *, hovered: bool) -> None:
        theme = self._theme
        is_disabled = str(button.cget("state")) == "disabled"

        if is_disabled:
            bg = theme.surface_muted
            fg = theme.text_muted
        elif getattr(button, "_is_accent", False):
            bg = theme.accent
            fg = "#08201d" if theme.name == "light" else "#062826"
        elif getattr(button, "_is_danger", False):
            bg = theme.danger
            fg = theme.danger_text
        else:
            bg = theme.button_bg
            fg = theme.button_text

        if hovered and not is_disabled:
            bg = self._shift_color(bg, 0.08 if theme.name == "light" else 0.12)

        button.config(
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            disabledforeground=fg,
            highlightthickness=0,
        )

    @staticmethod
    def _shift_color(hex_color: str, amount: float) -> str:
        try:
            red = int(hex_color[1:3], 16)
            green = int(hex_color[3:5], 16)
            blue = int(hex_color[5:7], 16)
            red = min(255, int(red + (255 - red) * amount))
            green = min(255, int(green + (255 - green) * amount))
            blue = min(255, int(blue + (255 - blue) * amount))
            return f"#{red:02x}{green:02x}{blue:02x}"
        except Exception:
            return hex_color

    def _apply_styles(self) -> None:
        theme = self._theme
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dev.Treeview",
            background=theme.surface_alt,
            foreground=theme.text,
            fieldbackground=theme.surface_alt,
            borderwidth=0,
            rowheight=30,
            font=(self._mono_font, 9),
        )
        style.configure(
            "Dev.Treeview.Heading",
            background=theme.surface,
            foreground=theme.text_muted,
            font=(self._ui_font, 9, "bold"),
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Dev.Treeview",
            background=[("selected", theme.selection_bg)],
            foreground=[("selected", theme.text)],
        )
        style.configure(
            "TScrollbar",
            troughcolor=theme.surface,
            background=theme.surface_muted,
            bordercolor=theme.surface,
            arrowcolor=theme.text_muted,
        )
        style.configure(
            "Scan.Horizontal.TProgressbar",
            troughcolor=theme.progress_trough,
            background=theme.accent,
            borderwidth=0,
            thickness=6,
        )

        self._tree.tag_configure("node", background=theme.node_bg, foreground=theme.node_fg)
        self._tree.tag_configure("venv", background=theme.venv_bg, foreground=theme.venv_fg)
        self._tree.tag_configure("checked_node", background=theme.checked_node_bg, foreground=theme.text)
        self._tree.tag_configure("checked_venv", background=theme.checked_venv_bg, foreground=theme.text)

    def _browse(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._path_var.get())
        if directory:
            self._path_var.set(directory)
            self._save_preferences()

    def _start_scan(self) -> None:
        root = Path(self._path_var.get().strip()).expanduser()
        if not root.is_dir():
            messagebox.showerror("Invalid path", f"Not a directory:\n{root}")
            return
        if self._scanning:
            return

        self._save_preferences()

        self._clear_results()
        self._stop_event.clear()
        self._scanning = True
        self._btn_scan.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._refresh_all_buttons()
        self._progress.start(12)
        self._status_var.set(f"Scanning {root} ...")

        threading.Thread(target=self._scan_thread, args=(root,), daemon=True).start()

    def _clear_results(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._items.clear()
        self._row_tags.clear()
        self._checked.clear()
        self._found_var.set("0 folders found")
        self._visible_total_var.set("0 B visible")
        self._update_summary()

    def _scan_thread(self, root: Path) -> None:
        count = 0

        def on_found(target: ScanTarget) -> None:
            nonlocal count
            count += 1
            if self.winfo_exists():
                self.after(0, self._add_row, target)
                self.after(0, self._status_var.set, f"Found {count} folder(s) so far ...")
                self.after(0, self._found_var.set, f"{count} folders found")

        for target in iter_scan_targets(root, self._stop_event, ignored_paths=self._ignored_paths):
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
        self._refresh_all_buttons()
        self._found_var.set(f"{count} folders found")
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
        self._update_visible_total()

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
        self._update_visible_total()

        if not self._checked:
            self._summary_var.set("No folders selected")
            self._del_btn.config(state="disabled")
            self._refresh_all_buttons()
            return

        total_size = sum(self._items[iid].size for iid in self._checked if iid in self._items)
        count = len([iid for iid in self._checked if iid in self._items])
        self._summary_var.set(f"{count} selected | {human_size(total_size)} can be reclaimed")
        self._del_btn.config(state="normal")
        self._refresh_all_buttons()

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

        self._found_var.set(f"{len(self._items)} folders found")
        self._update_summary()
        remaining_bytes = sum(target.size for target in self._items.values())
        self._status_var.set(
            f"Deleted {deleted} folder(s). {len(self._items)} remaining ({human_size(remaining_bytes)})."
        )

    def _on_close(self) -> None:
        self._stop_event.set()
        self._save_preferences()
        self.destroy()

    def _save_preferences(self) -> None:
        settings = AppSettings(
            last_path=self._path_var.get().strip(),
            theme=self._theme.name,
            ignored_paths=tuple(self._ignored_paths),
        )
        try:
            save_settings(settings)
        except OSError:
            pass

    def _update_visible_total(self) -> None:
        visible_ids = self._tree.get_children()
        visible_total = sum(self._items[iid].size for iid in visible_ids if iid in self._items)
        self._visible_total_var.set(f"{human_size(visible_total)} visible")

    def _visible_targets(self) -> list[ScanTarget]:
        return [self._items[iid] for iid in self._tree.get_children() if iid in self._items]

    def _preview_results(self) -> None:
        targets = self._visible_targets()
        preview_text = format_targets_table(targets)

        preview = tk.Toplevel(self)
        preview.title("Scan Preview")
        preview.geometry("900x520")
        preview.configure(bg=self._theme.surface)

        frame = tk.Frame(preview, bg=self._theme.surface, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        text = tk.Text(
            frame,
            wrap="none",
            relief="flat",
            bg=self._theme.field_bg,
            fg=self._theme.text,
            insertbackground=self._theme.text,
            font=(self._mono_font, 10),
        )
        text.insert("1.0", preview_text)
        text.config(state="disabled")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _export_results(self) -> None:
        targets = self._visible_targets()
        if not targets:
            messagebox.showinfo("Nothing to export", "There are no visible scan results to export.")
            return

        output = filedialog.asksaveasfilename(
            title="Export scan results",
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
            ],
        )
        if not output:
            return

        output_path = Path(output)
        try:
            if output_path.suffix.lower() == ".txt":
                write_text_report(targets, output_path)
            else:
                write_json_report(targets, output_path)
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not export results:\n{exc}")
            return

        self._status_var.set(f"Exported {len(targets)} result(s) to {output_path}")

    def _ignored_summary_text(self) -> str:
        count = len(self._ignored_paths)
        return f"{count} ignored folder{'s' if count != 1 else ''}"

    def _add_ignored_path(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._path_var.get())
        if not directory:
            return

        normalized = str(Path(directory).expanduser().resolve(strict=False))
        if normalized not in self._ignored_paths:
            self._ignored_paths.append(normalized)
            self._ignored_var.set(self._ignored_summary_text())
            self._save_preferences()
            self._status_var.set(f"Added ignore path: {normalized}")

    def _clear_ignored_paths(self) -> None:
        if not self._ignored_paths:
            return
        confirmed = messagebox.askyesno(
            "Clear ignores",
            "Remove all ignored paths from settings?",
            icon="question",
        )
        if not confirmed:
            return

        self._ignored_paths.clear()
        self._ignored_var.set(self._ignored_summary_text())
        self._save_preferences()
        self._status_var.set("Cleared ignored paths.")
