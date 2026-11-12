"""Рисунки для отчёта (нужен matplotlib). Запуск: python report/figures.py (после experiments.py)"""
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.patches import Circle, Rectangle
import numpy as np

import raster as R
import demo

HERE = Path(__file__).parent
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman"], "font.size": 10})

COLORS = {"step": "#6f9be0", "dda": "#62b878", "bresenham": "#f0a73a",
          "circle": "#b08ae0", "castle": "#e07aa3", "wu": "#203a8f"}
IDEAL = "#d62728"


def blend(color, c):
    rgb = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return 1 + (rgb - 1) * c


def grid_ax(ax, x0, x1, y0, y1, pixels=(), color=COLORS["bresenham"], labels=None, wu=(),
            lines=(), circles=(), centers=True, step=1, marks=(), wu_text=True):
    """Фрагмент растра как в приложении: клетки — пиксели, серые линии — границы (полуцелые),
    точки — центры (целые), оси проходят через центры нулевых строки и столбца."""
    ax.set_xlim(x0 - 0.5, x1 + 0.5)
    ax.set_ylim(y0 - 0.5, y1 + 0.5)
    ax.set_aspect("equal")
    for x, y in pixels:
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, color=color, lw=0))
    for x, y, c in wu:
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, color=blend(COLORS["wu"], c), lw=0))
        if wu_text:
            ax.text(x, y - 0.22, f"{c:.2f}".replace(".", ","), ha="center", va="center", fontsize=7,
                    color="white" if c > 0.55 else "black")
    for i in range(x0, x1 + 2):
        ax.plot([i - 0.5] * 2, [y0 - 0.5, y1 + 0.5], color="#cfcfcf", lw=0.5, zorder=1)
    for j in range(y0, y1 + 2):
        ax.plot([x0 - 0.5, x1 + 0.5], [j - 0.5] * 2, color="#cfcfcf", lw=0.5, zorder=1)
    if centers:
        gx, gy = np.meshgrid(range(x0, x1 + 1), range(y0, y1 + 1))
        ax.scatter(gx, gy, s=1.5, color="#8c8c8c", zorder=2, lw=0)
    if y0 <= 0 <= y1:
        ax.plot([x0 - 0.5, x1 + 0.5], [0, 0], color="black", lw=0.8, zorder=3)
    if x0 <= 0 <= x1:
        ax.plot([0, 0], [y0 - 0.5, y1 + 0.5], color="black", lw=0.8, zorder=3)
    for (a, b, c, d) in lines:
        ax.plot([a, c], [b, d], color=IDEAL, lw=1.1, zorder=4)
        ax.scatter([a, c], [b, d], s=10, facecolors="none", edgecolors=IDEAL, lw=0.9, zorder=4)
    for (xc, yc, r) in circles:
        ax.add_patch(Circle((xc, yc), r, fill=False, color=IDEAL, lw=1.1, zorder=4))
    for (x, y), text in (labels or {}).items():
        ax.text(x - 0.44, y + 0.44, text, ha="left", va="top", fontsize=6.5, zorder=5)
    for x, y in marks:
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, fill=False, ec="black", lw=1.6, zorder=6))
    ax.set_xticks(range(math.ceil(x0 / step) * step, x1 + 1, step))
    ax.set_yticks(range(math.ceil(y0 / step) * step, y1 + 1, step))
    ax.tick_params(labelsize=7, length=2, pad=1)
    for s in ax.spines.values():
        s.set_color("#808080")
        s.set_linewidth(0.6)


def step_labels(func, *args):
    t = R.Trace()
    func(*args, t)
    labels = {}
    for values, pixels in t.rows:
        for p in pixels:
            labels.setdefault(p, values[0])
    return labels


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220)
    plt.close(fig)


# 1. Привязка координат к сетке
seg = (0, 0, 7, 3)
fig, ax = plt.subplots(figsize=(6.2, 3.3))
grid_ax(ax, -1, 9, -1, 4, R.bresenham_line(*seg), lines=[seg], labels=step_labels(R.bresenham_line, *seg),
        marks=[(3, 1)])
ax.annotate("пиксель (3; 1) — квадрат\n[2,5; 3,5] × [0,5; 1,5]", xy=(3.5, 1.3), xytext=(5.6, -0.55),
            fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.7), va="center")
