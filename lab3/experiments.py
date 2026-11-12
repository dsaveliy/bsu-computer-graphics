"""Проверка корректности и замеры времени для отчёта: печатает все таблицы, на которые опираются выводы,
и сохраняет замеры в report/timings.json (по ним строится график).

Запуск: python experiments.py  (около минуты)
"""
import json
import math
import platform
import random
import sys
import time
from pathlib import Path

import raster as R

LINES = ["step", "dda", "bresenham", "castle"]


# --- эталоны для сравнения ------------------------------------------------------------------

def only_output(x0, y0, x1, y1):
    """Тот же цикл записи L + 1 пикселей, но без вычислений: сколько стоит сам Python."""
    n = max(abs(x1 - x0), abs(y1 - y0))
    points = []
    for i in range(n + 1):
        points.append((x0, y0))
    return points


def naive_circle(xc, yc, r):
    """Окружность «в лоб»: для x = 0 … R/√2 вычисляется y = round(√(R² − x²)), плюс симметрия."""
    points = []
    for x in range(0, math.floor(r / math.sqrt(2)) + 1):
        y = math.floor(math.sqrt(r * r - x * x) + 0.5)
        points += [(xc + x, yc + y), (xc + y, yc + x), (xc + y, yc - x), (xc + x, yc - y),
                   (xc - x, yc - y), (xc - y, yc - x), (xc - y, yc + x), (xc - x, yc + y)]
    return list(dict.fromkeys(points))


# --- корректность отрезков --------------------------------------------------------------------

def deviation2(p, x0, y0, x1, y1):
    """Удвоенное отклонение центра пикселя от прямой вдоль второстепенной оси, умноженное на длину
    по главной оси (целое число): пиксель допустим, если оно ≤ L, и это «ничья», если ровно L."""
    dx, dy = x1 - x0, y1 - y0
    x, y = p
    if abs(dx) >= abs(dy):
        return abs(2 * (y - y0) * dx - 2 * dy * (x - x0)), abs(dx)
    return abs(2 * (x - x0) * dy - 2 * dx * (y - y0)), abs(dy)


def check_line(points, x0, y0, x1, y1):
    """Список нарушений: концы, число пикселей, 8-связность без повторов, отклонение ≤ 1/2."""
    errors = []
    n = max(abs(x1 - x0), abs(y1 - y0))
    if points[0] != (x0, y0) or points[-1] != (x1, y1):
        errors.append("концы")
    if len(points) != n + 1:
        errors.append("число пикселей")
    major = 0 if abs(x1 - x0) >= abs(y1 - y0) else 1
    for a, b in zip(points, points[1:]):
        if abs(b[major] - a[major]) != 1 or abs(b[1 - major] - a[1 - major]) > 1:
            errors.append("связность")
            break
    for p in points:
        d, L = deviation2(p, x0, y0, x1, y1)
        if d > L:
            errors.append("отклонение > 1/2")
            break
    return errors


def lines_correctness():
    print("1. Отрезки: все концы в квадрате ±25 от (3; −2) — 2601 отрезок, все октанты")
    x0, y0 = 3, -2
    segs = [(x0, y0, x0 + i, y0 + j) for i in range(-25, 26) for j in range(-25, 26)]
    ties_total = sum(1 for s in segs for p in R.bresenham_line(*s)
                     if deviation2(p, *s)[0] == deviation2(p, *s)[1] and s[0:2] != s[2:4])
    print(f"   пикселей-«ничьих» (прямая ровно посередине между двумя центрами): {ties_total}")
    result = {}
    for key in LINES + ["wu"]:
        func = R.ALGORITHMS[key][2]
        bad = diff = rev = 0
        diff_pixels = 0
        for s in segs:
            pts = func(*s)
            if key == "wu":
                continue
            if check_line(pts, *s):
                bad += 1
            ref = R.bresenham_line(*s)
            if pts != ref:
                diff += 1
                d = set(pts) ^ set(ref)
                diff_pixels += len(d) // 2
                # все отличия обязаны быть в «ничьих»
                assert all(deviation2(p, *s)[0] == deviation2(p, *s)[1] for p in d), (key, s)
            back = func(s[2], s[3], s[0], s[1])
            if set(back) != set(pts):
                rev += 1
        if key == "wu":
            continue
        result[key] = (bad, diff, diff_pixels, rev)
        print(f"   {R.ALGORITHMS[key][0]:22s} нарушений {bad}, отличий от Брезенхема: {diff} отрезков "
              f"({diff_pixels} пикс., все в «ничьих»), A→B ≠ B→A: {rev}")
    return result


def long_lines_dda():
    """Накапливается ли ошибка ЦДА на длинных отрезках."""
    rng = random.Random(1)
    worst = 0
    bad = 0
    for _ in range(300):
        s = [rng.randint(-5000, 5000) for _ in range(4)]
        pts = R.dda(*s)
        for p in pts:
            d, L = deviation2(p, *s)
            worst = max(worst, d / (2 * L) if L else 0)
        bad += bool(check_line(pts, *s))
    print(f"   ЦДА на 300 случайных отрезках длиной до 10 000: нарушений {bad}, "
          f"наибольшее отклонение {worst:.6f}")


