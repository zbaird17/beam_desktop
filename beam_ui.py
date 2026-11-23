import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from beam_calculations import (
    PointLoad,
    UniformLoad,
    analyze_beam,
    evaluate_at,
    recommend_section,
)
from design_io import DesignFileError, load_design, save_design
from csv_output import export_csv
from pdf_report import export_pdf


def format_chart_crosshair_value(quantity, value):
    if quantity == "V":
        return f"{value:+.3f} kips"
    if quantity == "M":
        return f"{value:+.3f} kip-ft"
    if quantity == "theta":
        return f"{value:+.6f} rad"
    if quantity == "y":
        return f"{value:+.3f} in"
    return f"{value:+.3f}"


class BeamDesignerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Beam Designer")
        self.root.geometry("1450x900")
        self.root.minsize(900, 620)

        self.support = "simply_supported"
        self.span = 20.0
        self.material = "steel"
        self.section = "W12x26"
        self.deflection_limit = 360
        self.crosshair = 10.0
        self.load_counter = 1
        self.loads = [{"id": 1, "kind": "uniform", "magnitude": 1.0,
                       "start": 0.0, "end": 20.0}]
        self.latest_analysis = None
        self.dragging_load_id = None

        self._build_layout()
        self.refresh()

    def _build_layout(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f6f7")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#f3f6f7", foreground="#172f3b")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"),
                        background="#f3f6f7")
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"),
                        background="#ffffff")
        style.configure("TButton", padding=(10, 7))

        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=24, pady=(14, 10))
        ttk.Label(header, text="Beam Designer", style="Title.TLabel").pack(side="left")
        header_actions = ttk.Frame(header)
        header_actions.pack(side="right")
        ttk.Button(header_actions, text="Load design",
                   command=self.load_design).pack(side="left", padx=(0, 6))
        ttk.Button(header_actions, text="Save design",
                   command=self.save_design).pack(side="left")
        ttk.Button(header_actions, text="Export CSV",
                   command=self.export_csv).pack(side="left", padx=(6, 0))
        ttk.Button(header_actions, text="Save PDF",
                   command=self.save_pdf).pack(side="left", padx=(6, 0))

        app = ttk.Frame(self.root)
        app.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        app.columnconfigure(1, weight=1)
        app.rowconfigure(0, weight=1)

        left_shell = ttk.Frame(app, width=350)
        left_shell.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left_shell.grid_propagate(False)

        self.left_canvas = tk.Canvas(left_shell, bg="#f3f6f7", highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_shell, orient="vertical",
                                  command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.left_canvas.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(self.left_canvas)
        left_window = self.left_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>",
                  lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.bind("<Configure>",
                              lambda e: self.left_canvas.itemconfigure(left_window, width=e.width))

        self._build_controls(left)

        right_shell = ttk.Frame(app)
        right_shell.grid(row=0, column=1, sticky="nsew")
        right_shell.rowconfigure(0, weight=1)
        right_shell.columnconfigure(0, weight=1)

        self.right_canvas = tk.Canvas(right_shell, bg="#f3f6f7", highlightthickness=0)
        right_scroll = ttk.Scrollbar(right_shell, orient="vertical",
                                     command=self.right_canvas.yview)
        self.right_canvas.configure(yscrollcommand=right_scroll.set)
        right_scroll.pack(side="right", fill="y")
        self.right_canvas.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(self.right_canvas)
        right_window = self.right_canvas.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>",
                   lambda e: self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all")))
        self.right_canvas.bind("<Configure>",
                               lambda e: self.right_canvas.itemconfigure(right_window, width=e.width))

        self._build_results(right)
        self._enable_mousewheel_scrolling()

    def _enable_mousewheel_scrolling(self):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        canvas = None
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.left_canvas:
                canvas = self.left_canvas
                break
            if widget is self.right_canvas:
                canvas = self.right_canvas
                break
            widget = getattr(widget, "master", None)
        if canvas is None:
            return

        if hasattr(event, "delta") and event.delta:
            direction = -1 if event.delta > 0 else 1
            units = max(1, abs(int(event.delta)) // 40)
        elif getattr(event, "num", None) == 4:
            direction = -1
            units = 1
        else:
            direction = 1
            units = 1
        canvas.yview_scroll(direction * units, "units")
        return "break"

    def _card(self, parent):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=14)
        frame.configure(relief="solid", borderwidth=1)
        return frame

    def _build_controls(self, parent):
        beam_card = self._card(parent)
        beam_card.pack(fill="x", pady=(0, 12))
        ttk.Label(beam_card, text="Beam", style="Section.TLabel").pack(anchor="w")

        ttk.Label(beam_card, text="Support type").pack(anchor="w", pady=(10, 2))
        self.support_var = tk.StringVar(value="Simply supported")
        support = ttk.Combobox(beam_card, textvariable=self.support_var, state="readonly",
                               values=("Simply supported", "Cantilever (fixed left end)"))
        support.pack(fill="x")
        support.bind("<<ComboboxSelected>>", self.on_support)

        ttk.Label(beam_card, text="Span").pack(anchor="w", pady=(10, 2))
        span_row = ttk.Frame(beam_card)
        span_row.pack(fill="x")
        self.span_var = tk.StringVar(value="20")
        self.span_slider = tk.Scale(span_row, from_=4, to=40, resolution=0.25,
                                    orient="horizontal", command=self.on_span_slider,
                                    length=220, showvalue=False,
                                    highlightthickness=0)
        self.span_slider.set(20)
        self.span_slider.pack(side="left", fill="x", expand=True)
        span_number = ttk.Entry(span_row, textvariable=self.span_var, width=8)
        span_number.pack(side="left", padx=(8, 0))
        span_number.bind("<KeyRelease>", self.on_span_number)
        ttk.Label(span_row, text="ft").pack(side="left")
        self.span_error = ttk.Label(beam_card, foreground="#b42318")
        self.span_error.pack(anchor="w")

        loads_card = self._card(parent)
        loads_card.pack(fill="x", pady=(0, 12))
        ttk.Label(loads_card, text="Loads", style="Section.TLabel").pack(anchor="w")
        self.load_list = ttk.Frame(loads_card)
        self.load_list.pack(fill="x", pady=(6, 6))
        buttons = ttk.Frame(loads_card)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="+ Add point load",
                   command=self.add_point_load).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="+ Add uniform load",
                   command=self.add_uniform_load).pack(side="left")
        self.load_error = ttk.Label(loads_card, foreground="#b42318", wraplength=300)
        self.load_error.pack(anchor="w", pady=(6, 0))

        section_card = self._card(parent)
        section_card.pack(fill="x", pady=(0, 12))
        ttk.Label(section_card, text="Material and section",
                  style="Section.TLabel").pack(anchor="w")
        ttk.Label(section_card, text="Material").pack(anchor="w", pady=(10, 2))
        self.material_var = tk.StringVar(value="Steel W-shapes")
        material = ttk.Combobox(section_card, textvariable=self.material_var,
                                state="readonly",
                                values=("Steel W-shapes",
                                        "Douglas Fir-Larch No. 2 lumber"))
        material.pack(fill="x")
        material.bind("<<ComboboxSelected>>", self.on_material)

        ttk.Label(section_card, text="Section").pack(anchor="w", pady=(10, 2))
        self.section_var = tk.StringVar(value="W12x26")
        self.section_combo = ttk.Combobox(section_card, textvariable=self.section_var,
                                          state="readonly")
        self.section_combo.pack(fill="x")
        self.section_combo.bind("<<ComboboxSelected>>", self.on_section)

        properties_grid = ttk.Frame(section_card)
        properties_grid.pack(fill="x", pady=(8, 0))
        properties_grid.columnconfigure(0, weight=1)
        properties_grid.columnconfigure(1, weight=1)
        self.properties_left_label = ttk.Label(properties_grid, justify="left")
        self.properties_left_label.grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.properties_right_label = ttk.Label(properties_grid, justify="left")
        self.properties_right_label.grid(row=0, column=1, sticky="nw")

        limit_card = self._card(parent)
        limit_card.pack(fill="x")
        ttk.Label(limit_card, text="Deflection limit",
                  style="Section.TLabel").pack(anchor="w")
        self.limit_var = tk.IntVar(value=360)
        ttk.Radiobutton(limit_card, text="L/240", variable=self.limit_var,
                        value=240, command=self.on_limit).pack(anchor="w", pady=(8, 2))
        ttk.Radiobutton(limit_card, text="L/360 (Default)", variable=self.limit_var,
                        value=360, command=self.on_limit).pack(anchor="w")

    def _build_results(self, parent):
        title = ttk.Label(parent, text="Simply supported beam",
                          font=("Segoe UI", 16, "bold"),
                          background="#f3f6f7")
        title.pack(anchor="w", pady=(0, 8))

        fig = Figure(figsize=(11, 9), dpi=100, facecolor="#f3f6f7")
        gs = fig.add_gridspec(5, 1, height_ratios=[1.5, 1, 1, 1, 1],
                              hspace=0.48)
        self.beam_ax = fig.add_subplot(gs[0])
        self.shear_ax = fig.add_subplot(gs[1], sharex=self.beam_ax)
        self.moment_ax = fig.add_subplot(gs[2], sharex=self.beam_ax)
        self.rotation_ax = fig.add_subplot(gs[3], sharex=self.beam_ax)
        self.deflection_ax = fig.add_subplot(gs[4], sharex=self.beam_ax)
        fig.subplots_adjust(left=0.09, right=0.98, top=0.98, bottom=0.05)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.configure(height=680)
        canvas_widget.pack(fill="x", pady=(0, 8))
        canvas.draw()
        self.figure = fig
        self.canvas = canvas
        self.canvas_widget = canvas_widget
        self.axes = (self.shear_ax, self.moment_ax,
                     self.rotation_ax, self.deflection_ax)

        for ax in self.axes:
            ax.set_facecolor("#ffffff")
            ax.grid(True, axis="y", alpha=0.25)
            ax.axhline(0, color="#8aa0a7", linewidth=1)

        canvas_widget.bind("<Motion>", self.on_canvas_motion)
        canvas_widget.bind("<Button-1>", self.on_canvas_motion)
        canvas_widget.bind("<B1-Motion>", self.on_canvas_motion)
        canvas_widget.bind("<ButtonRelease-1>", self.on_canvas_release)
        canvas_widget.bind("<FocusIn>", lambda e: canvas_widget.focus_set())
        canvas_widget.focus_set()
        canvas_widget.bind("<KeyPress>", self.on_canvas_key)

        output_grid = ttk.Frame(parent)
        output_grid.pack(fill="x", pady=(0, 8))
        output_grid.columnconfigure(0, weight=1)
        output_grid.columnconfigure(1, weight=1)

        left_output = ttk.Frame(output_grid)
        left_output.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        summary_card = self._card(left_output)
        summary_card.pack(fill="x", pady=(0, 6))
        ttk.Label(summary_card, text="Maximum values",
                  style="Section.TLabel").pack(anchor="w")
        self.summary_label = ttk.Label(summary_card, justify="left")
        self.summary_label.pack(anchor="w", pady=(4, 0))

        readout_card = self._card(left_output)
        readout_card.pack(fill="x")
        ttk.Label(readout_card, text="Crosshair readout",
                  style="Section.TLabel").pack(anchor="w")
        self.readout_label = ttk.Label(readout_card, justify="left")
        self.readout_label.pack(anchor="w", pady=(4, 0))

        right_output = ttk.Frame(output_grid)
        right_output.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        checks_card = self._card(right_output)
        checks_card.pack(fill="x", pady=(0, 6))
        ttk.Label(checks_card, text="Bending and deflection checks",
                  style="Section.TLabel").pack(anchor="w")
        self.checks_label = ttk.Label(checks_card, justify="left")
        self.checks_label.pack(anchor="w", pady=(4, 0))

        recommendation_card = self._card(right_output)
        recommendation_card.pack(fill="x")
        ttk.Label(recommendation_card, text="Suggested section",
                  style="Section.TLabel").pack(anchor="w")
        self.recommendation_label = ttk.Label(recommendation_card, justify="left")
        self.recommendation_label.pack(anchor="w", pady=(4, 0))
        self.use_button = ttk.Button(recommendation_card, text="Use suggested section",
                                     command=self.use_recommendation)
        self.use_button.pack(anchor="w", pady=(6, 0))

        self.title_label = title
        self.suggested_section = None

    def on_support(self, event=None):
        self.support = ("simply_supported"
                        if self.support_var.get() == "Simply supported"
                        else "cantilever")
        self.refresh()

    def on_span_slider(self, value):
        self.span = float(value)
        self.span_var.set(f"{self.span:g}")
        self.span_error.configure(text="")
        self.refresh()

    def on_span_number(self, event=None):
        try:
            span = float(self.span_var.get())
            if 4 <= span <= 40:
                self.span = span
                self.span_slider.set(span)
                self.span_error.configure(text="")
                self.refresh()
            else:
                self.span_error.configure(text="Span must be between 4 and 40 ft.")
        except ValueError:
            self.span_error.configure(text="Enter a finite span.")

    def on_material(self, event=None):
        is_steel = self.material_var.get() == "Steel W-shapes"
        self.material = "steel" if is_steel else "lumber"
        names = (["W8x10", "W10x12", "W12x26", "W14x22",
                  "W16x26", "W18x35", "W21x44", "W24x55"]
                 if is_steel else ["2x8", "2x10", "2x12"])
        self.section_combo.configure(values=names)
        self.section = names[2] if is_steel else names[0]
        self.section_var.set(self.section)
        self.refresh()

    def on_section(self, event=None):
        self.section = self.section_var.get()
        self.refresh()

    def on_limit(self):
        self.deflection_limit = self.limit_var.get()
        self.refresh()

    def add_point_load(self):
        position = self.span if self.support == "cantilever" else self.span / 2
        self.load_counter += 1
        self.loads.append({"id": self.load_counter, "kind": "point",
                           "magnitude": 1.0, "position": position})
        self.refresh()

    def add_uniform_load(self):
        self.load_counter += 1
        self.loads.append({"id": self.load_counter, "kind": "uniform",
                           "magnitude": 1.0, "start": 2.0, "end": 4.0})
        self.refresh()

    def remove_load(self, load_id):
        self.loads = [load for load in self.loads if load["id"] != load_id]
        self.refresh()

    def use_recommendation(self):
        if self.suggested_section:
            self.section_var.set(self.suggested_section)
            self.section = self.suggested_section
            self.refresh()

    def _state_for_file(self):
        return {
            "support": self.support,
            "span": self.span,
            "material": self.material,
            "section": self.section,
            "deflection_limit": self.deflection_limit,
            "loads": self.loads,
        }

    def save_design(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Beam Designer design",
            defaultextension=".beam.json",
            filetypes=(("Beam design (*.beam.json)", "*.beam.json"),
                       ("JSON files (*.json)", "*.json"),
                       ("All files (*.*)", "*.*")),
        )
        if not path:
            return
        try:
            save_design(path, self._state_for_file())
        except (DesignFileError, OSError) as exc:
            messagebox.showerror("Could not save design", str(exc),
                                 parent=self.root)
            return
        messagebox.showinfo("Design saved",
                            f"Saved beam design to:\n{path}",
                            parent=self.root)

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export beam output values",
            defaultextension=".csv",
            filetypes=(("Excel CSV (*.csv)", "*.csv"),
                       ("CSV files (*.csv)", "*.csv"),
                       ("All files (*.*)", "*.*")),
        )
        if not path:
            return
        try:
            export_csv(path, self._state_for_file())
        except (ValueError, OSError) as exc:
            messagebox.showerror("Could not export CSV", str(exc),
                                 parent=self.root)
            return
        messagebox.showinfo(
            "CSV exported",
            f"Exported beam output values to:\n{path}",
            parent=self.root,
        )

    def save_pdf(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save beam design PDF",
            defaultextension=".pdf",
            filetypes=(("PDF document (*.pdf)", "*.pdf"),
                       ("All files (*.*)", "*.*")),
        )
        if not path:
            return
        try:
            export_pdf(path, self._state_for_file())
        except (ValueError, OSError) as exc:
            messagebox.showerror("Could not save PDF", str(exc),
                                 parent=self.root)
            return
        messagebox.showinfo(
            "PDF saved",
            f"Saved the engineering report to:\n{path}",
            parent=self.root,
        )

    def load_design(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load Beam Designer design",
            filetypes=(("Beam design (*.beam.json)", "*.beam.json"),
                       ("JSON files (*.json)", "*.json"),
                       ("All files (*.*)", "*.*")),
        )
        if not path:
            return
        try:
            design = load_design(path)
        except (DesignFileError, OSError) as exc:
            messagebox.showerror("Could not load design", str(exc),
                                 parent=self.root)
            return

        self.support = design["support"]
        self.support_var.set(
            "Simply supported" if self.support == "simply_supported"
            else "Cantilever (fixed left end)")
        self.span = design["span"]
        self.span_var.set(f"{self.span:g}")
        self.span_slider.set(self.span)
        self.span_error.configure(text="")
        self.material = design["material"]
        self.material_var.set(
            "Steel W-shapes" if self.material == "steel"
            else "Douglas Fir-Larch No. 2 lumber")
        names = (["W8x10", "W10x12", "W12x26", "W14x22",
                  "W16x26", "W18x35", "W21x44", "W24x55"]
                 if self.material == "steel"
                 else ["2x8", "2x10", "2x12"])
        self.section_combo.configure(values=names)
        self.section = design["section"]
        self.section_var.set(self.section)
        self.deflection_limit = design["deflection_limit"]
        self.limit_var.set(self.deflection_limit)
        self.load_counter = len(design["loads"])
        self.loads = []
        for load_id, load in enumerate(design["loads"], start=1):
            self.loads.append({"id": load_id, **load})
        self.crosshair = min(self.span, self.crosshair)
        self.refresh()

    def _point_loads(self):
        return tuple(PointLoad(load["magnitude"], load["position"])
                     for load in self.loads if load["kind"] == "point")

    def _uniform_loads(self):
        return tuple(UniformLoad(load["magnitude"], load["start"], load["end"])
                     for load in self.loads if load["kind"] == "uniform")

    def refresh(self, rebuild_loads=True):
        if rebuild_loads:
            for child in self.load_list.winfo_children():
                child.destroy()
        self.load_error.configure(text="")
        if rebuild_loads:
            for load in self.loads:
                self._render_load_editor(load)

        names = (["W8x10", "W10x12", "W12x26", "W14x22",
                  "W16x26", "W18x35", "W21x44", "W24x55"]
                 if self.material == "steel"
                 else ["2x8", "2x10", "2x12"])
        self.section_combo.configure(values=names)
        if self.section not in names:
            self.section = names[0]
            self.section_var.set(self.section)

        try:
            analysis = analyze_beam(
                self.support, self.span, self.material, self.section,
                self._point_loads(), self._uniform_loads(),
                self.deflection_limit)
        except ValueError as exc:
            self.load_error.configure(text=str(exc))
            return

        self.latest_analysis = analysis
        self.crosshair = max(0.0, min(self.span, self.crosshair))
        self._render_results(analysis)
        self._render_crosshair()

    def _render_load_editor(self, load):
        card = ttk.Frame(self.load_list, relief="solid", borderwidth=1,
                         padding=8)
        card.pack(fill="x", pady=(0, 6))
        title = "Point load" if load["kind"] == "point" else "Uniform load"
        row = ttk.Frame(card)
        row.pack(fill="x")
        ttk.Label(row, text=title, font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(row, text="Remove",
                   command=lambda i=load["id"]: self.remove_load(i)).pack(side="right")

        fields = ttk.Frame(card)
        fields.pack(fill="x", pady=(6, 0))
        if load["kind"] == "point":
            self._load_field(fields, "Magnitude", "kips", load, "magnitude")
            self._load_field(fields, "Position", "ft", load, "position")
        else:
            self._load_field(fields, "Magnitude", "kip/ft", load, "magnitude")
            self._load_field(fields, "Start", "ft", load, "start")
            self._load_field(fields, "End", "ft", load, "end")

    def _load_field(self, parent, label, unit, load, key):
        frame = ttk.Frame(parent)
        frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Label(frame, text=f"{label} ({unit})").pack(anchor="w")
        var = tk.StringVar(value=str(load[key]))
        entry = ttk.Entry(frame, textvariable=var, width=8)
        entry.pack(fill="x")

        def update(event=None):
            try:
                value = float(var.get())
                load[key] = value
                self.load_error.configure(text="")
                self.refresh(rebuild_loads=False)
            except ValueError:
                self.load_error.configure(text=f"{label} must be a finite number.")
        entry.bind("<KeyRelease>", update)

    def _render_results(self, analysis):
        support_label = "Simply supported" if self.support == "simply_supported" else "Cantilever"
        self.title_label.configure(text=f"{support_label} beam")
        p = analysis.properties
        self.properties_left_label.configure(
            text=(f"E = {p['E']:,.0f} ksi\n"
                  f"Ix = {p['Ix']:g} in4\n"
                  f"Weight = {p['weight']:g} lb/ft"))
        self.properties_right_label.configure(
            text=(f"Fb = {p['Fb']:,.3f} ksi\n"
                  f"Sx = {p['Sx']:g} in3\n"
                  f"Self-weight = {p['weight']/1000:.6g} kip/ft"))

        ra = analysis.reactions["RA"]
        rb = analysis.reactions["RB"]
        ca = analysis.reactions["CA"]
        reaction_text = f"RA = {ra:.3f} kip upward\n"
        if self.support == "simply_supported":
            reaction_text += f"RB = {rb:.3f} kip upward"
        else:
            reaction_text += f"CA = {ca:.3f} kip-ft"
        self.summary_label.configure(
            text=(f"{reaction_text}\n"
                  f"|V|max = {analysis.shear_max.value:.3f} kips at "
                  f"{', '.join(f'{x:g} ft' for x in analysis.shear_max.positions)}\n"
                  f"|M|max = {analysis.moment_max.value:.3f} kip-ft at "
                  f"{', '.join(f'{x:g} ft' for x in analysis.moment_max.positions)}\n"
                  f"|theta|max = {analysis.rotation_max.value:.6f} rad at "
                  f"{', '.join(f'{x:g} ft' for x in analysis.rotation_max.positions)}\n"
                  f"|y|max = {abs(analysis.deflection_max.value):.3f} in at "
                  f"{', '.join(f'{x:g} ft' for x in analysis.deflection_max.positions)}"))

        self.checks_label.configure(
            text=(f"Bending: fb = {analysis.bending_stress:.3f} ksi / "
                  f"{analysis.bending_allowable:.3f} ksi "
                  f"({analysis.bending_ratio*100:.1f}% — "
                  f"{'PASS' if analysis.bending_ratio <= 1 else 'FAIL'})\n"
                  f"Deflection: y_max = {abs(analysis.deflection_max.value):.3f} in / "
                  f"{analysis.deflection_allowable:.3f} in "
                  f"(L/{self.deflection_limit}, "
                  f"{analysis.deflection_ratio*100:.1f}% — "
                  f"{'PASS' if analysis.deflection_ratio <= 1 else 'FAIL'})"))

        recommendation = recommend_section(
            self.support, self.span, self.material,
            self._point_loads(), self._uniform_loads(),
            self.deflection_limit)
        self.suggested_section = recommendation["section"]
        if self.suggested_section:
            rec = recommendation["analysis"]
            self.recommendation_label.configure(
                text=(f"Suggested section: {self.suggested_section}\n"
                      f"Lightest passing section · "
                      f"{rec.properties['weight']:g} lb/ft"))
            self.use_button.configure(state="normal")
        else:
            self.recommendation_label.configure(
                text="No listed section passes both checks.")
            self.use_button.configure(state="disabled")

        self._draw_beam(analysis)
        self._draw_diagrams(analysis)
        self.canvas.draw_idle()

    def _draw_beam(self, analysis):
        ax = self.beam_ax
        ax.clear()
        ax.set_facecolor("#ffffff")
        ax.set_xlim(-1, self.span + 1)
        ax.set_ylim(-2.5, 3.2)
        ax.axis("off")
        ax.plot([0, self.span], [0, 0], color="#172f3b", linewidth=6,
                solid_capstyle="round")
        if self.support == "simply_supported":
            ax.plot([0, -0.8, 0.8, 0], [0, -1.2, -1.2, 0], color="#4567a7")
            ax.plot([self.span, self.span-0.8, self.span+0.8, self.span],
                    [0, -1.2, -1.2, 0], color="#4567a7")
        else:
            ax.fill_between([-1.0, 0.0], [-1.8, -1.8], [1.8, 1.8],
                            color="#dce5e8")

        ra = analysis.reactions["RA"]
        rb = analysis.reactions["RB"]
        ax.annotate(f"RA={ra:.2f} k",
                    xy=(0, -0.2), xytext=(0, -2),
                    ha="center", arrowprops=dict(arrowstyle="->", color="#16784b"))
        if self.support == "simply_supported":
            ax.annotate(f"RB={rb:.2f} k",
                        xy=(self.span, -0.2), xytext=(self.span, -2),
                        ha="center", arrowprops=dict(arrowstyle="->", color="#16784b"))
        else:
            ax.text(-0.2, 2.4, f"CA={analysis.reactions['CA']:.2f} kip-ft",
                    ha="left", fontsize=9)

        for load in self.loads:
            if load["kind"] == "point":
                direction = 1 if load["magnitude"] >= 0 else -1
                text_y = 2.2 * direction
                ax.annotate(f"{load['magnitude']:g} kip",
                            xy=(load["position"], 0),
                            xytext=(load["position"], text_y),
                            ha="center",
                            arrowprops=dict(
                                arrowstyle="-|>" if direction > 0 else "<|-",
                                color="#a45b2a",
                                mutation_scale=14,
                                lw=1.5,
                            ))
            else:
                start = max(0, load["start"])
                end = min(self.span, load["end"])
                if start < end:
                    y = 1.7 if load["magnitude"] >= 0 else -1.7
                    ax.annotate(f"{load['magnitude']:g} kip/ft",
                                xy=((start + end)/2, y),
                                xytext=((start + end)/2, y),
                                ha="center", color="#4567a7")
                    ax.plot([start, end], [0.7 if y > 0 else -0.7] * 2,
                            color="#4567a7", linewidth=2)
                    arrow_count = max(2, min(12, int((end - start) / 1.5) + 1))
                    for arrow_index in range(arrow_count):
                        fraction = arrow_index / (arrow_count - 1)
                        position = start + (end - start) * fraction
                        if load["magnitude"] >= 0:
                            ax.annotate("", xy=(position, 0.02),
                                        xytext=(position, 1.15),
                                        arrowprops=dict(
                                            arrowstyle="-|>",
                                            color="#4567a7",
                                            mutation_scale=12,
                                            lw=1.2,
                                        ))
                        else:
                            ax.annotate("", xy=(position, 1.15),
                                        xytext=(position, 0.02),
                                        arrowprops=dict(
                                            arrowstyle="-|>",
                                            color="#4567a7",
                                            mutation_scale=12,
                                            lw=1.2,
                                        ))
        ax.text(self.span / 2, -2.3, f"L = {self.span:g} ft",
                ha="center", fontsize=9)

    def _draw_diagrams(self, analysis):
        quantities = (
            (self.shear_ax, "V", "Shear",
             analysis.shear_max, "#087e83"),
            (self.moment_ax, "M", "Moment",
             analysis.moment_max, "#087e83"),
            (self.rotation_ax, "theta", "Rotation θ",
             analysis.rotation_max, "#7a4aa3"),
            (self.deflection_ax, "y", "Deflection y (downward negative)",
             analysis.deflection_max, "#4567a7"),
        )
        units = {"V": "kips", "M": "kip-ft", "theta": "rad", "y": "in"}
        for ax, key, label, maximum, color in quantities:
            ax.clear()
            ax.set_facecolor("#ffffff")
            ax.grid(True, axis="y", alpha=0.25)
            ax.axhline(0, color="#8aa0a7", linewidth=1)
            xs = [sample["x"] for sample in analysis.samples]
            ys = [sample[key] for sample in analysis.samples]
            ax.plot(xs, ys, color=color, linewidth=1.8)
            ax.fill_between(xs, 0, ys, alpha=0.10, color=color)
            ax.set_title(f"{label} ({units[key]})", loc="left",
                         fontsize=9, fontweight="bold", pad=30)
            ax.set_ylabel(units[key], fontsize=8)
            ax.set_xlim(0, self.span)
            ax.tick_params(axis="both", labelsize=8)
            if ax is not self.deflection_ax:
                ax.tick_params(labelbottom=False)
            else:
                ax.set_xlabel("Position x (ft)", fontsize=8)
            for point_x, point_y in maximum.points:
                ax.plot(point_x, point_y, "o", color=color, markersize=4)

    def on_canvas_motion(self, event):
        if not self.latest_analysis:
            return
        widget_height = self.canvas_widget.winfo_height()
        display_y = widget_height - event.y
        beam_bbox = self.beam_ax.bbox
        beam_hit = (beam_bbox.x0 <= event.x <= beam_bbox.x1
                    and beam_bbox.y0 <= display_y <= beam_bbox.y1)

        if beam_hit:
            try:
                beam_x = self.beam_ax.transData.inverted().transform(
                    (event.x, display_y))[0]
            except Exception:
                beam_x = None
            if beam_x is not None:
                if self.dragging_load_id is not None:
                    snapped = round(max(0.0, min(self.span, beam_x)) * 4) / 4
                    for load in self.loads:
                        if load["id"] == self.dragging_load_id and load["kind"] == "point":
                            load["position"] = snapped
                            self.refresh(rebuild_loads=False)
                            return
                nearest = None
                nearest_distance = 1e9
                for load in self.loads:
                    if load["kind"] == "point":
                        distance = abs(load["position"] - beam_x)
                        if distance < nearest_distance:
                            nearest_distance = distance
                            nearest = load
                if nearest is not None and nearest_distance <= max(0.5, self.span / 40):
                    self.dragging_load_id = nearest["id"]
                    return

        shear_bbox = self.shear_ax.bbox
        if not (shear_bbox.x0 <= event.x <= shear_bbox.x1):
            return
        try:
            fraction = (event.x - shear_bbox.x0) / (
                shear_bbox.x1 - shear_bbox.x0)
            self.crosshair = max(0.0, min(self.span, fraction * self.span))
        except Exception:
            return
        self._render_crosshair()

    def on_canvas_release(self, event):
        self.dragging_load_id = None

    def on_canvas_key(self, event):
        if event.keysym in ("Left", "Right"):
            step = 1.0 if event.state & 0x1 else 0.25
            delta = -step if event.keysym == "Left" else step
            self.crosshair = max(0.0, min(self.span, self.crosshair + delta))
        elif event.keysym == "Home":
            self.crosshair = 0.0
        elif event.keysym == "End":
            self.crosshair = self.span
        else:
            return
        self._render_crosshair()

    def _render_crosshair(self):
        if not self.latest_analysis:
            return
        for ax in self.axes:
            for line in list(ax.lines):
                if getattr(line, "_beam_crosshair", False):
                    line.remove()
            for text in list(ax.texts):
                if getattr(text, "_beam_crosshair", False):
                    text.remove()

        direct = evaluate_at(
            self.latest_analysis, self.crosshair,
            self._point_loads(), self._uniform_loads())

        chart_values = (
            (self.shear_ax, "V", "V", "#087e83"),
            (self.moment_ax, "M", "M", "#087e83"),
            (self.rotation_ax, "theta", "theta", "#7a4aa3"),
            (self.deflection_ax, "y", "y", "#4567a7"),
        )
        for ax, key, label, color in chart_values:
            line = ax.axvline(self.crosshair, color="#172f3b",
                              linewidth=1, linestyle="--", alpha=0.7)
            line._beam_crosshair = True
            value = direct[key]
            marker = ax.plot(self.crosshair, value, "o", color=color,
                             markersize=5, zorder=7)[0]
            marker._beam_crosshair = True

            right_side = self.crosshair > self.span * 0.68
            annotation = ax.annotate(
                f"x={direct['x']:.2f} ft\n{label} = "
                f"{format_chart_crosshair_value(key, value)}",
                xy=(self.crosshair, value),
                xytext=(-10 if right_side else 10,
                        10),
                textcoords="offset points",
                ha="right" if right_side else "left",
                va="bottom",
                fontsize=8,
                color="#172f3b",
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="#ffffff",
                          edgecolor="#b9c8cd",
                          alpha=0.96),
                zorder=9,
            )
            annotation._beam_crosshair = True

        self.readout_label.configure(
            text=(f"x = {direct['x']:.2f} ft   "
                  f"V = {direct['V']:+.3f} kips   "
                  f"M = {direct['M']:+.3f} kip-ft\n"
                  f"theta = {direct['theta']:+.6f} rad   "
                  f"y = {direct['y']:+.3f} in"))
        self.canvas.draw_idle()
