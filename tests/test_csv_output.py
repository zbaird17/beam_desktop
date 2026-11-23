import csv
import tempfile
import unittest
from pathlib import Path

from csv_output import CSV_HEADERS, export_csv, export_positions
from pdf_report import export_pdf


class CsvOutputTests(unittest.TestCase):
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
            ],
        }

    def test_positions_include_quarter_foot_grid_and_endpoint(self):
        positions = export_positions(20)
        self.assertEqual(positions[0], 0)
        self.assertEqual(positions[-1], 20)
        self.assertEqual(len(positions), 81)
        self.assertTrue(all(
            abs(round(position * 4) - position * 4) < 1e-9
            for position in positions
        ))

    def test_csv_headers_units_and_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "beam_output.csv"
            export_csv(path, self.state)
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(tuple(rows[0]), CSV_HEADERS)
        self.assertEqual(len(rows), 82)
        self.assertEqual(rows[1][0], "0.0000")
        self.assertEqual(rows[-1][0], "20.0000")
        self.assertEqual(len(rows[1]), 5)
        midpoint = float(rows[41][4])
        self.assertLess(midpoint, 0)
        self.assertAlmostEqual(abs(midpoint), 0.62434, places=3)

        end_shear = float(rows[-1][1])
        end_moment = float(rows[-1][2])
        end_y = float(rows[-1][4])
        self.assertAlmostEqual(end_shear, -10.26, places=6)
        self.assertAlmostEqual(end_moment, 0.0, places=6)
        self.assertLess(abs(end_y), 1e-7)


class PdfReportTests(unittest.TestCase):
    def test_pdf_report_creates_two_page_document(self):
        state = {
            "support": "simply_supported",
            "span": 20,
            "material": "steel",
            "section": "W12x26",
            "deflection_limit": 360,
            "loads": [
                {"id": 1, "kind": "uniform", "magnitude": 1,
                 "start": 0, "end": 20},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "beam_report.pdf"
            export_pdf(path, state)
            content = path.read_bytes()

        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 20_000)
        self.assertGreaterEqual(content.count(b"/Type /Page"), 2)


if __name__ == "__main__":
    unittest.main()
