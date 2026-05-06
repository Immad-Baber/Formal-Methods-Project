"""
ui_app.py — Part 1: Feature Model UI + Visualization (Member 3)
================================================================
Modern desktop UI + built-in testing guide.

Run (from this folder):
    python -m pip install -r requirements.txt
    python ui_app.py

Optional:
    python ui_app.py path/to/model.xml
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Set, List, Tuple, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fm_core import load_feature_model
from sat_solver import SATValidator

try:
    import pysat  # noqa: F401
    _PYSAT_OK = True
except ImportError:
    _PYSAT_OK = False


# --- Theme (neutral / teal accent — reads well on projector & PDF screenshots)
COL_BG = "#e8ecf1"
COL_SURFACE = "#ffffff"
COL_SURFACE_ALT = "#f4f6f8"
COL_BORDER = "#d1d8e0"
COL_TEXT = "#0f172a"
COL_TEXT_DIM = "#64748b"
COL_ACCENT = "#0d9488"
COL_ACCENT_HOVER = "#0f766e"
COL_ACCENTBAR = "#134e4a"
COL_XOR = "#7c3aed"
COL_OR = "#0369a1"
COL_OK_BG = "#ecfdf5"
COL_OK_FG = "#047857"
COL_BAD_BG = "#fef2f2"
COL_BAD_FG = "#b91c1c"
COL_WARN_BG = "#fffbeb"
COL_WARN_FG = "#b45309"
FONT_FAMILY = "Segoe UI"
FONT_UI = (FONT_FAMILY, 10)
FONT_UI_MD = (FONT_FAMILY, 11)
FONT_UI_SM = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 18, "bold")
FONT_SUB = (FONT_FAMILY, 11)
FONT_CODE = ("Consolas", 10)
if sys.platform == "darwin":
    FONT_CODE = ("Menlo", 11)


class ScrollableFrame(ttk.Frame):
    """Vertical scroll; mouse wheel only while pointer is over the canvas."""

    def __init__(self, parent, bg_canvas: str, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=bg_canvas)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=COL_SURFACE)
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win, width=max(event.width - 4, 100))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class FeatureModelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Feature Model Analysis Tool")
        self.minsize(1120, 740)
        self.geometry("1240x820")
        self.configure(bg=COL_BG)

        self._parser = None
        self._translator = None
        self._validator: Optional[SATValidator] = None
        self._xml_path: Optional[str] = None
        self._vars: Dict[str, tk.BooleanVar] = {}
        self._suppress_trace = False
        self._after_id: Optional[str] = None
        self._tree_row_i = 0

        self._build_style()
        self._build_menu()
        self._build_layout()

        default_xml = os.path.join(os.path.dirname(__file__), "feature_model.xml")
        if os.path.isfile(default_xml):
            self.load_xml_file(default_xml)

    def _build_style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=COL_BG, foreground=COL_TEXT, font=FONT_UI)
        s.configure("TFrame", background=COL_BG)
        s.configure("Card.TFrame", background=COL_SURFACE)
        s.configure("TNotebook", background=COL_BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(14, 10), font=FONT_UI_MD)
        s.configure("TLabelframe", background=COL_SURFACE)
        s.configure("TLabelframe.Label", background=COL_SURFACE, foreground=COL_ACCENTBAR, font=(FONT_FAMILY, 10, "bold"))
        s.configure("Tool.TButton", padding=(12, 8), font=FONT_UI_MD)

    def _build_menu(self):
        m = tk.Menu(self)
        file_m = tk.Menu(m, tearoff=0)
        file_m.add_command(label="Open XML…", command=self._menu_open_xml)
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self.destroy)
        m.add_cascade(label="File", menu=file_m)
        view_m = tk.Menu(m, tearoff=0)
        view_m.add_command(label="Open tab: How to test", command=self._show_how_to_test_tab)
        m.add_cascade(label="View", menu=view_m)
        help_m = tk.Menu(m, tearoff=0)
        help_m.add_command(label="About", command=self._about)
        m.add_cascade(label="Help", menu=help_m)
        self.config(menu=m)

    def _menu_open_xml(self):
        path = filedialog.askopenfilename(
            title="Open feature model XML",
            filetypes=[("XML", "*.xml"), ("All files", "*.*")],
        )
        if path:
            self.load_xml_file(path)

    def _about(self):
        messagebox.showinfo(
            "About",
            "Feature Model Analysis Tool — Part 1\n\n"
            "XML & logic: fm_core\n"
            "SAT / MWP / verify: sat_solver (PySAT)\n\n"
            "Tip: open the “How to test” tab for a demo checklist.",
        )

    def _show_how_to_test_tab(self):
        """
        Switch to the testing guide tab. Uses tab index 0 because some Windows
        Tk builds ignore select(child_widget) from the menu bar.
        """
        nb = getattr(self, "nb", None)
        if nb is None:
            return
        try:
            # First tab is always "How to test"
            nb.select(0)
        except tk.TclError:
            try:
                nb.select(self.tab_how)
            except (tk.TclError, AttributeError):
                pass
        self.update_idletasks()

    def _accent_btn(self, parent, text, command):
        b = tk.Button(
            parent,
            text=text,
            command=command,
            font=FONT_UI_MD,
            fg="white",
            bg=COL_ACCENT,
            activebackground=COL_ACCENT_HOVER,
            activeforeground="white",
            relief=tk.FLAT,
            padx=18,
            pady=10,
            cursor="hand2",
        )
        return b

    def _ghost_btn(self, parent, text, command):
        b = tk.Button(
            parent,
            text=text,
            command=command,
            font=FONT_UI_MD,
            fg=COL_TEXT,
            bg=COL_SURFACE,
            activebackground=COL_SURFACE_ALT,
            relief=tk.FLAT,
            padx=14,
            pady=10,
            highlightthickness=1,
            highlightbackground=COL_BORDER,
            cursor="hand2",
        )
        return b

    def _text_set_readonly(self, w: tk.Text, content: str) -> None:
        """Replace all text and lock editing (output-only panes)."""
        w.configure(state=tk.NORMAL)
        w.delete("1.0", tk.END)
        if content:
            w.insert(tk.END, content)
        w.configure(state=tk.DISABLED, cursor="arrow")

    def _build_layout(self):
        outer = tk.Frame(self, bg=COL_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Top bar ---
        top = tk.Frame(outer, bg=COL_ACCENTBAR, padx=28, pady=18)
        top.pack(fill=tk.X)
        left_head = tk.Frame(top, bg=COL_ACCENTBAR)
        left_head.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(left_head, text="Feature Model Analysis", font=FONT_TITLE, fg="white", bg=COL_ACCENTBAR).pack(anchor=tk.W)
        tk.Label(
            left_head,
            text="Interactive configuration · SAT verification · MWP · Logic export",
            font=FONT_SUB,
            fg="#99f6e4",
            bg=COL_ACCENTBAR,
        ).pack(anchor=tk.W, pady=(4, 0))

        btns = tk.Frame(top, bg=COL_ACCENTBAR)
        btns.pack(side=tk.RIGHT)
        self._accent_btn(btns, "  Open XML…  ", self._menu_open_xml).pack(side=tk.LEFT, padx=(0, 8))
        self._ghost_btn(btns, " How to test ", self._show_how_to_test_tab).pack(side=tk.LEFT, padx=(0, 8))
        self._ghost_btn(btns, " Verify now ", lambda: self._verify_now(reveal_verification_tab=True)).pack(side=tk.LEFT, padx=(0, 8))
        self._ghost_btn(btns, " Check MWP ", self._apply_mwp).pack(side=tk.LEFT)

        # --- Warning / SAT banner ---
        self.banner = tk.Label(outer, text="", font=FONT_UI_MD, bg=COL_WARN_BG, fg=COL_WARN_FG, anchor=tk.W, padx=24, pady=10)
        self.banner.pack(fill=tk.X)
        self._set_pysat_banner()

        body = tk.Frame(outer, bg=COL_BG, padx=20, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        paned = ttk.Panedwindow(body, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left column — tree card
        left_wrap = tk.Frame(paned, bg=COL_BG)
        paned.add(left_wrap, weight=5)

        left_card = tk.Frame(left_wrap, bg=COL_SURFACE, highlightbackground=COL_BORDER, highlightthickness=1)
        left_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(left_card, text="Feature selection", font=(FONT_FAMILY, 12, "bold"), fg=COL_TEXT, bg=COL_SURFACE).pack(
            anchor=tk.W, padx=16, pady=(14, 4)
        )

        legend = tk.Frame(left_card, bg=COL_SURFACE)
        legend.pack(fill=tk.X, padx=16, pady=(0, 8))
        for txt, color in [
            ("Mandatory", COL_TEXT),
            ("Optional", COL_TEXT_DIM),
            ("XOR group", COL_XOR),
            ("OR group", COL_OR),
        ]:
            pill = tk.Label(legend, text=f" {txt} ", font=FONT_UI_SM, fg="white" if txt.startswith(("XOR", "OR")) else COL_TEXT,
                           bg=color if txt.startswith(("XOR", "OR")) else COL_SURFACE_ALT,
                           padx=8, pady=4)
            pill.pack(side=tk.LEFT, padx=(0, 8))

        self.tree_scroll = ScrollableFrame(left_card, bg_canvas=COL_SURFACE)
        self.tree_scroll.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        actions = tk.Frame(left_card, bg=COL_SURFACE)
        actions.pack(fill=tk.X, padx=16, pady=(0, 14))
        ttk.Button(actions, text="Select mandatory chain", command=self._select_mandatory_closure, style="Tool.TButton").pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(actions, text="Check MWP", command=self._apply_mwp, style="Tool.TButton").pack(side=tk.LEFT)

        tk.Label(
            left_card,
            text=(
                "MWP: the SAT layer finds one smallest valid configuration. "
                "“Check MWP ” does NOT change your selected checkboxes; it only compares and verifies. "
                "Use this to detect missing mandatory features without auto-selecting them."
            ),
            font=FONT_UI_SM,
            fg=COL_TEXT_DIM,
            bg=COL_SURFACE,
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=520,
        ).pack(fill=tk.X, padx=16, pady=(0, 12))

        # Right column — notebook
        right_wrap = tk.Frame(paned, bg=COL_BG)
        paned.add(right_wrap, weight=4)

        nb_holder = tk.Frame(right_wrap, bg=COL_SURFACE, highlightbackground=COL_BORDER, highlightthickness=1)
        nb_holder.pack(fill=tk.BOTH, expand=True)

        self.nb = ttk.Notebook(nb_holder)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tab_how = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_how, text="  How to test  ")

        self.tab_verify = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_verify, text="  Verification  ")

        self.tab_logic = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_logic, text="  Logic  ")

        self.tab_constraints = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_constraints, text="  Constraints  ")

        self.tab_mwp = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_mwp, text="  MWP  ")

        self.tab_diagram = tk.Frame(self.nb, bg=COL_SURFACE)
        self.nb.add(self.tab_diagram, text="  Diagram  ")

        self._build_tab_how()
        self._build_tab_verify()
        self._build_tab_logic()
        self._build_tab_constraints()
        self._build_tab_mwp()
        self._build_tab_diagram()

        self.nb.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        # Footer
        foot = tk.Frame(outer, bg=COL_SURFACE_ALT, highlightbackground=COL_BORDER, highlightthickness=1)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer_left = tk.Label(foot, text="No file loaded.", font=FONT_UI_SM, fg=COL_TEXT_DIM, bg=COL_SURFACE_ALT, anchor=tk.W, padx=16, pady=8)
        self.footer_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.footer_right = tk.Label(foot, text="", font=FONT_UI_SM, fg=COL_TEXT_DIM, bg=COL_SURFACE_ALT, anchor=tk.E, padx=16, pady=8)
        self.footer_right.pack(side=tk.RIGHT)

    HOW_TO_TEST_TEXT = """HOW TO RUN AND TEST THIS TOOL (for your demo & sanity check)