ax.annotate("центр пикселя —\nцелая точка (8; 3)", xy=(8, 3), xytext=(6.6, 3.95), fontsize=8,
            arrowprops=dict(arrowstyle="->", lw=0.7), va="center", ha="right")
ax.annotate("граница — полуцелая\nкоордината x = −0,5", xy=(-0.5, 2.6), xytext=(0.3, 3.4), fontsize=8,
            arrowprops=dict(arrowstyle="->", lw=0.7), va="center")
fig.tight_layout(pad=0.3)
save(fig, "f1_grid")

# 2. Пошаговый алгоритм на крутом отрезке: шаг только по x и с выбором главной оси
steep = (0, 0, 3, 8)
only_x = [(x, R.rnd(8 / 3 * x)) for x in range(0, 4)]
fig, axes = plt.subplots(1, 2, figsize=(4.6, 4.2))
grid_ax(axes[0], -1, 4, -1, 9, only_x, color=COLORS["step"], lines=[steep])
axes[0].set_title("а) шаг только по x", fontsize=10)
grid_ax(axes[1], -1, 4, -1, 9, R.step_by_step(*steep), color=COLORS["step"], lines=[steep],
        labels=step_labels(R.step_by_step, *steep))
axes[1].set_title("б) шаг по главной оси y", fontsize=10)
fig.tight_layout(pad=0.4)
save(fig, "f2_steep")

# 3. Пример: окружность R = 7
fig, ax = plt.subplots(figsize=(4.4, 4.4))
grid_ax(ax, -9, 9, -9, 9, R.bresenham_circle(0, 0, 7), color=COLORS["circle"], circles=[(0, 0, 7)],
        labels=step_labels(R.bresenham_circle, 0, 0, 7), step=2)
fig.tight_layout(pad=0.3)
save(fig, "f3_circle")

# 4. Ву: пример с яркостями и сравнение с Брезенхемом в натуральную величину
fig = plt.figure(figsize=(6.2, 4.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25])
ax = fig.add_subplot(gs[0, :])
grid_ax(ax, -1, 9, -1, 4, wu=R.wu_line(*seg), lines=[seg])
ax.set_title("а) отрезок (0; 0)–(7; 3), в клетках — яркость", fontsize=10)
size = 41
img_b = np.ones((size, size))
img_w = np.ones((size, size))
c = size // 2
for k in range(16):
    a = 2 * math.pi * (k + 0.5) / 16
    end = (c + round(19 * math.cos(a)), c + round(19 * math.sin(a)))
    for x, y in R.bresenham_line(c, c, *end):
        img_b[size - 1 - y, x] = 0
    for x, y, v in R.wu_line(c, c, *end):
        img_w[size - 1 - y, x] = min(img_w[size - 1 - y, x], 1 - v)
for k, (img, title) in enumerate([(img_b, "б) Брезенхем"), (img_w, "в) Ву")]):
    ax = fig.add_subplot(gs[1, k])
    ax.imshow(img, cmap="gray", vmin=0, vmax=1, interpolation="nearest")
    ax.set_title(title, fontsize=10)
    ax.axis("off")
fig.tight_layout(pad=0.4)
save(fig, "f4_wu")

# 5. Корректность во всех октантах: пучок отрезков и окружности
fig, axes = plt.subplots(1, 2, figsize=(6.2, 3.2))
ends = [(9, 2), (9, 6), (6, 9), (2, 9), (-2, 9), (-6, 9), (-9, 6), (-9, 2),
        (-9, -2), (-9, -6), (-6, -9), (-2, -9), (2, -9), (6, -9), (9, -6), (9, -2)]
pix = {p for e in ends for p in R.bresenham_line(0, 0, *e)}
grid_ax(axes[0], -10, 10, -10, 10, pix, lines=[(0, 0, *e) for e in ends], step=5, centers=False)
axes[0].set_title("а) 16 отрезков, все октанты", fontsize=10)
pix = {p for r in (2, 5, 9) for p in R.bresenham_circle(0, 0, r)}
grid_ax(axes[1], -10, 10, -10, 10, pix, color=COLORS["circle"], circles=[(0, 0, r) for r in (2, 5, 9)],
        step=5, centers=False)
axes[1].set_title("б) окружности R = 2, 5, 9", fontsize=10)
fig.tight_layout(pad=0.4)
save(fig, "f5_octants")

