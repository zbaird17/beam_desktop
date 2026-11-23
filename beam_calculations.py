"""Beam statics, diagrams, deflection, and design checks."""

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Sequence
import numpy as np


STEEL_SECTIONS = (
    {"name": "W8x10", "Ix": 30.8, "Sx": 7.81, "weight": 10.0},
    {"name": "W10x12", "Ix": 53.8, "Sx": 10.9, "weight": 12.0},
    {"name": "W12x26", "Ix": 204.0, "Sx": 33.4, "weight": 26.0},
    {"name": "W14x22", "Ix": 199.0, "Sx": 29.0, "weight": 22.0},
    {"name": "W16x26", "Ix": 301.0, "Sx": 38.4, "weight": 26.0},
    {"name": "W18x35", "Ix": 510.0, "Sx": 57.6, "weight": 35.0},
    {"name": "W21x44", "Ix": 843.0, "Sx": 81.6, "weight": 44.0},
    {"name": "W24x55", "Ix": 1350.0, "Sx": 114.0, "weight": 55.0},
)

LUMBER_SECTIONS = (
    {"name": "2x8", "Ix": 47.63, "Sx": 13.14, "weight": 2.638},
    {"name": "2x10", "Ix": 98.93, "Sx": 21.39, "weight": 3.366},
    {"name": "2x12", "Ix": 177.98, "Sx": 31.64, "weight": 4.102},
)

MATERIALS = {
    "steel": {"label": "Steel W-shapes", "E": 29000.0, "Fb": 30.0, "sections": STEEL_SECTIONS},
    "lumber": {"label": "Douglas Fir-Larch No. 2 lumber", "E": 1600.0, "Fb": 0.900, "sections": LUMBER_SECTIONS},
}


@dataclass(frozen=True)
class PointLoad:
    magnitude: float
    position: float


@dataclass(frozen=True)
class UniformLoad:
    magnitude: float
    start: float
    end: float


@dataclass(frozen=True)
class Extrema:
    value: float
    positions: tuple
    points: tuple


@dataclass(frozen=True)
class Analysis:
    support: str
    span: float
    material: str
    section: str
    properties: dict
    reactions: dict
    shear_max: Extrema
    moment_max: Extrema
    rotation_max: Extrema
    deflection_max: Extrema
    bending_stress: float
    bending_allowable: float
    bending_ratio: float
    deflection_allowable: float
    deflection_ratio: float
    passes: bool
    samples: tuple


def get_sections(material: str) -> tuple:
    return MATERIALS[material]["sections"]


def get_properties(material: str, section: str) -> dict:
    for item in get_sections(material):
        if item["name"] == section:
            result = dict(item)
            result["E"] = MATERIALS[material]["E"]
            result["Fb"] = MATERIALS[material]["Fb"]
            return result
    raise ValueError("The selected section is unavailable.")


def validate_inputs(span: float, support: str, deflection_limit: int,
                    point_loads: Sequence[PointLoad],
                    uniform_loads: Sequence[UniformLoad]) -> None:
    if not isfinite(span) or span < 4 or span > 40:
        raise ValueError("Span must be between 4 and 40 ft.")
    if support not in ("simply_supported", "cantilever"):
        raise ValueError("Support type is invalid.")
    if deflection_limit not in (240, 360):
        raise ValueError("Deflection limit must be L/240 or L/360.")
    for load in point_loads:
        if not isfinite(load.magnitude):
            raise ValueError("Point-load magnitude must be a finite number.")
        if not isfinite(load.position) or load.position < 0 or load.position > span:
            raise ValueError("Point-load position must be within the beam span.")
    for load in uniform_loads:
        if not isfinite(load.magnitude):
            raise ValueError("Uniform-load magnitude must be a finite number.")
        if not isfinite(load.start) or not isfinite(load.end):
            raise ValueError("Uniform-load positions must be finite numbers.")
        if load.end <= load.start:
            raise ValueError("Uniform-load end must be greater than its start.")
        if load.end <= 0 or load.start >= span:
            raise ValueError("Uniform load must overlap the beam span.")


def clipped_uniforms(uniform_loads: Iterable[UniformLoad], span: float) -> tuple:
    clipped = []
    for load in uniform_loads:
        start = max(0.0, load.start)
        end = min(span, load.end)
        if start < end:
            clipped.append(UniformLoad(load.magnitude, start, end))
    return tuple(clipped)


