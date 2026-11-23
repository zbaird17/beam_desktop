import unittest

from beam_calculations import (
    PointLoad,
    UniformLoad,
    analyze_beam,
)


class BeamCalculationTests(unittest.TestCase):
    def assert_close(self, actual, expected, tol=0.01):
        self.assertTrue(abs(actual - expected) <= tol,
                        f"{actual} != {expected} within {tol}")

    def test_uniform_full_span_simply_supported(self):
        a = analyze_beam(
            "simply_supported", 20, "steel", "W12x26",
            [], [UniformLoad(1.0, 0, 20)], 360)
        self.assert_close(a.reactions["RA"], 10.26)
        self.assert_close(a.reactions["RB"], 10.26)
        self.assert_close(a.shear_max.value, 10.26)
        self.assert_close(a.moment_max.value, 51.30)
        self.assert_close(a.bending_stress, 18.43)
        self.assert_close(a.deflection_max.value, 0.624)
        self.assert_close(a.rotation_max.value, 0.008325)
        self.assertTrue(a.passes)

    def test_point_load_at_five_feet(self):
        a = analyze_beam(
            "simply_supported", 20, "steel", "W12x26",
            [PointLoad(10.0, 5.0)], [], 360)
        self.assert_close(a.reactions["RA"], 7.76)
        self.assert_close(a.reactions["RB"], 2.76)
        self.assert_close(a.moment_max.value, 38.47)
        self.assert_close(a.bending_stress, 13.82)
        self.assert_close(a.deflection_max.value, 0.356, 0.02)

    def test_cantilever_point_load(self):
        a = analyze_beam(
            "cantilever", 10, "steel", "W12x26",
            [PointLoad(5.0, 10.0)], [], 360)
        self.assert_close(a.reactions["RA"], 5.26)
        self.assert_close(a.reactions["CA"], 51.30)
        self.assert_close(a.deflection_max.value, 0.496)
        self.assert_close(a.rotation_max.value, 0.006191)
        self.assertFalse(a.passes)

    def test_lumber_joist(self):
        a = analyze_beam(
            "simply_supported", 12, "lumber", "2x10",
            [], [UniformLoad(0.05, 0, 12)], 360)
        self.assert_close(a.reactions["RA"], 0.3202)
        self.assert_close(a.moment_max.value, 0.961)
        self.assert_close(a.bending_stress, 0.539)
        self.assert_close(a.deflection_max.value, 0.157)
        self.assertTrue(a.passes)

    def test_partial_uniform(self):
        a = analyze_beam(
            "simply_supported", 30, "steel", "W18x35",
            [], [UniformLoad(2.0, 0, 15)], 360)
        self.assert_close(a.reactions["RA"], 23.025)
        self.assert_close(a.reactions["RB"], 8.025)
        self.assert_close(a.moment_max.value, 130.258)
        self.assert_close(a.moment_max.positions[0], 11.314)

    def test_signed_deflection_and_rotation(self):
        a = analyze_beam(
            "simply_supported", 20, "steel", "W12x26",
            [], [UniformLoad(1.0, 0, 20)], 360)
        from beam_calculations import evaluate_at
        mid = evaluate_at(
            a, 10.0, (), (UniformLoad(1.0, 0, 20),))
        left = evaluate_at(
            a, 0.0, (), (UniformLoad(1.0, 0, 20),))
        right = evaluate_at(
            a, 20.0, (), (UniformLoad(1.0, 0, 20),))
        self.assertLess(mid["y"], 0)
        self.assert_close(abs(mid["y"]), 0.624)
        self.assertLess(left["theta"], 0)
        self.assertGreater(right["theta"], 0)

    def test_clipped_uniform_and_upward_load(self):
        a = analyze_beam(
            "simply_supported", 20, "steel", "W12x26",
            [PointLoad(-1.0, 5.0)],
            [UniformLoad(-0.5, -2.0, 5.0)], 360)
        self.assertTrue(a.reactions["RA"] == a.reactions["RA"])
        self.assertFalse(any(load for load in []))

    def test_invalid_uniform_order(self):
        with self.assertRaises(ValueError):
            analyze_beam(
                "simply_supported", 20, "steel", "W12x26", [],
                [UniformLoad(1.0, 5.0, 5.0)], 360)


if __name__ == "__main__":
    unittest.main()