# 6. «Ничья»: прямая проходит ровно посередине между центрами
tie = (0, 0, 4, -1)
fig, axes = plt.subplots(1, 3, figsize=(6.2, 1.9))
for ax, (pts, color, title, line) in zip(axes, [
        (R.step_by_step(*tie), COLORS["step"], "а) пошаговый и ЦДА", tie),
        (R.bresenham_line(*tie), COLORS["bresenham"], "б) Брезенхем A → B", tie),
        (R.bresenham_line(4, -1, 0, 0), COLORS["bresenham"], "в) Брезенхем B → A", (4, -1, 0, 0))]):
    grid_ax(ax, -1, 5, -2, 1, pts, color=color, lines=[line], marks=[(2, 0), (2, -1)])
    ax.set_title(title, fontsize=10)
fig.tight_layout(pad=0.4)
save(fig, "f6_tie")

# 7. Время: нс на пиксель от длины и Кастл–Питвей в зависимости от b
data = json.loads((HERE / "timings.json").read_text())
L = np.array(data["lengths"])
fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.9))
ax = axes[0]
for key, title, style in [("empty", "только запись", dict(color="0.55", ls="--")),
                          ("step", "пошаговый", dict(color=COLORS["step"])),
                          ("dda", "ЦДА", dict(color=COLORS["dda"])),
                          ("bresenham", "Брезенхем", dict(color=COLORS["bresenham"])),
                          ("castle", "Кастл–Питвей", dict(color=COLORS["castle"])),
                          ("wu", "Ву (на столбец)", dict(color=COLORS["wu"]))]:
    ax.plot(L, np.array(data["lines"][key]) / (L + 1) * 1e9, marker="o", ms=3, lw=1.2, label=title, **style)
ax.set_xscale("log")
ax.set_xlabel("длина отрезка L, пикселей")
ax.set_ylabel("время на пиксель, нс")
ax.set_ylim(0, None)
ax.grid(alpha=0.3)
ax.legend(fontsize=7, loc="upper left", ncol=2)
ax.set_title("а) отрезки", fontsize=10)


def best(func, args, n=3):
    out = []
    for _ in range(n):
        t = time.perf_counter()
        func(*args)
        out.append(time.perf_counter() - t)
    return min(out)


ax = axes[1]
a = 1000
bs = list(range(1, a, 3))
ax.plot(bs, [best(R.castle_pitteway, (0, 0, a, b)) * 1e6 for b in bs], ".", ms=2.5,
        color=COLORS["castle"], label="Кастл–Питвей")
ax.plot(bs, [best(R.bresenham_line, (0, 0, a, b)) * 1e6 for b in bs], ".", ms=2.5,
        color=COLORS["bresenham"], label="Брезенхем")
ax.set_yscale("log")
ax.set_yticks([50, 100, 200, 500])
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
ax.set_xlabel(f"b (отрезок (0; 0)–({a}; b))")
ax.set_ylabel("время, мкс")
ax.grid(alpha=0.3)
ax.legend(fontsize=7, markerscale=3)
ax.set_title("б) зависимость от наклона", fontsize=10)
fig.tight_layout(pad=0.4)
save(fig, "f7_time")
# 8. Один наглядный пример для последовательного переключения методов.
fig, axes = plt.subplots(2, 3, figsize=(7.5, 7.2))
marks = [(x, y) for _, pixels in demo.differences(demo.SEGMENT) for x, y in set(pixels)]
for ax, key in zip(axes.flat, ("step", "dda", "bresenham", "castle", "wu", "circle")):
    title, kind, func = R.ALGORITHMS[key]
    if kind == "circle":
        grid_ax(ax, -8, 8, -8, 8, func(0, 0, 7), color=COLORS["step"],
                circles=[(0, 0, 7)], step=4, centers=False)
    else:
        points = func(*demo.SEGMENT)
        grid_ax(ax, -1, 19, -16, 1, pixels=points if key != "wu" else (),
                wu=points if key == "wu" else (), color=COLORS["step"],
                lines=[demo.SEGMENT], marks=marks, step=3, wu_text=False, centers=False)
    ax.set_title(title, fontsize=10)
fig.tight_layout(pad=0.6)
save(fig, "f8_demo")
print("Рисунки:", OUT)
