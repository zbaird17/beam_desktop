from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from beam_calculations import (
    PointLoad,
    UniformLoad,
    analyze_beam,
)


def positions_text(positions):
    if not positions:
        return "none"
    return ", ".join(f"{position:g} ft" for position in positions)


def export_pdf(path, state):
    support = state["support"]
    span = float(state["span"])
    material = state["material"]
    section = state["section"]
    deflection_limit = int(state["deflection_limit"])

    point_loads = tuple(
        PointLoad(float(load["magnitude"]), float(load["position"]))
        for load in state["loads"]
        if load["kind"] == "point"
    )
    uniform_loads = tuple(
        UniformLoad(
            float(load["magnitude"]),
            float(load["start"]),
            float(load["end"]),
        )
        for load in state["loads"]
        if load["kind"] == "uniform"
    )

    analysis = analyze_beam(
        support, span, material, section,
        point_loads, uniform_loads, deflection_limit,
    )

    support_label = ("Simply supported" if support == "simply_supported"
                     else "Cantilever (fixed left end)")
    material_label = ("Steel W-shapes" if material == "steel"
                      else "Douglas Fir-Larch No. 2 lumber")
    p = analysis.properties

    with PdfPages(str(path)) as pdf:
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_axes([0.04, 0.04, 0.92, 0.92])
        ax.axis("off")

        ax.text(0.02, 0.96, "Beam Designer - Engineering Report",
                fontsize=18, fontweight="bold", va="top")
        ax.text(0.02, 0.91,
                f"Support: {support_label}   |   Span: {span:g} ft",
                fontsize=10, va="top")

        input_lines = [
            f"Material: {material_label}",
            f"Section: {section}",
            f"Deflection limit: L/{deflection_limit}",
            f"E: {p['E']:,.0f} ksi",
            f"Ix: {p['Ix']:g} in4",
            f"Sx: {p['Sx']:g} in3",
            f"Allowable bending stress Fb: {p['Fb']:,.3f} ksi",
            f"Section weight: {p['weight']:g} lb/ft",
            f"Self-weight load: {p['weight']/1000:.6g} kip/ft",
        ]
        ax.text(0.02, 0.85, "DESIGN INPUTS",
                fontsize=11, fontweight="bold", va="top")
        ax.text(0.02, 0.81, "\n".join(input_lines),
                fontsize=9, va="top", linespacing=1.45)

        ax.text(0.40, 0.85, "APPLIED LOADS",
                fontsize=11, fontweight="bold", va="top")
        load_lines = []
        for load in state["loads"]:
            if load["kind"] == "point":
                load_lines.append(
                    f"Point load: {float(load['magnitude']):g} kips "
                    f"at {float(load['position']):g} ft")
            else:
                load_lines.append(
                    f"Uniform load: {float(load['magnitude']):g} kip/ft "
                    f"from {float(load['start']):g} to "
                    f"{float(load['end']):g} ft")
        if not load_lines:
            load_lines.append("None (beam self-weight only)")
        ax.text(0.40, 0.81, "\n".join(load_lines),
                fontsize=9, va="top", linespacing=1.45)

        ra = analysis.reactions["RA"]
        rb = analysis.reactions["RB"]
        ca = analysis.reactions["CA"]
        reaction_text = f"RA = {ra:.3f} kip upward"
        if support == "simply_supported":
            reaction_text += f"\nRB = {rb:.3f} kip upward"
        else:
            reaction_text += f"\nFixed-end moment CA = {ca:.3f} kip-ft"

        ax.text(0.72, 0.85, "REACTIONS",
                fontsize=11, fontweight="bold", va="top")
        ax.text(0.72, 0.81, reaction_text,
                fontsize=9, va="top", linespacing=1.45)

        beam_ax = fig.add_axes([0.07, 0.45, 0.86, 0.22])
        beam_ax.set_xlim(-1, span + 1)
        beam_ax.set_ylim(-2.5, 3.2)
        beam_ax.axis("off")
        beam_ax.plot([0, span], [0, 0], color="#172f3b",
                     linewidth=6, solid_capstyle="round")
        if support == "simply_supported":
            beam_ax.plot([0, -0.8, 0.8, 0], [0, -1.2, -1.2, 0],
                         color="#4567a7")
            beam_ax.plot([span, span-0.8, span+0.8, span],
                         [0, -1.2, -1.2, 0], color="#4567a7")
        else:
            beam_ax.fill_between([-1.0, 0.0], [-1.8, -1.8],
                                 [1.8, 1.8], color="#dce5e8")
        beam_ax.annotate(f"RA={ra:.2f} k",
                         xy=(0, -0.2), xytext=(0, -2),
                         ha="center",
                         arrowprops={"arrowstyle": "->", "color": "#16784b"})
        if support == "simply_supported":
            beam_ax.annotate(f"RB={rb:.2f} k",
                             xy=(span, -0.2), xytext=(span, -2),
                             ha="center",
                             arrowprops={"arrowstyle": "->",
                                         "color": "#16784b"})

        for load in state["loads"]:
            if load["kind"] == "point":
                position = float(load["position"])
                magnitude = float(load["magnitude"])
                direction = 1 if magnitude >= 0 else -1
                beam_ax.annotate(f"{magnitude:g} kip",
                                 xy=(position, 0),
                                 xytext=(position, 2.2 * direction),
                                 ha="center",
                                 arrowprops={
                                     "arrowstyle": "-|>" if direction > 0 else "<|-",
                                     "color": "#a45b2a",
                                     "mutation_scale": 14,
                                     "lw": 1.5,
                                 })
            else:
                start = max(0.0, float(load["start"]))
                end = min(span, float(load["end"]))
                if start < end:
                    magnitude = float(load["magnitude"])
                    y = 1.7 if magnitude >= 0 else -1.7
                    beam_ax.annotate(f"{magnitude:g} kip/ft",
                                     xy=((start + end)/2, y),
                                     xytext=((start + end)/2, y),
                                     ha="center", color="#4567a7")
                    arrow_count = max(2, min(12, int((end-start)/1.5)+1))
                    for arrow_index in range(arrow_count):
                        fraction = arrow_index/(arrow_count-1)
                        position = start+(end-start)*fraction
                        if magnitude >= 0:
                            beam_ax.annotate(
                                "", xy=(position, 0.02),
                                xytext=(position, 1.15),
                                arrowprops={"arrowstyle": "-|>",
                                            "color": "#4567a7",
                                            "mutation_scale": 12,
                                            "lw": 1.2})
                        else:
                            beam_ax.annotate(
                                "", xy=(position, 1.15),
                                xytext=(position, 0.02),
                                arrowprops={"arrowstyle": "-|>",
                                            "color": "#4567a7",
                                            "mutation_scale": 12,
                                            "lw": 1.2})
        beam_ax.text(span/2, -2.3, f"L = {span:g} ft",
                     ha="center", fontsize=9)

        summary_lines = [
            f"|V|max = {analysis.shear_max.value:.3f} kips at "
            f"{positions_text(analysis.shear_max.positions)}",
            f"|M|max = {analysis.moment_max.value:.3f} kip-ft at "
            f"{positions_text(analysis.moment_max.positions)}",
            f"|theta|max = {analysis.rotation_max.value:.6f} rad at "
            f"{positions_text(analysis.rotation_max.positions)}",
            f"|y|max = {abs(analysis.deflection_max.value):.3f} in at "
            f"{positions_text(analysis.deflection_max.positions)}",
        ]
        ax.text(0.02, 0.38, "OUTPUT SUMMARY",
                fontsize=11, fontweight="bold", va="top")
        ax.text(0.02, 0.34, "\n".join(summary_lines),
                fontsize=9, va="top", linespacing=1.45)

        bending_status = "PASS" if analysis.bending_ratio <= 1 else "FAIL"
        deflection_status = "PASS" if analysis.deflection_ratio <= 1 else "FAIL"
        check_lines = [
            f"Bending: fb = {analysis.bending_stress:.3f} ksi / "
            f"{analysis.bending_allowable:.3f} ksi "
            f"({analysis.bending_ratio*100:.1f}% - {bending_status})",
            f"Deflection: y_max = {abs(analysis.deflection_max.value):.3f} in / "
            f"{analysis.deflection_allowable:.3f} in "
            f"(L/{deflection_limit}, {analysis.deflection_ratio*100:.1f}% "
            f"- {deflection_status})",
        ]
        ax.text(0.40, 0.38, "DESIGN CHECKS",
                fontsize=11, fontweight="bold", va="top")
        ax.text(0.40, 0.34, "\n".join(check_lines),
                fontsize=9, va="top", linespacing=1.45)
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(4, 1, figsize=(11, 8.5), sharex=True)
        quantities = (
            ("V", "Shear", "kips", "#087e83", analysis.shear_max),
            ("M", "Moment", "kip-ft", "#087e83", analysis.moment_max),
            ("theta", "Rotation theta", "rad", "#7a4aa3",
             analysis.rotation_max),
            ("y", "Deflection y (downward negative)", "in", "#4567a7",
             analysis.deflection_max),
        )
        xs = [sample["x"] for sample in analysis.samples]
        for ax, (key, title, unit, color, maximum) in zip(axes, quantities):
            ys = [sample[key] for sample in analysis.samples]
            ax.plot(xs, ys, color=color, linewidth=1.5)
            ax.fill_between(xs, 0, ys, alpha=0.10, color=color)
            ax.axhline(0, color="#8aa0a7", linewidth=0.8)
            ax.set_title(title, loc="left", fontsize=10,
                         fontweight="bold", pad=30)
            ax.set_ylabel(unit, fontsize=8)
            ax.grid(True, axis="y", alpha=0.25)
            ax.set_xlim(0, span)
            for point_x, point_y in maximum.points:
                ax.plot(point_x, point_y, "o", color=color, markersize=4)
                ax.annotate(f"{point_y:+.6g} {unit}",
                            xy=(point_x, point_y),
                            xytext=(5, 8),
                            textcoords="offset points",
                            fontsize=7)
        axes[-1].set_xlabel("Position x (ft)", fontsize=9)
        fig.suptitle("Beam Designer - Calculated Diagrams",
                     fontsize=15, fontweight="bold")
        fig.subplots_adjust(top=0.93, bottom=0.08, left=0.10,
                            right=0.97, hspace=0.48)
        pdf.savefig(fig)
        plt.close(fig)
