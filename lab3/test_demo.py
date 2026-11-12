"""Проверка фактов, используемых в демонстрации и отчёте: python -m unittest test_demo.py."""
import unittest

import demo
import raster as R
from experiments import check_line, deviation2


class DemoTests(unittest.TestCase):
    def test_visible_differences(self):
        self.assertEqual(demo.comparison_rows(), [
            ["3", "(3; −2)", "(3; −2)", "(3; −3)", "(3; −3)"],
            ["9", "(9; −7)", "(9; −7)", "(9; −8)", "(9; −8)"],
            ["15", "(15; −12)", "(15; −13)", "(15; −13)", "(15; −13)"],
        ])
        for _, pixels in demo.differences(demo.SEGMENT):
            for p in pixels:
                d, length = deviation2(p, *demo.SEGMENT)
                self.assertEqual(d, length, "Различие должно быть ровно в ничьей")

    def test_line_invariants_and_trace(self):
        for key in demo.LINE_KEYS:
            func = R.ALGORITHMS[key][2]
            t = R.Trace()
            points = func(*demo.SEGMENT, t)
            self.assertEqual(points, func(*demo.SEGMENT))
            self.assertEqual(check_line(points, *demo.SEGMENT), [])
            self.assertEqual(len(points), 19)
            self.assertEqual([pixels[0] for _, pixels in t.rows], points)

    def test_castle_same_raster_different_construction(self):
        self.assertEqual(R.castle_pitteway_moves(18, 15), "dddsdd" * 3)
        for dx in range(-25, 26):
            for dy in range(-25, 26):
                args = (3, -2, 3 + dx, -2 + dy)
                self.assertEqual(R.castle_pitteway(*args), R.bresenham_line(*args))

    def test_wu_weights_and_position(self):
        points = R.wu_line(*demo.SEGMENT)
        self.assertEqual(len(points), 34)
        for x in range(19):
            col = [(y, v) for px, y, v in points if px == x]
            self.assertAlmostEqual(sum(v for _, v in col), 1)
            self.assertAlmostEqual(sum(y * v for y, v in col), float(demo.exact_y(x)))
            self.assertTrue(all(0 < v <= 1 for _, v in col))
        self.assertEqual([(y, v) for x, y, v in points if x == 3], [(-3, .5), (-2, .5)])

    def test_circle(self):
        t = R.Trace()
        points = R.bresenham_circle(0, 0, 7, t)
        self.assertEqual(len(points), 40)
        self.assertEqual(len(t.rows), 6)
        self.assertEqual(len(set(points)), len(points))
        for x, y in points:
            self.assertIn((-x, y), points)
            self.assertIn((y, x), points)


if __name__ == "__main__":
    unittest.main()
