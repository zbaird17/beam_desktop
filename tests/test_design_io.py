import json
import tempfile
import unittest
from pathlib import Path
from beam_ui import format_chart_crosshair_value

from design_io import (
    DesignFileError,
    load_design,
    save_design,
)


class DesignIoTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "support": "simply_supported",
            "span": 20,
            "material": "steel",
            "section": "W12x26",
            "deflection_limit": 360,
            "loads": [
                {"id": 1, "kind": "uniform", "magnitude": 1,
                 "start": 0, "end": 20},
                {"id": 2, "kind": "point", "magnitude": -2,
                 "position": 5.2},
            ],
        }

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.beam.json"
            save_design(path, self.state)
            loaded = load_design(path)

        self.assertEqual(loaded["format"], "beam-designer")
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(loaded["support"], "simply_supported")
        self.assertEqual(loaded["span"], 20)
        self.assertEqual(loaded["material"], "steel")
        self.assertEqual(loaded["section"], "W12x26")
        self.assertEqual(loaded["deflection_limit"], 360)
        self.assertEqual(len(loaded["loads"]), 2)
        self.assertEqual(loaded["loads"][1]["position"], 5.25)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.beam.json"
            path.write_text("{bad json", encoding="utf-8")
            with self.assertRaises(DesignFileError):
                load_design(path)

    def test_unknown_section(self):
        state = dict(self.state)
        state["section"] = "W999x999"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.beam.json"
            with self.assertRaises(DesignFileError):
                save_design(path, state)

    def test_invalid_uniform_load_outside_span(self):
        state = dict(self.state)
        state["loads"] = [
            {"id": 1, "kind": "uniform", "magnitude": 1,
             "start": 21, "end": 22},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.beam.json"
            with self.assertRaises(DesignFileError):
                save_design(path, state)

    def test_unsupported_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "version.beam.json"
            design = {
                "format": "beam-designer",
                "version": 999,
                "support": "simply_supported",
                "span": 20,
                "material": "steel",
                "section": "W12x26",
                "deflection_limit": 360,
                "loads": [],
            }
            path.write_text(json.dumps(design), encoding="utf-8")
            with self.assertRaises(DesignFileError):
                load_design(path)


class ChartCrosshairTests(unittest.TestCase):
    def test_units_are_included(self):
        self.assertEqual(format_chart_crosshair_value("V", 10.25), "+10.250 kips")
        self.assertEqual(format_chart_crosshair_value("M", -51.3), "-51.300 kip-ft")
        self.assertEqual(format_chart_crosshair_value("theta", -0.008324544),
                         "-0.008325 rad")
        self.assertEqual(format_chart_crosshair_value("y", -0.624341),
                         "-0.624 in")


if __name__ == "__main__":
    unittest.main()