def reaction_values(support: str, span: float,
                   point_loads: Sequence[PointLoad],
                   uniform_loads: Sequence[UniformLoad]) -> dict:
    total_point = sum(load.magnitude for load in point_loads)
    point_moment = sum(load.magnitude * load.position for load in point_loads)
    total_uniform = sum(load.magnitude * (load.end - load.start) for load in uniform_loads)
    uniform_moment = sum(load.magnitude * (load.end ** 2 - load.start ** 2) / 2
                         for load in uniform_loads)
    total_load = total_point + total_uniform
    moment_about_left = point_moment + uniform_moment

    if support == "simply_supported":
        rb = moment_about_left / span
        ra = total_load - rb
        return {"RA": ra, "RB": rb, "CA": 0.0}
    ra = total_load
    ca = moment_about_left + sum(load.magnitude * load.position for load in point_loads) * 0
    # CA is positive counterclockwise in equilibrium: sum external moments about left = 0.
    ca = point_moment + uniform_moment
    return {"RA": ra, "RB": 0.0, "CA": ca}


def shear_at(x: float, support: str, span: float,
             point_loads: Sequence[PointLoad],
             uniform_loads: Sequence[UniformLoad],
             reactions: dict, right_side: bool = True) -> float:
    value = reactions["RA"]
    eps = 1e-9 if right_side else -1e-9
    for load in point_loads:
        if x + eps >= load.position:
            value -= load.magnitude
    for load in uniform_loads:
        overlap_end = min(max(x, 0.0), load.end)
        if overlap_end > load.start:
            value -= load.magnitude * (overlap_end - load.start)
    return value


def moment_at(x: float, support: str, span: float,
              point_loads: Sequence[PointLoad],
              uniform_loads: Sequence[UniformLoad],
              reactions: dict) -> float:
    value = reactions["RA"] * x
    for load in point_loads:
        value -= load.magnitude * max(0.0, x - load.position)
    for load in uniform_loads:
        start_distance = max(0.0, x - load.start)
        end_distance = max(0.0, x - load.end)
        value -= load.magnitude * (start_distance ** 2 - end_distance ** 2) / 2
    if support == "cantilever":
        value -= reactions["CA"]
    return value


def first_moment_integral(x: float, support: str, span: float,
                          point_loads: Sequence[PointLoad],
                          uniform_loads: Sequence[UniformLoad],
                          reactions: dict) -> float:
    point_area = sum(load.magnitude * max(0.0, x - load.position) ** 2 / 2
                     for load in point_loads)
    distributed_area = sum(
        load.magnitude * (
            max(0.0, x - load.start) ** 3
            - max(0.0, x - load.end) ** 3
        ) / 6
        for load in uniform_loads
    )
    value = reactions["RA"] * x ** 2 / 2 - point_area - distributed_area
    if support == "cantilever":
        value -= reactions["CA"] * x
    return value


def second_moment_integral(x: float, support: str, span: float,
                           point_loads: Sequence[PointLoad],
                           uniform_loads: Sequence[UniformLoad],
                           reactions: dict) -> float:
    point_area = sum(load.magnitude * max(0.0, x - load.position) ** 3 / 6
                     for load in point_loads)
    distributed_area = sum(
        load.magnitude * (
            max(0.0, x - load.start) ** 4
            - max(0.0, x - load.end) ** 4
        ) / 24
        for load in uniform_loads
    )
    value = reactions["RA"] * x ** 3 / 6 - point_area - distributed_area
    if support == "cantilever":
        value -= reactions["CA"] * x ** 2 / 2
    return value


