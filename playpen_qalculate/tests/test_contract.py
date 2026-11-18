"""Portable checks: install the package, then unittest discover -s tests."""

import os
import tempfile
import unittest
from playpen_qalculate import CalculationError, QalculateEngine
from playpen_qalculate.engine import checked_expression


class ContractTests(unittest.TestCase):
    def test_reject_commands(self):
        for expression in ("load(1)", "export(2)", "save 1", "rand()", "1\nquit"):
            with (
                self.subTest(expression=expression),
                self.assertRaises(CalculationError),
            ):
                checked_expression(expression)

    @unittest.skipUnless(
        os.environ.get("QALCULATE_TEST_BINARY"), "optional real engine"
    )
    def test_real_units(self):
        with tempfile.TemporaryDirectory(
            dir=os.environ.get("QALCULATE_WORK_DIR")
        ) as work:
            engine = QalculateEngine(os.environ["QALCULATE_TEST_BINARY"], work_dir=work)
            result = engine.evaluate(
                "distance/duration", variables={"distance": "120 km", "duration": "2 h"}
            )
            self.assertEqual(result["result"], "60 km/h")