═══════════════════════════════════════════════════════════════

STEP 0 — START THE APP
  • Open Terminal / PowerShell or Cursor terminal.
  • Go to the project folder that contains ui_app.py (Formal-Methods-Project).
  • Run:
        python -m pip install -r requirements.txt
        python ui_app.py
  • A window must open. If nothing opens, copy any error text and fix Python PATH.

STEP 1 — PYSAT (SAT + MWP)
  • Look at the yellow banner under the green header.
  • If it says PySAT is missing, run:
        python -m pip install python-sat
    then restart ui_app.py.
  • With PySAT OK, “Verification” and “MWP” tabs work fully.

STEP 2 — LOAD XML
  • Click “Open XML…” (top right) or File → Open XML.
  • Pick feature_model.xml (or another model).
  • Left panel fills with checkboxes (tree).

STEP 3 — TREE BEHAVIOUR (assignment checklist)
  • Root feature stays ON (greyed checkbox). That is intentional.
  • Mandatory vs optional labels appear beside names.
  • Under XOR: selecting SMS clears Call (only one XOR choice).
  • Under OR under Payment: you may tick CreditCard or Discount (or both); if Payment is on,
    at least one OR member must be on or verification fails.

STEP 4 — VERIFY (SAT)
  • Tick / untick features.
  • Open “Verification” tab: after a short pause it updates automatically.
  • Press “Verify now” or top “Verify now” to force refresh.
  • Valid → green-style message. Invalid → red-style message + bullet reasons.

