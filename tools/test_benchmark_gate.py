"""Synthetic parser tests; these are not Jenkins execution evidence."""

import unittest

from benchmark_gate import evaluate


class GateTest(unittest.TestCase):
    baseline = "accepted: 10000/10000\nthroughput: 1003 events/sec\np50 latency: 56.3 ms\np95 latency: 106.6 ms\n"

    def test_baseline_and_boundaries(self):
        self.assertTrue(evaluate(self.baseline, 750, 150)["passed"])
        self.assertTrue(evaluate(self.baseline, 1003, 106.6)["passed"])

    def test_regressions(self):
        for old, new in [("1003", "749"), ("106.6", "150.1"),
                         ("10000/10000", "9999/10000"), ("10000/10000", "9999/9999")]:
            with self.subTest(new=new):
                self.assertFalse(evaluate(self.baseline.replace(old, new), 750, 150)["passed"])

    def test_forced_failure(self):
        self.assertFalse(evaluate(self.baseline, 1e12, 150)["passed"])

    def test_missing_duplicate_and_invalid_metrics(self):
        for text in ["", self.baseline * 2, self.baseline.replace("106.6", "nan"),
                     self.baseline.replace("1003", "9" * 400)]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    evaluate(text, 750, 150)


if __name__ == "__main__":
    unittest.main()
