import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

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
        ttk.Label(header, text="Single-span beam analysis").pack(side="right")

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

        self.properties_label = ttk.Label(section_card, justify="left")
        self.properties_label.pack(anchor="w", pady=(8, 0))

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

        summary_card = self._card(parent)
        summary_card.pack(fill="x", pady=(0, 8))
        self.summary_label = ttk.Label(summary_card, justify="left")
        self.summary_label.pack(anchor="w")

        readout_card = self._card(parent)
        readout_card.pack(fill="x", pady=(0, 8))
        ttk.Label(readout_card, text="Crosshair readout",
                  style="Section.TLabel").pack(anchor="w")
        self.readout_label = ttk.Label(readout_card, justify="left")
        self.readout_label.pack(anchor="w", pady=(4, 0))

        checks_card = self._card(parent)
        checks_card.pack(fill="x", pady=(0, 8))
        self.checks_label = ttk.Label(checks_card, justify="left")
        self.checks_label.pack(anchor="w")

        recommendation_card = self._card(parent)
        recommendation_card.pack(fill="x", pady=(0, 8))
        self.recommendation_label = ttk.Label(recommendation_card, justify="left")
        self.recommendation_label.pack(anchor="w")
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
        self.properties_label.configure(
            text=(f"E = {p['E']:,.0f} ksi\nFb = {p['Fb']:,.3f} ksi\n"
                  f"Ix = {p['Ix']:g} in4\nSx = {p['Sx']:g} in3\n"
                  f"Weight = {p['weight']:g} lb/ft\n"
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
                ax.annotate(f"{load['magnitude']:g} kip",
                            xy=(load["position"], 0),
                            xytext=(load["position"], 2.2 * direction),
                            ha="center",
                            arrowprops=dict(arrowstyle="-|>", color="#a45b2a"))
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
        ax.text(self.span / 2, -2.3, f"L = {self.span:g} ft",
                ha="center", fontsize=9)

    def _draw_diagrams(self, analysis):
        quantities = (
            (self.shear_ax, "V", "Shear (kips)",
             analysis.shear_max, "#087e83"),
            (self.moment_ax, "M", "Moment (kip-ft)",
             analysis.moment_max, "#087e83"),
            (self.rotation_ax, "theta", "Rotation θ (rad)",
             analysis.rotation_max, "#7a4aa3"),
            (self.deflection_ax, "y", "Deflection y (in)",
             analysis.deflection_max, "#4567a7"),
        )
        for ax, key, label, maximum, color in quantities:
            ax.clear()
            ax.set_facecolor("#ffffff")
            ax.grid(True, axis="y", alpha=0.25)
            ax.axhline(0, color="#8aa0a7", linewidth=1)
            xs = [sample["x"] for sample in analysis.samples]
            ys = [sample[key] for sample in analysis.samples]
            ax.plot(xs, ys, color=color, linewidth=1.8)
            ax.fill_between(xs, 0, ys, alpha=0.10, color=color)
            ax.set_ylabel(label, fontsize=8)
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
        for ax in self.axes:
            line = ax.axvline(self.crosshair, color="#172f3b",
                              linewidth=1, linestyle="--", alpha=0.7)
            line._beam_crosshair = True

        direct = evaluate_at(
            self.latest_analysis, self.crosshair,
            self._point_loads(), self._uniform_loads())
        self.readout_label.configure(
            text=(f"x = {direct['x']:.2f} ft   "
                  f"V = {direct['V']:+.3f} kips   "
                  f"M = {direct['M']:+.3f} kip-ft\n"
                  f"theta = {direct['theta']:+.6f} rad   "
                  f"y = {direct['y']:+.3f} in"))
        self.canvas.draw_idle()