STEP 5 — TRY A BAD CASE (cross-tree / requires)
  • Under Filtered, pick ByLocation (XOR). Turn OFF Location (and its WiFi/GPS children if needed).
  • Verification must say NOT feasible (ByLocation requires Location per the XML constraint).
  • Check the “Logic” tab: you should see one R5/R6 line: ByLocation → Location (not Location → Catalog).

STEP 6 — MWP
  • Open “MWP” tab to read the computed feature list (or click “Refresh MWP list” there).
  • Click “Check MWP” (top bar or under the tree): current selection is verified, and MWP list is shown.
  • This action does NOT auto-select unchecked features.

STEP 7 — LOGIC & DIAGRAM (documentation marks)
  • “Logic” tab: full prop formulas + combined AND view (Person 1 output).
  • “Diagram” tab: readable hierarchy for screenshots / report.

WHAT YOU SAY IN THE DEMO VIDEO (30-second script)
  “We load XML, the tree shows mandatory vs optional and XOR/OR groups.
   Selections are checked live against PySAT. Invalid configs show reasons.
   MWP lists one minimal product configuration.”

═══════════════════════════════════════════════════════════════
"""

    def _build_tab_how(self):
        f = self.tab_how
        tk.Label(f, text="Follow these steps once — then relax.", font=(FONT_FAMILY, 12, "bold"), fg=COL_TEXT, bg=COL_SURFACE).pack(
            anchor=tk.W, padx=14, pady=(12, 6)
        )
        txt = tk.Text(f, wrap=tk.WORD, font=FONT_CODE if FONT_CODE[0] else FONT_UI, relief=tk.FLAT, bg=COL_SURFACE_ALT, fg=COL_TEXT, padx=12, pady=12)
        sy = ttk.Scrollbar(f, command=txt.yview)
        txt.configure(yscrollcommand=sy.set)
        txt.insert(tk.END, self.HOW_TO_TEST_TEXT)
        txt.configure(state=tk.DISABLED)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        sy.pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=(0, 8))

    def _set_pysat_banner(self):
        if _PYSAT_OK:
            self.banner.configure(text="  PySAT is installed — verification and MWP are active.", bg=COL_OK_BG, fg=COL_OK_FG)
        else:
            self.banner.configure(
                text="  Install PySAT for SAT marks:  python -m pip install python-sat   (then restart this app)",
                bg=COL_WARN_BG,
                fg=COL_WARN_FG,
            )

    def _update_footer(self):
        path = self._xml_path or "—"
        n = sum(1 for v in self._vars.values() if v.get()) if self._vars else 0
        total = len(self._vars)
        self.footer_left.configure(text=f"  Model: {os.path.basename(path) if path != '—' else path}")
        self.footer_right.configure(text=f"{n} / {total} features selected  ", fg=COL_TEXT_DIM)

    def _build_tab_verify(self):
        f = self.tab_verify
        self.card_verify = tk.Frame(f, bg=COL_SURFACE, padx=12, pady=12)
        self.card_verify.pack(fill=tk.BOTH, expand=True)

        self.lbl_feasible = tk.Label(
            self.card_verify,
            text="Load an XML model to begin.",
            font=(FONT_FAMILY, 12, "bold"),
            fg=COL_TEXT_DIM,
            bg=COL_SURFACE,
            anchor=tk.W,
        )
        self.lbl_feasible.pack(fill=tk.X, pady=(0, 10))

        tk.Label(self.card_verify, text="Summary (read-only)", font=(FONT_FAMILY, 10, "bold"), fg=COL_ACCENTBAR, bg=COL_SURFACE, anchor=tk.W).pack(fill=tk.X)
        self.txt_reason = tk.Text(self.card_verify, height=5, wrap=tk.WORD, font=FONT_UI_MD, relief=tk.FLAT, bg=COL_SURFACE_ALT, fg=COL_TEXT, padx=8, pady=8)
        self.txt_reason.pack(fill=tk.X, pady=(4, 12))

        tk.Label(self.card_verify, text="Violations & hints (read-only)", font=(FONT_FAMILY, 10, "bold"), fg=COL_ACCENTBAR, bg=COL_SURFACE, anchor=tk.W).pack(fill=tk.X)
        self.txt_violations = tk.Text(self.card_verify, height=14, wrap=tk.WORD, font=FONT_UI, relief=tk.FLAT, bg=COL_BAD_BG, fg=COL_TEXT, padx=8, pady=8)
        self.txt_violations.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._text_set_readonly(self.txt_reason, "Load XML to see verification results.")
        self._text_set_readonly(self.txt_violations, "")

    def _build_tab_logic(self):
        f = self.tab_logic
        tk.Label(f, text="Propositional logic (read-only)", font=(FONT_FAMILY, 10, "bold"), fg=COL_TEXT, bg=COL_SURFACE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4)
        )
        self.txt_logic = tk.Text(f, wrap=tk.NONE, font=FONT_CODE, relief=tk.FLAT, bg="#1e293b", fg="#e2e8f0", insertbackground="white", padx=8, pady=8)
        sy = ttk.Scrollbar(f, command=self.txt_logic.yview)
        sx = ttk.Scrollbar(f, orient=tk.HORIZONTAL, command=self.txt_logic.xview)
        self.txt_logic.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.txt_logic.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        sy.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        sx.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)
        self._text_set_readonly(self.txt_logic, "Load XML to see translated formulas.")

    def _build_tab_constraints(self):
        f = self.tab_constraints
        tk.Label(f, text="Cross-tree constraints (read-only)", font=(FONT_FAMILY, 10, "bold"), fg=COL_TEXT, bg=COL_SURFACE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4)
        )
        self.txt_constraints = tk.Text(f, wrap=tk.WORD, font=FONT_UI_MD, relief=tk.FLAT, bg=COL_SURFACE_ALT, fg=COL_TEXT, padx=10, pady=10)
        sy = ttk.Scrollbar(f, command=self.txt_constraints.yview)
        self.txt_constraints.configure(yscrollcommand=sy.set)
        self.txt_constraints.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        sy.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(0, 8))
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)
        self._text_set_readonly(self.txt_constraints, "Load XML to see constraints.")

    def _build_tab_mwp(self):
        f = self.tab_mwp
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        tk.Label(f, text="Minimum Working Product (read-only)", font=(FONT_FAMILY, 12, "bold"), fg=COL_TEXT, bg=COL_SURFACE).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        self.txt_mwp = tk.Text(f, wrap=tk.WORD, font=FONT_UI_MD, relief=tk.FLAT, bg=COL_OK_BG, fg=COL_TEXT, padx=10, pady=10)
        self.txt_mwp.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        ttk.Button(
            f,
            text="Refresh MWP list",
            command=lambda: self._refresh_mwp_text(reveal_mwp_tab=True),
            style="Tool.TButton",
        ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))
        self._text_set_readonly(self.txt_mwp, "Load XML (and PySAT) to see MWP.")

    def _build_tab_diagram(self):
        f = self.tab_diagram
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        tk.Label(
            f,
            text="Text hierarchy diagram (read-only — use File → Open XML if empty)",
            font=(FONT_FAMILY, 11, "bold"),
            fg=COL_TEXT,
            bg=COL_SURFACE,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))
        self.txt_diagram = tk.Text(f, wrap=tk.NONE, font=FONT_CODE, relief=tk.FLAT, bg=COL_SURFACE_ALT, fg=COL_TEXT, padx=10, pady=10)
        sy = ttk.Scrollbar(f, command=self.txt_diagram.yview)
        self.txt_diagram.configure(yscrollcommand=sy.set)
        self.txt_diagram.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        sy.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(0, 8))
        self._text_set_readonly(self.txt_diagram, "Open feature_model.xml (or any model) to build the tree diagram here.")

    # --- model --------------------------------------------------------------
    def load_xml_file(self, path: str):
        try:
            parser, translator = load_feature_model(path)
        except Exception as e:
            messagebox.showerror("XML error", str(e))
            return
        self._xml_path = path
        self._parser = parser
        self._translator = translator
        self._validator = SATValidator(parser, translator) if _PYSAT_OK else None
        self._rebuild_vars()
        self._rebuild_tree()
        self._refresh_logic_tab()
        self._refresh_constraints_tab()
        self._refresh_diagram_tab()
        self._refresh_mwp_text()
        self._schedule_verify()
        self.title(f"Feature Model — {os.path.basename(path)}")
        self._update_footer()

    def _rebuild_vars(self):
        self._vars.clear()
        assert self._parser is not None
        for name in self._parser.features:
            v = tk.BooleanVar(value=False)
            self._vars[name] = v
            v.trace_add("write", lambda *a, n=name: self._on_var_changed(n))

        root = self._parser.root_name
        self._suppress_trace = True
        self._vars[root].set(True)
        self._suppress_trace = False

    def _rebuild_tree(self):
        for w in self.tree_scroll.inner.winfo_children():
            w.destroy()
        self._tree_row_i = 0
        assert self._parser is not None
        self._render_feature_block(self.tree_scroll.inner, self._parser.root_name, indent=0)

    def _render_feature_block(self, parent: tk.Frame, name: str, indent: int):
        parser = self._parser
        assert parser is not None
        feat = parser.features[name]

        self._tree_row_i += 1
        bg = COL_SURFACE_ALT if self._tree_row_i % 2 else COL_SURFACE

        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, anchor=tk.W, pady=1)

        pad = tk.Frame(row, width=max(indent * 18, 4), bg=bg)
        pad.pack(side=tk.LEFT)
        pad.pack_propagate(False)

        cb = tk.Checkbutton(row, variable=self._vars[name], bg=bg, activebackground=bg, selectcolor=COL_SURFACE, bd=0, highlightthickness=0)
        cb.pack(side=tk.LEFT, padx=(4, 6))

        if name == parser.root_name:
            cb.configure(state=tk.DISABLED)
            tag = "root · always on"
            color = COL_TEXT
            pill_bg = COL_BORDER
        elif feat.mandatory:
            tag = "mandatory"
            color = COL_TEXT
            pill_bg = "#cbd5e1"
        else:
            tag = "optional"
            color = COL_TEXT_DIM
            pill_bg = COL_SURFACE_ALT

        name_lbl = tk.Label(row, text=name, font=(FONT_FAMILY, 11, "bold"), fg=color, bg=bg, anchor=tk.W)
        name_lbl.pack(side=tk.LEFT)

        tk.Label(row, text=f"  {tag}  ", font=FONT_UI_SM, fg=COL_TEXT, bg=pill_bg).pack(side=tk.LEFT, padx=(8, 0))

        for child in feat.children:
            self._render_feature_block(parent, child, indent + 1)

        if feat.group_type and feat.group_children:
            strip = tk.Frame(parent, bg=bg)
            strip.pack(fill=tk.X, padx=max(indent * 18, 8), pady=(4, 8))
            badge_bg = COL_XOR if feat.group_type == "xor" else COL_OR
            tk.Label(strip, text=f" {feat.group_type.upper()} — choose per rules ", font=FONT_UI_SM, fg="white", bg=badge_bg, padx=8, pady=4).pack(
                side=tk.LEFT
            )
            inner = tk.Frame(parent, bg=COL_SURFACE)
            inner.pack(fill=tk.X, padx=max((indent + 1) * 18, 12))
            for gc in feat.group_children:
                self._render_feature_block(inner, gc, indent + 1)

    def _on_var_changed(self, name: str):
        if self._suppress_trace:
            return
        self._suppress_trace = True
        try:
            if not self._parser:
                return
            parser = self._parser
            feat = parser.features[name]
            want = self._vars[name].get()

            if name == parser.root_name:
                self._vars[name].set(True)
                return

            if want:
                p = feat.parent
                while p:
                    self._vars[p].set(True)
                    p = parser.features[p].parent
                if feat.parent:
                    par = parser.features[feat.parent]
                    for c in par.children:
                        if c == name:
                            continue
                        cf = parser.features[c]
                        if cf.mandatory:
                            self._vars[c].set(True)
                self._apply_xor_exclusivity(name, True)
                for n in list(self._vars.keys()):
                    if self._vars[n].get():
                        self._enforce_mandatory_children(n)
                # Also enforce group defaults on features that were auto-selected
                # (mandatory closure/sibling propagation happens under suppressed traces).
                for n in list(self._vars.keys()):
                    if self._vars[n].get():
                        self._ensure_group_pick_if_parent_selected(n)
            else:
                for d in self._descendants(name):
                    self._vars[d].set(False)
                self._deselect_features_that_required(name)
        finally:
            self._suppress_trace = False

        self._schedule_verify()
        self._update_footer()

    def _descendants(self, root_name: str) -> List[str]:
        parser = self._parser
        assert parser is not None
        out: List[str] = []

        def walk(n: str):
            f = parser.features[n]
            for c in f.children:
                out.append(c)
                walk(c)
            for g in f.group_children:
                out.append(g)
                walk(g)

        walk(root_name)
        return out

    def _group_info_for_feature(self, name: str) -> Optional[Tuple[str, List[str], str]]:
        parser = self._parser
        assert parser is not None
        feat = parser.features[name]
        p = feat.parent
        if not p:
            return None
        par = parser.features[p]
        if name in par.group_children and par.group_type:
            return p, list(par.group_children), par.group_type
        return None

    def _apply_xor_exclusivity(self, name: str, turned_on: bool):
        if not turned_on:
            return
        info = self._group_info_for_feature(name)
        if not info:
            return
        _parent, members, gtype = info
        if gtype != "xor":
            return
        for m in members:
            if m != name and self._vars[m].get():
                self._vars[m].set(False)

    def _ensure_group_pick_if_parent_selected(self, name: str):
        parser = self._parser
        assert parser is not None
        if not self._vars[name].get():
            return
        feat = parser.features[name]
        if not feat.group_type or not feat.group_children:
            return
        any_on = any(self._vars[c].get() for c in feat.group_children)
        if any_on:
            return
        first = feat.group_children[0]
        self._vars[first].set(True)
        if feat.group_type == "xor":
            for m in feat.group_children[1:]:
                self._vars[m].set(False)

    def _enforce_mandatory_children(self, parent_name: str):
        parser = self._parser
        assert parser is not None
        if not self._vars[parent_name].get():
            return
        feat = parser.features[parent_name]
        for c in feat.children:
            if parser.features[c].mandatory:
                self._vars[c].set(True)

    def _deselect_features_that_required(self, removed: str):
        parser = self._parser
        trans = self._translator
        if not parser or not trans:
            return
        to_clear: Set[str] = set()
        for entry in trans.formulas:
            if entry["rule"] != "R5/R6":
                continue
            f = entry["formula"].strip()
            if "→" not in f or "∨" in f.split("→", 1)[0]:
                continue
            lhs, rhs = f.split("→", 1)
            lhs, rhs = lhs.strip(), rhs.strip()
            if rhs.startswith("¬"):
                continue
            rhs_name = rhs.strip()
            if rhs_name == removed and lhs in self._vars and self._vars[lhs].get():
                to_clear.add(lhs)
        for n in to_clear:
            self._vars[n].set(False)

    def _selected_list(self) -> List[str]:
        return sorted([n for n, v in self._vars.items() if v.get()])

    def _schedule_verify(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(200, lambda: self._verify_now())

    def _on_notebook_tab_changed(self, _event=None):
        """Refresh diagram when that tab is shown (fixes empty view if layout was late)."""
        try:
            tab = self.nb.nametowidget(self.nb.select())
        except tk.TclError:
            return
        if tab is self.tab_diagram:
            self._refresh_diagram_tab()

    def _verify_now(self, *, reveal_verification_tab: bool = False):
        self._after_id = None
        self._update_footer()
        try:
            if not self._parser or not self._translator:
                self.lbl_feasible.configure(text="Load XML first", fg=COL_TEXT_DIM, bg=COL_SURFACE)
                self._text_set_readonly(self.txt_reason, "Open a feature model XML file (File → Open XML…).")
                self._text_set_readonly(self.txt_violations, "")
                return

            selected = self._selected_list()

            if self._validator is None:
                self.lbl_feasible.configure(text="Verification needs PySAT", fg=COL_WARN_FG, bg=COL_SURFACE)
                self.card_verify.configure(bg=COL_SURFACE)
                self._text_set_readonly(
                    self.txt_reason,
                    "Install: python -m pip install python-sat\nThen restart this application.",
                )
                self._text_set_readonly(self.txt_violations, "(SAT solver not available)")
                return

            try:
                result = self._validator.verify(selected)
            except RuntimeError as e:
                self.lbl_feasible.configure(text="Error while verifying", fg=COL_BAD_FG, bg=COL_SURFACE)
                self._text_set_readonly(self.txt_reason, str(e))
                self._text_set_readonly(self.txt_violations, "")
                return

            if result["valid"]:
                self.lbl_feasible.configure(text="Feasible configuration", fg=COL_OK_FG, bg=COL_OK_BG)
            else:
                self.lbl_feasible.configure(text="Not feasible", fg=COL_BAD_FG, bg=COL_BAD_BG)

            vio = result.get("violations") or []
            vio_text = "\n".join(f"• {x}" for x in vio) if vio else "(none)"
            adds = self._validator.get_required_additions(selected)
            if adds and not result["valid"]:
                vio_text += "\n\nHints — also select:\n" + ", ".join(adds)

            self._text_set_readonly(self.txt_reason, result.get("reason", ""))
            self._text_set_readonly(self.txt_violations, vio_text)
        finally:
            if reveal_verification_tab:
                try:
                    self.nb.select(self.tab_verify)
                except tk.TclError:
                    pass

    def _apply_mwp(self):
        if not self._validator:
            messagebox.showwarning("MWP", "Install PySAT first (see banner).")
            return
        if not self._parser:
            return
        try:
            mwp = self._validator.get_mwp()
        except RuntimeError as e:
            messagebox.showerror("MWP", str(e))
            return
        feats_list = mwp.get("features") or []
        if not mwp.get("valid") or not feats_list:
            messagebox.showwarning(
                "MWP",
                "The solver did not return a valid MWP list.\nCheck the XML model and PySAT install.",
            )
            return
        selected_now = set(self._selected_list())
        missing_from_current = [f for f in feats_list if f not in selected_now]

        # Do NOT mutate user selection here. Just verify current selection + show MWP details.
        self._verify_now(reveal_verification_tab=True)
        self._refresh_mwp_text(reveal_mwp_tab=True)
        self._refresh_diagram_tab()

        if missing_from_current:
            self.footer_right.configure(
                text=(
                    f"Current selection differs from MWP: {len(missing_from_current)} "
                    f"MWP feature(s) are currently unselected."
                ),
                fg=COL_WARN_FG,
            )
        else:
            self.footer_right.configure(
                text="Current selection already matches the MWP feature set.",
                fg=COL_OK_FG,
            )
        self.after(10000, self._update_footer)

    def _bfs_feature_names(self) -> List[str]:
        """Root-first order: parent before child, parent before group members (good for trace propagation)."""
        parser = self._parser
        assert parser is not None
        out: List[str] = []
        q: List[str] = [parser.root_name]
        seen: Set[str] = set()
        while q:
            n = q.pop(0)
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
            feat = parser.features[n]
            for c in feat.children:
                q.append(c)
            for g in feat.group_children:
                q.append(g)
        return out

    def _select_mandatory_closure(self):
        """
        Turn on every structurally mandatory feature and let checkbox traces run
        so XOR/OR groups get a default first choice (same idea as MWP helper).

        Previously this used suppress_trace while toggling, which blocked those
        traces — leaving XOR/OR empty until you clicked manually.
        """
        if not self._parser:
            return
        from fm_core import get_mandatory_features

        need = set(get_mandatory_features(self._parser))
        # Reset optional selections so stale XOR/OR picks do not linger
        self._suppress_trace = True
        try:
            for n, v in self._vars.items():
                if n != self._parser.root_name:
                    v.set(False)
            self._vars[self._parser.root_name].set(True)
        finally:
            self._suppress_trace = False

        # Apply mandatory in tree order WITHOUT suppress — each set() runs propagation
        for n in self._bfs_feature_names():
            if n in need:
                self._vars[n].set(True)

        self._verify_now()

    def _refresh_logic_tab(self):
        if not self._translator:
            self._text_set_readonly(self.txt_logic, "No translator loaded. Open a valid XML file.")
            return
        body = (
            self._translator.get_all_formulas()
            + "\n\n── Combined (AND) ──\n\n"
            + self._translator.get_combined_formula()
        )
        self._text_set_readonly(self.txt_logic, body)

    def _refresh_constraints_tab(self):
        w = self.txt_constraints
        w.configure(state=tk.NORMAL)
        w.delete("1.0", tk.END)
        if not self._parser or not self._translator:
            w.insert(tk.END, "Load XML to see cross-tree constraints.")
            w.configure(state=tk.DISABLED, cursor="arrow")
            return
        if not self._parser.constraints:
            w.insert(tk.END, "(This XML file has no <constraints> entries.)")
        else:
            for i, c in enumerate(self._parser.constraints, 1):
                w.insert(tk.END, f"Constraint {i}\n", "h")
                if c.english:
                    w.insert(tk.END, f"  English:\n    {c.english}\n")
                if c.boolean_expr:
                    w.insert(tk.END, f"  Boolean:\n    {c.boolean_expr}\n")
                prop = getattr(c, "propositional", None) or "(see Logic tab)"
                w.insert(tk.END, f"  Propositional:\n    {prop}\n\n")
            w.tag_configure("h", font=(FONT_FAMILY, 11, "bold"), foreground=COL_ACCENTBAR)
        w.configure(state=tk.DISABLED, cursor="arrow")

    def _refresh_mwp_text(self, *, reveal_mwp_tab: bool = False):
        if not self._validator:
            self._text_set_readonly(
                self.txt_mwp,
                "Install PySAT (see banner), then restart the app.\nCommand: python -m pip install python-sat",
            )
            if reveal_mwp_tab:
                try:
                    self.nb.select(self.tab_mwp)
                except tk.TclError:
                    pass
            return
        try:
            mwp = self._validator.get_mwp()
        except RuntimeError as e:
            self._text_set_readonly(self.txt_mwp, str(e))
            if reveal_mwp_tab:
                try:
                    self.nb.select(self.tab_mwp)
                except tk.TclError:
                    pass
            return
        current_valid = "Unknown"
        current_reason = ""
        current_violations: list[str] = []
        if self._parser:
            if self._validator:
                try:
                    now = self._validator.verify(self._selected_list())
                    current_valid = "True" if now.get("valid") else "False"
                    current_reason = now.get("reason", "") or ""
                    current_violations = now.get("violations") or []
                except RuntimeError:
                    current_valid = "Unknown"

        lines = [
            f"Current selection valid: {current_valid}",
        ]
        if current_reason:
            lines.extend([
                f"Current selection reason:\n{current_reason}",
            ])
        if current_violations:
            lines.append("Current selection violations:")
            for v in current_violations:
                lines.append(f"  • {v}")
        lines.extend([
            "",
            f"MWP valid: {mwp.get('valid')}   (this is for the MWP configuration, not current checkboxes)",
            f"MWP note:\n{mwp.get('note')}",
            "",
            "Features in this MWP:",
        ])
        for feat in mwp.get("features", []):
            lines.append(f"  • {feat}")
        self._text_set_readonly(self.txt_mwp, "\n".join(lines))
        if reveal_mwp_tab:
            try:
                self.nb.select(self.tab_mwp)
            except tk.TclError:
                pass

    def _refresh_diagram_tab(self):
        if not self._parser:
            self._text_set_readonly(
                self.txt_diagram,
                "No model loaded yet.\n\n"
                "1. Menu: File → Open XML…\n"
                "2. Choose feature_model.xml from the Formal-Methods-Project folder.\n\n"
                "The diagram is generated from the parsed feature tree (same data as the checkboxes).",
            )
            return
        lines: List[str] = []

        def walk(n: str, indent: int):
            feat = self._parser.features[n]
            pad = "  " * indent
            kind = "root" if n == self._parser.root_name else ("mandatory" if feat.mandatory else "optional")
            lines.append(f"{pad}• {n}  [{kind}]")
            for c in feat.children:
                walk(c, indent + 1)
            if feat.group_type and feat.group_children:
                lines.append(f"{pad}  [{feat.group_type.upper()}]")
                for g in feat.group_children:
                    walk(g, indent + 2)

        walk(self._parser.root_name, 0)
        self._text_set_readonly(self.txt_diagram, "\n".join(lines))


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    app = FeatureModelApp()
    if argv and os.path.isfile(argv[0]):
        app.load_xml_file(argv[0])
    app.mainloop()


if __name__ == "__main__":
    main()
