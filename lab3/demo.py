"""Общий пример приложения, отчёта и проверки для защиты лабораторной 3."""
from fractions import Fraction

import raster

SEGMENT = (0, 0, 18, -15)
LINE_KEYS = ("step", "dda", "bresenham", "castle")


def differences(args):
    """Строки (шаг, пиксели четырёх методов), где выбор пикселя различается."""
    results = [raster.ALGORITHMS[key][2](*args) for key in LINE_KEYS]
    return [(i, pixels) for i, pixels in enumerate(zip(*results)) if len(set(pixels)) > 1]


def comparison_rows(args=SEGMENT):
    return [[str(i)] + [raster.pt(*p) for p in pixels] for i, pixels in differences(args)]


EXPLANATIONS = {
    "step": "Каждый y считается заново: y = −5x/6. При x = 15 получается ровно −12,5; "
            "floor(y + 0,5) выбирает −12.",
    "dda": "К y прибавляется −5/6. При x = 15 накоплено −12.500000000000002: "
           "округление даёт −13. Это погрешность float на границе, а не другая прямая.",
    "bresenham": "Целая ошибка e₀ = 12; если e ≥ 0, y уменьшается. "
                 "Перед x = 3, 9, 15 возникает e = 0: выбирается нижний пиксель, к концу отрезка.",
    "castle": "Сначала строятся ходы (dddsdd)³: d = (+1; −1), s = (+1; 0). "
              "Пиксели совпадают с Брезенхемом, но нет пересчёта ошибки на каждом шаге.",
    "wu": "Вместо выбора одной клетки яркость делится между двумя. "
          "При x = 3, 9, 15 обе получают 0,5; при x = 1: (1; −1) — 5/6, (1; 0) — 1/6.",
    "circle": "Это отдельная задача: окружность R = 7. Строится 1/8 дуги, "
              "точки отражаются в 8 сторон. Выбор следующей точки определяется целой ошибкой d.",
}


def exact_y(x, args=SEGMENT):
    x0, y0, x1, y1 = args
    return Fraction(y0) + Fraction((y1 - y0) * (x - x0), x1 - x0)
