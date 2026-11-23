import csv
from pathlib import Path

from beam_calculations import (
    PointLoad,
    UniformLoad,
    analyze_beam,
    evaluate_at,
)


CSV_HEADERS = (
    "x (ft)",
    "V (kips)",
    "M (kip-ft)",
    "theta (rad)",
    "deflection y (in)",
)


def export_positions(span):
    if span <= 0:
        raise ValueError("Span must be greater than zero.")
    count = int(round(span * 4))
    positions = [index / 4 for index in range(count + 1)]
    if abs(positions[-1] - span) > 1e-9:
        positions.append(span)
    return sorted(set(round(position, 9) for position in positions))


def export_csv(path, state):
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
        support,
        span,
        material,
        section,
        point_loads,
        uniform_loads,
        deflection_limit,
    )

    target = Path(path)
    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADERS)
        for position in export_positions(span):
            values = evaluate_at(
                analysis,
                position,
                point_loads,
                uniform_loads,
            )
            writer.writerow([
                f"{position:.4f}",
                f"{values['V']:.9f}",
                f"{values['M']:.9f}",
                f"{values['theta']:.12f}",
                f"{values['y']:.9f}",
            ])