def wu_correctness():
    rng = random.Random(2)
    worst_sum = worst_centroid = 0
    for _ in range(3000):
        x0, y0, x1, y1 = [rng.randint(-40, 40) for _ in range(4)]
        if (x0, y0) == (x1, y1):
            continue
        steep = abs(y1 - y0) > abs(x1 - x0)
        cols = {}
        for x, y, c in R.wu_line(x0, y0, x1, y1):
            u, v = (y, x) if steep else (x, y)
            cols.setdefault(u, []).append((v, c))
        a0, b0, a1, b1 = (y0, x0, y1, x1) if steep else (x0, y0, x1, y1)
        for u, items in cols.items():
            worst_sum = max(worst_sum, abs(sum(c for _, c in items) - 1))
            exact = b0 + (b1 - b0) * (u - a0) / (a1 - a0)
            worst_centroid = max(worst_centroid, abs(sum(v * c for v, c in items) - exact))
    print(f"3. Ву, 3000 случайных отрезков: |Σ яркостей в столбце − 1| ≤ {worst_sum:.1e}, "
          f"|центр тяжести столбца − точный y| ≤ {worst_centroid:.1e}")


def circle_correctness():
    worst, holes, diff_naive, total = 0.0, 0, 0, 0
    for r in range(0, 301):
        pts = R.bresenham_circle(0, 0, r)
        worst = max(worst, max(abs(math.hypot(x, y) - r) for x, y in pts))
        s = set(pts)
        # у каждого пикселя есть хотя бы 2 соседа из окружности в 8-окрестности (замкнутость), при R ≥ 2
        if r >= 2:
            for x, y in pts:
                nb = sum((x + i, y + j) in s for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j)
                holes += nb < 2
        naive = set(naive_circle(0, 0, r))
        diff_naive += len(s ^ naive)
        total += len(s)
    print(f"2. Окружность, R = 0 … 300: наибольшее |√(x² + y²) − R| = {worst:.4f}, разрывов {holes}, "
          f"отличий от округления √(R² − x²): {diff_naive} пикс. из {total}")
    return worst


# --- время ---------------------------------------------------------------------------------------

def best_time(func, args_list, budget=0.04, repeats=5):
    """Среднее время одного вызова (усреднение по args_list), лучшая из repeats серий."""
    n = 1
    while True:
        t = time.perf_counter()
        for _ in range(n):
            for args in args_list:
                func(*args)
        dt = time.perf_counter() - t
        if dt >= budget:
            break
        n *= 2
    best = dt
    for _ in range(repeats - 1):
        t = time.perf_counter()
        for _ in range(n):
            for args in args_list:
                func(*args)
        best = min(best, time.perf_counter() - t)
    return best / n / len(args_list)


def directions(L, count=12, seed=3):
    """count случайных направлений, главная ось длиной ровно L."""
    rng = random.Random(seed + L)
    out = []
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        c, s = math.cos(a), math.sin(a)
        m = max(abs(c), abs(s))
        out.append((0, 0, round(L * c / m), round(L * s / m)))
    return out


def line_timings():
    print("\n4. Время построения отрезка, мкс на отрезок (в скобках — нс на пиксель); "
          "среднее по 12 направлениям, лучшая из 5 серий")
    funcs = {"empty": ("Только запись пикселей", only_output)}
    funcs.update({k: (R.ALGORITHMS[k][0], R.ALGORITHMS[k][2]) for k in LINES + ["wu"]})
    data = {}
    lengths = [10, 100, 1000, 10000]
    print(f"   {'':24s}" + "".join(f"{'L = ' + str(L):>20s}" for L in lengths))
    for key, (title, func) in funcs.items():
        row = []
        for L in lengths:
            sec = best_time(func, directions(L))
            row.append(sec)
        data[key] = row
        print(f"   {title:24s}" + "".join(f"{s * 1e6:11.2f} ({s / (L + 1) * 1e9:4.0f})" for s, L in zip(row, lengths)))
    return lengths, data


def castle_cases():
    print("\n5. Кастл–Питвей: время зависит от пары (a, b), а не только от длины; a = 10 000")
    out = []
    for b in (1, 2, 4000, 3999, 6180, 9999):
        sec = best_time(R.castle_pitteway, [(0, 0, 10000, b)])
        bres = best_time(R.bresenham_line, [(0, 0, 10000, b)])
        t = R.Trace()
        R.castle_pitteway_moves(10000, b, t)
        steps = len(t.notes) - 2
        out.append((b, math.gcd(10000, b), steps, sec, bres))
        print(f"   b = {b:5d}: НОД = {math.gcd(10000, b):5d}, шагов «Евклида» {steps:5d}, "
              f"{sec * 1e6:8.0f} мкс (Брезенхем {bres * 1e6:6.0f} мкс)")
    return out


def circle_timings():
    print("\n6. Время построения окружности, мкс (в скобках — нс на пиксель)")
    radii = [10, 100, 1000, 10000]
    data = {}
    for key, title, func in (("circle", "Брезенхем", R.bresenham_circle), ("naive", "через √(R² − x²)", naive_circle)):
        row = [best_time(func, [(0, 0, r)]) for r in radii]
        npx = [len(func(0, 0, r)) for r in radii]
        data[key] = row
        print(f"   {title:18s}" + "".join(f"  R = {r}: {s * 1e6:9.1f} ({s / n * 1e9:3.0f})"
                                         for r, s, n in zip(radii, row, npx)))
    data["pixels"] = [len(R.bresenham_circle(0, 0, r)) for r in radii]
    return radii, data


if __name__ == "__main__":
    print(f"Python {platform.python_version()}, {platform.machine()}, {platform.platform()}\n")
    lines_correctness()
    long_lines_dda()
    circle_correctness()
    wu_correctness()
    lengths, line_data = line_timings()
    cp = castle_cases()
    radii, circle_data = circle_timings()
    out = Path(__file__).with_name("report") / "timings.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"python": platform.python_version(), "lengths": lengths, "lines": line_data,
                               "radii": radii, "circles": circle_data, "castle": cp}, indent=1))
    print("\nЗамеры сохранены:", out)
