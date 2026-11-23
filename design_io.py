import json
import math
from pathlib import Path


FORMAT_VERSION = 1
SECTION_NAMES = {
    "steel": ("W8x10", "W10x12", "W12x26", "W14x22",
              "W16x26", "W18x35", "W21x44", "W24x55"),
    "lumber": ("2x8", "2x10", "2x12"),
}


class DesignFileError(ValueError):
    pass


def design_from_state(state):
    loads = []
    for load in state["loads"]:
        if load["kind"] == "point":
            loads.append({
                "kind": "point",
                "magnitude": float(load["magnitude"]),
                "position": float(load["position"]),
            })
        elif load["kind"] == "uniform":
            loads.append({
                "kind": "uniform",
                "magnitude": float(load["magnitude"]),
                "start": float(load["start"]),
                "end": float(load["end"]),
            })
    return {
        "format": "beam-designer",
        "version": FORMAT_VERSION,
        "support": state["support"],
        "span": float(state["span"]),
        "material": state["material"],
        "section": state["section"],
        "deflection_limit": int(state["deflection_limit"]),
        "loads": loads,
    }


def validate_design(design):
    if not isinstance(design, dict):
        raise DesignFileError("The design file must contain a JSON object.")
    if design.get("format") != "beam-designer":
        raise DesignFileError("The file is not a Beam Designer design.")
    if design.get("version") != FORMAT_VERSION:
        raise DesignFileError(
            f"Unsupported Beam Designer file version: {design.get('version')!r}.")

    support = design.get("support")
    if support not in ("simply_supported", "cantilever"):
        raise DesignFileError("Support type is invalid.")

    span = design.get("span")
    if not isinstance(span, (int, float)) or isinstance(span, bool):
        raise DesignFileError("Span must be a number.")
    span = float(span)
    if not math.isfinite(span) or not 4 <= span <= 40:
        raise DesignFileError("Span must be between 4 and 40 ft.")

    material = design.get("material")
    if material not in SECTION_NAMES:
        raise DesignFileError("Material is invalid.")
    section = design.get("section")
    if section not in SECTION_NAMES[material]:
        raise DesignFileError("Section is not available for the selected material.")

    deflection_limit = design.get("deflection_limit")
    if deflection_limit not in (240, 360):
        raise DesignFileError("Deflection limit must be 240 or 360.")

    loads = design.get("loads")
    if not isinstance(loads, list):
        raise DesignFileError("Loads must be a JSON list.")

    normalized = []
    for index, load in enumerate(loads, start=1):
        if not isinstance(load, dict):
            raise DesignFileError(f"Load {index} must be a JSON object.")
        kind = load.get("kind")
        magnitude = load.get("magnitude")
        if not isinstance(magnitude, (int, float)) or isinstance(magnitude, bool):
            raise DesignFileError(f"Load {index} magnitude must be a number.")
        magnitude = float(magnitude)
        if not math.isfinite(magnitude):
            raise DesignFileError(f"Load {index} magnitude must be finite.")

        if kind == "point":
            position = load.get("position")
            if not isinstance(position, (int, float)) or isinstance(position, bool):
                raise DesignFileError(f"Point load {index} position must be a number.")
            position = float(position)
            if not math.isfinite(position) or not 0 <= position <= span:
                raise DesignFileError(
                    f"Point load {index} position must be within the beam span.")
            normalized.append({
                "kind": "point",
                "magnitude": magnitude,
                "position": round(position * 4) / 4,
            })
        elif kind == "uniform":
            start = load.get("start")
            end = load.get("end")
            if (not isinstance(start, (int, float)) or isinstance(start, bool)
                    or not isinstance(end, (int, float)) or isinstance(end, bool)):
                raise DesignFileError(
                    f"Uniform load {index} start and end positions must be numbers.")
            start, end = float(start), float(end)
            if not math.isfinite(start) or not math.isfinite(end):
                raise DesignFileError(
                    f"Uniform load {index} positions must be finite.")
            if end <= start:
                raise DesignFileError(
                    f"Uniform load {index} end must be greater than its start.")
            if end <= 0 or start >= span:
                raise DesignFileError(
                    f"Uniform load {index} must overlap the beam span.")
            normalized.append({
                "kind": "uniform",
                "magnitude": magnitude,
                "start": start,
                "end": end,
            })
        else:
            raise DesignFileError(f"Load {index} type is invalid.")

    return {
        "format": "beam-designer",
        "version": FORMAT_VERSION,
        "support": support,
        "span": span,
        "material": material,
        "section": section,
        "deflection_limit": int(deflection_limit),
        "loads": normalized,
    }


def save_design(path, state):
    design = validate_design(design_from_state(state))
    target = Path(path)
    with target.open("w", encoding="utf-8") as file:
        json.dump(design, file, indent=2, ensure_ascii=False)
        file.write("\n")


def load_design(path):
    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as file:
            design = json.load(file)
    except json.JSONDecodeError as exc:
        raise DesignFileError(
            f"The file contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}.") from exc
    except OSError as exc:
        raise DesignFileError(f"The design file could not be read: {exc}.") from exc
    return validate_design(design)