def bisect_root(function, a: float, b: float) -> float:
    fa = function(a)
    fb = function(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        return (a + b) / 2
    lo, hi = a, b
    for _ in range(80):
        mid = (lo + hi) / 2
        fm = function(mid)
        if fm == 0 or hi - lo < 1e-9:
            return mid
        if fa * fm <= 0:
            hi = mid
            fb = fm
        else:
            lo = mid
            fa = fm
    return (lo + hi) / 2


def find_roots(positions: Sequence[float], function) -> tuple:
    roots = []
    previous_x = positions[0]
    previous_y = function(previous_x)
    for x in positions[1:]:
        y = function(x)
        if y == 0:
            roots.append(x)
        elif previous_y * y < 0:
            roots.append(bisect_root(function, previous_x, x))
        previous_x, previous_y = x, y
    return tuple(sorted(set(round(r, 9) for r in roots)))


def unique_positions(values: Iterable[float]) -> tuple:
    return tuple(sorted(set(round(value, 9) for value in values)))


def extrema_from_points(points: Sequence[tuple]) -> Extrema:
    if not points:
        return Extrema(0.0, (0.0,), ((0.0, 0.0),))
    maximum = max(abs(value) for _, value in points)
    selected = tuple((x, value) for x, value in points if abs(abs(value) - maximum) <= 1e-8)
    positions = tuple(sorted(set(x for x, _ in selected)))
    return Extrema(maximum, positions, selected)


def analyze_beam(support: str, span: float, material: str, section: str,
                 point_loads: Sequence[PointLoad],
                 uniform_loads: Sequence[UniformLoad],
                 deflection_limit: int = 360) -> Analysis:
    validate_inputs(span, support, deflection_limit, point_loads, uniform_loads)
    properties = get_properties(material, section)
    clipped = clipped_uniforms(uniform_loads, span)
    self_weight = UniformLoad(properties["weight"] / 1000.0, 0.0, span)
    all_uniform = tuple((*clipped, self_weight))
    reactions = reaction_values(support, span, tuple(point_loads), all_uniform)

    events = [0.0, span]
    events.extend(load.position for load in point_loads)
    for load in clipped:
        events.extend((load.start, load.end))
    events = list(unique_positions(events))

    base_positions = set(events)
    for index in range(len(events) - 1):
        start, end = events[index], events[index + 1]
        steps = max(1, int((end - start) + 0.999999))
        for step in range(steps + 1):
            base_positions.add(start + (end - start) * step / steps)

    shear_points = []
    moment_points = []
    for x in sorted(base_positions):
        for side in (True, False):
            if side or x not in (0.0, span):
                shear_points.append((x, shear_at(x, support, span, tuple(point_loads),
                                                  all_uniform, reactions, side)))
        moment_points.append((x, moment_at(x, support, span, tuple(point_loads),
                                           all_uniform, reactions)))

    shear_roots = ()
    moment_roots = tuple(
        find_roots(tuple(sorted(base_positions)),
                   lambda x: moment_at(x, support, span, tuple(point_loads),
                                       all_uniform, reactions))
    )
    shear_max_points = []
    moment_candidate_positions = unique_positions([0.0, span, *events,
                                                    *moment_roots])
    # Locate moment extrema by roots of shear on the fine plotting grid.
    for a, b in zip(sorted(base_positions), sorted(base_positions)[1:]):
        va = shear_at(a, support, span, tuple(point_loads), all_uniform, reactions, True)
        vb = shear_at(b, support, span, tuple(point_loads), all_uniform, reactions, True)
        if va * vb < 0:
            root = bisect_root(
                lambda x: shear_at(x, support, span, tuple(point_loads),
                                   all_uniform, reactions, True),
                a, b)
            moment_candidate_positions = unique_positions((*moment_candidate_positions, root))

    for x in sorted(base_positions):
        shear_left = shear_at(x, support, span, tuple(point_loads), all_uniform,
                              reactions, False)
        shear_right = shear_at(x, support, span, tuple(point_loads), all_uniform,
                               reactions, True)
        shear_max_points.append((x, shear_left))
        shear_max_points.append((x, shear_right))

    moment_candidate_positions = unique_positions((*moment_candidate_positions,
                                                    *moment_roots))
    moment_points = [(x, moment_at(x, support, span, tuple(point_loads),
                                   all_uniform, reactions))
                     for x in moment_candidate_positions]
    moment_max = extrema_from_points(moment_points)

    final_double_integral = second_moment_integral(
        span, support, span, tuple(point_loads), all_uniform, reactions)

    def deflection_basis(x: float) -> float:
        double_integral = second_moment_integral(
            x, support, span, tuple(point_loads), all_uniform, reactions)
        if support == "cantilever":
            return -double_integral
        return x * final_double_integral / span - double_integral

    def slope_basis(x: float) -> float:
        area = first_moment_integral(
            x, support, span, tuple(point_loads), all_uniform, reactions)
        if support == "cantilever":
            return -area
        return final_double_integral / span - area

    deflection_scale = 1728.0 / (properties["E"] * properties["Ix"])
    rotation_scale = deflection_scale / 12.0

    def deflection_at(x: float) -> float:
        return deflection_basis(x) * deflection_scale

    def rotation_at(x: float) -> float:
        return slope_basis(x) * rotation_scale

    fine_positions = tuple(sorted(base_positions))
    deflection_roots = find_roots(fine_positions, slope_basis)
    deflection_candidate_positions = unique_positions(
        (0.0, span, *deflection_roots))
    deflection_max = extrema_from_points(
        [(x, deflection_at(x)) for x in deflection_candidate_positions])

    rotation_candidate_positions = unique_positions(
        (0.0, span, *moment_roots))
    rotation_max = extrema_from_points(
        [(x, rotation_at(x)) for x in rotation_candidate_positions])
    shear_max = extrema_from_points(shear_max_points)

    plot_positions = unique_positions((*base_positions, *moment_roots,
                                       *deflection_roots, *moment_candidate_positions))
    samples = tuple({
        "x": x,
        "V": shear_at(x, support, span, tuple(point_loads), all_uniform,
                       reactions, True),
        "M": moment_at(x, support, span, tuple(point_loads), all_uniform, reactions),
        "theta": rotation_at(x),
        "y": deflection_at(x),
    } for x in plot_positions)

    bending_stress = 12.0 * moment_max.value / properties["Sx"]
    bending_allowable = properties["Fb"]
    bending_ratio = bending_stress / bending_allowable
    deflection_allowable = 12.0 * span / deflection_limit
    deflection_ratio = abs(deflection_max.value) / deflection_allowable

    result = Analysis(
        support=support,
        span=span,
        material=material,
        section=section,
        properties=properties,
        reactions=reactions,
        shear_max=shear_max,
        moment_max=moment_max,
        rotation_max=rotation_max,
        deflection_max=deflection_max,
        bending_stress=bending_stress,
        bending_allowable=bending_allowable,
        bending_ratio=bending_ratio,
        deflection_allowable=deflection_allowable,
        deflection_ratio=deflection_ratio,
        passes=bending_ratio <= 1.0 and deflection_ratio <= 1.0,
        samples=samples,
    )
    return result


def recommend_section(support: str, span: float, material: str,
                      point_loads: Sequence[PointLoad],
                      uniform_loads: Sequence[UniformLoad],
                      deflection_limit: int) -> dict:
    passing = []
    for section in get_sections(material):
        analysis = analyze_beam(
            support, span, material, section["name"],
            point_loads, uniform_loads, deflection_limit)
        if analysis.passes:
            passing.append(analysis)
    if not passing:
        return {"section": None, "analysis": None}
    if material == "steel":
        passing.sort(key=lambda item: (
            item.properties["weight"],
            -item.properties["Ix"],
        ))
    return {"section": passing[0].section, "analysis": passing[0]}


def evaluate_at(analysis: Analysis, x: float,
                point_loads: Sequence[PointLoad],
                uniform_loads: Sequence[UniformLoad]) -> dict:
    """Directly evaluate equations at x; do not interpolate plot samples."""
    clipped = clipped_uniforms(uniform_loads, analysis.span)
    self_weight = UniformLoad(
        analysis.properties["weight"] / 1000.0, 0.0, analysis.span)
    all_uniform = tuple((*clipped, self_weight))
    span = analysis.span
    support = analysis.support

    shear = shear_at(x, support, span, tuple(point_loads), all_uniform,
                     analysis.reactions, True)
    moment = moment_at(x, support, span, tuple(point_loads), all_uniform,
                       analysis.reactions)

    i1 = first_moment_integral(
        span, support, span, tuple(point_loads), all_uniform, analysis.reactions)
    i2 = second_moment_integral(
        x, support, span, tuple(point_loads), all_uniform, analysis.reactions)
    i2_span = second_moment_integral(
        span, support, span, tuple(point_loads), all_uniform, analysis.reactions)

    if support == "cantilever":
        value_basis = -i2
        slope_basis = -first_moment_integral(
            x, support, span, tuple(point_loads), all_uniform, analysis.reactions)
    else:
        value_basis = x * i2_span / span - i2
        slope_basis = i2_span / span - first_moment_integral(
            x, support, span, tuple(point_loads), all_uniform, analysis.reactions)

    deflection_scale = 1728.0 / (
        analysis.properties["E"] * analysis.properties["Ix"])
    return {
        "x": x,
        "V": shear,
        "M": moment,
        "theta": slope_basis * deflection_scale / 12.0,
        "y": value_basis * deflection_scale,
    }
