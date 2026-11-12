import math
import time
import tkinter as tk
from tkinter import ttk

import raster
import demo

BG = "#f0f0f0"
CANVAS_W, CANVAS_H = 720, 560
MARGIN_L, MARGIN_B = 46, 26          # поля под подписи осей слева и снизу
ZOOMS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80]  # точек экрана на пиксель
FIT_MAX = 56                         # «вписать» не увеличивает сильнее
TABLE_ROWS = 1000                    # больше строк таблица вычислений не показывает
TABLE_W = 340                        # ширина таблицы вычислений
LIMIT = 10000                        # предел координат и радиуса

COLORS = {"step": "#6f9be0", "dda": "#62b878", "bresenham": "#f0a73a",
          "circle": "#b08ae0", "castle": "#e07aa3", "wu": "#203a8f"}
PIN_COLORS = ("#ad4e16", "#8b3fa0", "#237148", "#a3275c")
IDEAL = "#d62728"
FONT = ("Helvetica", 9)
# цвет текста на холсте задаётся явно: в тёмной теме macOS Tk по умолчанию рисует его белым


def blend(color, c):
    """Цвет color с яркостью c ∈ [0, 1] поверх белого — так показывается пиксель алгоритма Ву."""
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255 + (v - 255) * c):02x}" for v in rgb)


def measure(func, args, budget=0.06):
    """Среднее время одного построения без рисования: серию из n запусков удваиваем, пока она
    не займёт budget/3 секунды, затем берём лучшую из трёх серий (меньше всего помех от ОС)."""
    n = 1
    while True:
        t = time.perf_counter()
        for _ in range(n):
            func(*args)
        dt = time.perf_counter() - t
        if dt >= budget / 3 or n >= 1 << 20:
            break
        n *= 2
    best = dt / n
    for _ in range(2):
        t = time.perf_counter()
        for _ in range(n):
            func(*args)
        best = min(best, (time.perf_counter() - t) / n)
    return best, n


def nice_step(cell, min_gap=32):
    """Шаг подписей по оси: 1, 2, 5, 10, 20, 50 … — чтобы подписи не налезали друг на друга."""
    for base in (1, 10, 100, 1000, 10000):
        for m in (1, 2, 5):
            if m * base * cell >= min_gap:
                return m * base
    return 100000


class GridView(tk.Canvas):
    """Растровая сетка. Пиксель (i, j) — квадрат со стороной cell точек экрана с центром
    в экранной точке (ox + i·cell, oy − j·cell); ось y направлена вверх, как в математике."""

    def __init__(self, master, on_hover, on_zoom):
        super().__init__(master, width=CANVAS_W, height=CANVAS_H, bg="white", highlightthickness=1,
                         highlightbackground="#808080", cursor="crosshair")
        self.on_hover, self.on_zoom = on_hover, on_zoom
        self.cell = 24
        self.ox, self.oy = MARGIN_L + 60, CANVAS_H - MARGIN_B - 60
        self.figures = []          # [{"key", "kind", "args", "points"}]
        self.labels = {}           # пиксель -> номер шага, пишется в углу клетки
        self.marked = []           # пиксели выбранной строки таблицы
        self.difference_pixels = []  # оба кандидата в спорных столбцах
        self.comparing = False
        self.show_ideal = True
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<MouseWheel>", lambda e: self.zoom_at(e.x, e.y, 1 if e.delta > 0 else -1))
        self.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, 1))       # колесо в Linux
        self.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, -1))
        self.bind("<ButtonPress-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Motion>", lambda e: self.on_hover(*self.to_world(e.x, e.y)))
        self.bind("<Leave>", lambda e: self.on_hover(None, None))

    # --- координаты ----------------------------------------------------------------------------

    def to_screen(self, x, y):
        return self.ox + x * self.cell, self.oy - y * self.cell

    def to_world(self, sx, sy):
        return (sx - self.ox) / self.cell, (self.oy - sy) / self.cell

    def plot_area(self):
        return MARGIN_L, 0, self.winfo_width(), self.winfo_height() - MARGIN_B

    def visible(self):
        """Диапазон номеров пикселей, хотя бы частично попадающих в окно."""
        l, t, r, b = self.plot_area()
        x0, y1 = self.to_world(l, t)
        x1, y0 = self.to_world(r, b)
        return math.floor(x0) - 1, math.floor(y0) - 1, math.ceil(x1) + 1, math.ceil(y1) + 1

    # --- масштаб и сдвиг ------------------------------------------------------------------------

    def set_cell(self, cell, sx=None, sy=None):
        """Новый масштаб; точка экрана (sx, sy) остаётся на месте (по умолчанию — центр окна)."""
        l, t, r, b = self.plot_area()
        sx = (l + r) / 2 if sx is None else sx
        sy = (t + b) / 2 if sy is None else sy
        wx, wy = self.to_world(sx, sy)
        self.cell = cell
        self.ox, self.oy = round(sx - wx * cell), round(sy + wy * cell)
        self.on_zoom(cell)
        self.redraw()

    def zoom_at(self, sx, sy, direction):
        i = ZOOMS.index(self.cell) + direction
        if 0 <= i < len(ZOOMS):
            self.set_cell(ZOOMS[i], sx, sy)

    def fit_cell(self, box):
        """Наибольший масштаб, при котором box = (xmin, ymin, xmax, ymax) и начало координат видны целиком."""
        xmin, ymin, xmax, ymax = min(box[0], 0), min(box[1], 0), max(box[2], 0), max(box[3], 0)
        l, t, r, b = self.plot_area()
        size = min((r - l) / (xmax - xmin + 3), (b - t) / (ymax - ymin + 3))
        return max([z for z in ZOOMS if z <= min(size, FIT_MAX)] or [ZOOMS[0]])

    def fit(self, box):
        """Показать box вместе с началом координат: оси всегда в кадре."""
        xmin, ymin, xmax, ymax = min(box[0], 0), min(box[1], 0), max(box[2], 0), max(box[3], 0)
        l, t, r, b = self.plot_area()
        self.cell = self.fit_cell(box)
        self.ox = round((l + r) / 2 - (xmin + xmax) / 2 * self.cell)
        self.oy = round((t + b) / 2 + (ymin + ymax) / 2 * self.cell)
        self.on_zoom(self.cell)
        self.redraw()

    def contains(self, box):
        x0, y0, x1, y1 = self.visible()
        return x0 + 1 <= box[0] and y0 + 1 <= box[1] and box[2] <= x1 - 1 and box[3] <= y1 - 1

    def center_on(self, x, y):
        l, t, r, b = self.plot_area()
        self.ox, self.oy = round((l + r) / 2 - x * self.cell), round((t + b) / 2 + y * self.cell)
        self.redraw()

    def _drag_start(self, e):
        self._drag_from = (e.x, e.y, self.ox, self.oy)

    def _drag(self, e):
        x, y, ox, oy = self._drag_from
        self.ox, self.oy = ox + e.x - x, oy + e.y - y
        self.redraw()

    # --- рисование ------------------------------------------------------------------------------

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        c = self.cell
        vx0, vy0, vx1, vy1 = self.visible()
        half = c / 2

        def square(x, y, **kw):
            sx, sy = self.to_screen(x, y)
            return self.create_rectangle(sx - half, sy - half, sx + half, sy + half, **kw)

        # 1. закрашенные пиксели
        for fig in self.figures:
            wu = fig["key"] == "wu"
            color = fig.get("color") or ("#6f9be0" if self.comparing and not wu else COLORS[fig["key"]])
            for p in fig["points"]:
                x, y = p[0], p[1]
                if vx0 <= x <= vx1 and vy0 <= y <= vy1:
                    fill = blend(color, p[2]) if wu else color
                    square(x, y, fill=fill, outline=fill if c < 6 else "")

        # Цветной ободок сохраняет закреплённый растр видимым даже там,
        # где его клетки полностью совпадают с текущей фигурой.
        if c >= 6:
            inset = half - min(2, c / 4)
            for fig in self.figures:
                if "color" not in fig:
                    continue
                for p in fig["points"]:
                    x, y = p[:2]
                    if vx0 <= x <= vx1 and vy0 <= y <= vy1:
                        sx, sy = self.to_screen(x, y)
                        color = blend(fig["color"], p[2]) if fig["key"] == "wu" else fig["color"]
                        self.create_rectangle(sx - inset, sy - inset, sx + inset, sy + inset,
                                              outline=color, width=2)

        # 2. сетка: линии на полуцелых координатах — это границы пикселей
        if c >= 6:
            for i in range(vx0, vx1 + 1):
                sx = self.ox + (i + 0.5) * c
                self.create_line(sx, 0, sx, h, fill="#d4d4d4")
            for j in range(vy0, vy1 + 1):
                sy = self.oy - (j + 0.5) * c
                self.create_line(0, sy, w, sy, fill="#d4d4d4")
        # центры пикселей — целочисленные точки
        if c >= 20:
            for i in range(vx0, vx1 + 1):
                for j in range(vy0, vy1 + 1):
                    sx, sy = self.to_screen(i, j)
                    self.create_oval(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5, fill="#8c8c8c", outline="")

        # 3. оси проходят через центры пикселей нулевой строки и нулевого столбца
        l, t, r, b = self.plot_area()
        if t <= self.oy <= b:
            self.create_line(l, self.oy, r - 2, self.oy, fill="#202020", width=1.5, arrow="last")
            self.create_text(r - 10, self.oy - 10, text="x", fill="black", font=("Helvetica", 11, "italic"))
        if l <= self.ox <= r:
            self.create_line(self.ox, b, self.ox, t + 2, fill="#202020", width=1.5, arrow="last")
            self.create_text(self.ox + 12, t + 10, text="y", fill="black", font=("Helvetica", 11, "italic"))

        # 4. идеальная фигура: отрезок между центрами концов или окружность
        if self.show_ideal:
            for fig in self.figures:
                if fig["kind"] == "line":
                    x0, y0, x1, y1 = fig["args"]
                    a, b_ = self.to_screen(x0, y0), self.to_screen(x1, y1)
                    self.create_line(*a, *b_, fill=IDEAL, width=1.5)
                    for sx, sy in (a, b_):
                        self.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, outline=IDEAL, width=1.5)
                else:
                    xc, yc, rad = fig["args"]
                    (sx0, sy0), (sx1, sy1) = self.to_screen(xc - rad, yc + rad), self.to_screen(xc + rad, yc - rad)
                    self.create_oval(sx0, sy0, sx1, sy1, outline=IDEAL, width=1.5)
                    sx, sy = self.to_screen(xc, yc)
                    self.create_line(sx - 4, sy, sx + 5, sy, fill=IDEAL)
                    self.create_line(sx, sy - 4, sx, sy + 5, fill=IDEAL)

        # 5. номера шагов и яркости Ву внутри клеток
        if self.figures and c >= 28:
            size = max(7, min(11, c // 5))
            last = self.figures[-1]
            if last["key"] == "wu" and c >= 34:
                for x, y, v in last["points"]:
                    if vx0 <= x <= vx1 and vy0 <= y <= vy1:
                        sx, sy = self.to_screen(x, y)
                        self.create_text(sx, sy + c * 0.22, text=f"{v:.2f}".replace(".", ","),
                                         fill="white" if v > 0.55 else "black", font=("Helvetica", size))
            elif last["key"] != "wu":
                for (x, y), label in self.labels.items():
                    if vx0 <= x <= vx1 and vy0 <= y <= vy1:
                        sx, sy = self.to_screen(x, y)
                        self.create_text(sx - half + 3, sy - half + 2, text=label, anchor="nw",
                                         fill="black", font=("Helvetica", size))

        # 6. пиксели выбранной строки таблицы
        for x, y in self.difference_pixels:
            square(x, y, outline="#333333", width=2, dash=(4, 3))
        for x, y in self.marked:
            square(x, y, outline="black", width=3)

        # 7. поля с подписями: номера пикселей = координаты их центров
        self.create_rectangle(0, 0, l, h, fill="white", outline="")
        self.create_rectangle(0, b, w, h, fill="white", outline="")
        self.create_line(l, 0, l, b, fill="#808080")
        self.create_line(l, b, w, b, fill="#808080")
        step = nice_step(c)
        for i in range(math.ceil(vx0 / step) * step, vx1 + 1, step):
            sx = self.ox + i * c
            if l <= sx <= w:
                self.create_line(sx, b, sx, b + 4, fill="#404040")
                self.create_text(sx, b + 5, text=str(i).replace("-", "−"), anchor="n", fill="black", font=FONT)
        for j in range(math.ceil(vy0 / step) * step, vy1 + 1, step):
            sy = self.oy - j * c
            if 0 <= sy <= b:
                self.create_line(l - 4, sy, l, sy, fill="#404040")
                self.create_text(l - 6, sy, text=str(j).replace("-", "−"), anchor="e", fill="black", font=FONT)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Лабораторная 3: базовые растровые алгоритмы")
        self.configure(bg=BG)
        self._setup_style()
        self.pinned, self.current = [], None   # закреплённые фигуры и текущая
        self.row_pixels = {}                   # строка таблицы -> пиксели этого шага

        self.alg = tk.StringVar(value="step")
        self.line = [tk.IntVar(value=v) for v in demo.SEGMENT]
        self.circle = [tk.IntVar(value=v) for v in (0, 0, 7)]
        self.ideal = tk.BooleanVar(value=True)
        self.compare = tk.BooleanVar(value=True)

        self._build_toolbar()
        self._build_controls()
        self.view = GridView(self, self.on_hover, self.on_zoom)
        self.view.grid(row=1, column=1, sticky="nsew", pady=6)
        self._build_trace_panel()
        self.status = ttk.Label(self, relief="sunken", padding=(6, 2))
        self.status.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self.update_idletasks()
        self.apply(fit=True)

    # --- действия ------------------------------------------------------------------------------

    def apply(self, *_, fit=False):
        """Построить текущую фигуру выбранным алгоритмом, замерить время и показать вычисления."""
        key = self.alg.get()
        title, kind, func = raster.ALGORITHMS[key]
        self._update_controls()
        try:
            args = tuple(v.get() for v in (self.line if kind == "line" else self.circle))
        except tk.TclError:
            self.status.configure(text="В поле координаты не целое число")
            return
        if any(abs(v) > LIMIT for v in args) or (kind == "circle" and args[2] < 0):
            self.status.configure(text=f"Координаты и радиус — целые от −{LIMIT} до {LIMIT}, R ≥ 0")
            return

        trace = raster.Trace()
        points = func(*args, trace)
        seconds, runs = measure(func, args)
        self.current = {"key": key, "kind": kind, "args": args, "points": points}
        self.view.figures = self.pinned + [self.current]
        self.view.marked = []
        self._show_trace(trace)
        self._show_comparison(key, kind, args)
        self.view.labels = {}
        if key != "wu":
            for values, pixels in trace.rows[:TABLE_ROWS]:
                for p in pixels:
                    self.view.labels.setdefault(p, values[0])

        n = len(points)
        self.time_info.configure(
            text=f"{title}: {n} пикс. за {raster.num(seconds * 1e6, 1)} мкс, "
                 f"{seconds / n * 1e9:.0f} нс на пиксель (среднее по {runs} запускам, без рисования)")
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        box = (min(xs), min(ys), max(xs), max(ys))
        # масштаб подстраивается, если фигура не влезает или её можно показать вдвое крупнее
        if fit or not self.view.contains(box) or self.view.fit_cell(box) >= 2 * self.view.cell:
            self.view.fit(box)
        else:
            self.view.redraw()

    def on_pin(self):
        if self.current is not None:
            self.pinned.append({**self.current, "color": PIN_COLORS[len(self.pinned) % len(PIN_COLORS)]})
            self.view.figures = self.pinned + [self.current]
            self.view.redraw()
            self.status.configure(text=f"Закреплено фигур: {len(self.pinned)}")

    def load_demo(self):
        self.pinned = []
        for var, value in zip(self.line, demo.SEGMENT):
            var.set(value)
        for var, value in zip(self.circle, (0, 0, 7)):
            var.set(value)
        self.compare.set(True)
        self.alg.set("step")
        self.apply(fit=True)

    def _show_comparison(self, key, kind, args):
        active = self.compare.get() and kind == "line"
        self.view.comparing = active
        self.view.difference_pixels = []
        self.diff_table.delete(*self.diff_table.get_children())
        self.diff_pixels = {}
        if active:
            for i, pixels in demo.differences(args):
                item = self.diff_table.insert("", "end", values=[i] + [p[1] if abs(args[2]-args[0]) >= abs(args[3]-args[1]) else p[0] for p in pixels])
                self.diff_pixels[item] = list(set(pixels))
                self.view.difference_pixels.extend(set(pixels))
        if args == demo.SEGMENT or (kind == "circle" and args == (0, 0, 7)):
            text = demo.EXPLANATIONS[key]
        elif kind == "circle":
            text = "Окружность: целая ошибка d выбирает шаг вправо или вправо-вниз. Остальные точки получаются по симметрии."
        else:
            text = "Сравнение четырёх методов без сглаживания. Таблица содержит только отличающиеся шаги."
        self.demo_info.configure(text=text)
        self.diff_info.configure(text=("Пунктир — оба кандидата; закрашен выбранный.\n"
                                      "В таблице: шаг и координата по второй оси.\n"
                                      "Пиксели Брезенхема и Кастла могут совпадать.") if active else
                                "Сравнение отрезков выключено или выбрана окружность.")

    def on_difference(self, _):
        self.view.marked = [p for item in self.diff_table.selection() for p in self.diff_pixels.get(item, [])]
        if self.view.marked:
            self.view.center_on(*self.view.marked[0])

    def on_clear(self):
        self.pinned = []
        self.view.figures = [self.current] if self.current else []
        self.view.redraw()
        self.status.configure(text="Закреплённые фигуры убраны")

    def on_fit(self):
        pts = [p for fig in self.view.figures for p in fig["points"]]
        if pts:
            self.view.fit((min(p[0] for p in pts), min(p[1] for p in pts),
                           max(p[0] for p in pts), max(p[1] for p in pts)))

    def on_ideal(self):
        self.view.show_ideal = self.ideal.get()
        self.view.redraw()

    def on_row(self, _):
        sel = self.table.selection()
        self.view.marked = [p for item in sel for p in self.row_pixels.get(item, [])]
        if self.view.marked and not self.view.contains(self.view.marked[0] * 2):
            self.view.center_on(*self.view.marked[0])
        else:
            self.view.redraw()

    def on_zoom(self, cell):
        self.zoom_info.configure(text=f"Масштаб: 1 пиксель = {cell}×{cell} точек экрана")

    def on_hover(self, x, y):
        if x is None:
            self.status.configure(text="")
            return
        i, j = raster.rnd(x), raster.rnd(y)
        n = raster.num
        text = (f"Курсор ({n(x, 2)}; {n(y, 2)}) → пиксель ({n(i)}; {n(j)}) = квадрат "
                f"[{n(i - 0.5)}; {n(i + 0.5)}] × [{n(j - 0.5)}; {n(j + 0.5)}]")
        for fig in reversed(self.view.figures):
            hit = [p for p in fig["points"] if p[0] == i and p[1] == j]
            if hit:
                text += f"   — закрашен: {raster.ALGORITHMS[fig['key']][0]}"
                if fig["key"] == "wu":
                    text += f", яркость {n(hit[0][2])}"
                break
        self.status.configure(text=text)

    # --- построение окна -----------------------------------------------------------------------

    def _show_trace(self, trace):
        self.notes.configure(text=trace.text())
        cols = [f"c{i}" for i in range(len(trace.columns))]
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=cols, displaycolumns="#all")
        # Treeview считает свою ширину в момент смены колонок (по 200 точек на колонку), поэтому
        # сначала задаём ширины, а потом ещё раз назначаем displaycolumns — ширина пересчитается
        narrow = [title in ("i", "ход") for title in trace.columns]
        width = (TABLE_W - 40 * sum(narrow)) // max(len(cols) - sum(narrow), 1)
        for col, title, small in zip(cols, trace.columns, narrow):
            self.table.heading(col, text=title)
            self.table.column(col, width=40 if small else width, anchor="center", stretch=False)
        self.table.configure(displaycolumns=cols)
        self.row_pixels = {}
        for values, pixels in trace.rows[:TABLE_ROWS]:
            item = self.table.insert("", "end", values=values)
            self.row_pixels[item] = pixels
        rest = len(trace.rows) - TABLE_ROWS
        self.more.configure(text=f"…и ещё {rest} шагов не показано" if rest > 0 else "")

    def _update_controls(self):
        kind = raster.ALGORITHMS[self.alg.get()][1]
        for name, widgets in self.params.items():
            for widget in widgets:
                widget.state(["!disabled"] if name == kind else ["disabled"])

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(8, 6))
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(bar, text="−", width=3, command=lambda: self.view.zoom_at(*self._center(), -1)).pack(side="left")
        ttk.Button(bar, text="+", width=3, command=lambda: self.view.zoom_at(*self._center(), 1)).pack(side="left", padx=4)
        ttk.Button(bar, text="Вписать", command=self.on_fit).pack(side="left")
        self.zoom_info = ttk.Label(bar, foreground="#555")
        self.zoom_info.pack(side="left", padx=(12, 0))
        ttk.Checkbutton(bar, text="Идеальная фигура (красным)", variable=self.ideal,
                        command=self.on_ideal).pack(side="right")

    def _center(self):
        l, t, r, b = self.view.plot_area()
        return (l + r) / 2, (t + b) / 2

    def _build_controls(self):
        panel = ttk.Frame(self, padding=(8, 0))
        panel.grid(row=1, column=0, sticky="n", pady=6)

        methods = ttk.LabelFrame(panel, text="Алгоритм", padding=6)
        methods.pack(fill="x")
        for key, (title, _, _) in raster.ALGORITHMS.items():
            ttk.Radiobutton(methods, text=title, value=key, variable=self.alg,
                            command=self.apply).pack(anchor="w", pady=1)

        ttk.Button(panel, text="Для сдачи (пример)", command=self.load_demo).pack(fill="x", pady=(8, 0))
        ttk.Label(panel, text="(0; 0) → (18; −15), окружность R = 7").pack(anchor="w")
        ttk.Checkbutton(panel, text="Подсветить различия", variable=self.compare,
                        command=self.apply).pack(anchor="w", pady=4)
        self.demo_info = ttk.Label(panel, wraplength=240, justify="left", foreground="#1f4e9a")
        self.demo_info.pack(fill="x", pady=4)

        self.params = {}
        for kind, title, names, variables in (
                ("line", "Отрезок", ("x₀", "y₀", "x₁", "y₁"), self.line),
                ("circle", "Окружность", ("xc", "yc", "R"), self.circle)):
            frame = ttk.LabelFrame(panel, text=title, padding=6)
            frame.pack(fill="x", pady=(8, 0))
            widgets = []
            for k, (name, var) in enumerate(zip(names, variables)):
                label = ttk.Label(frame, text=name)
                label.grid(row=k // 2, column=(k % 2) * 2, sticky="e", padx=(0 if k % 2 == 0 else 10, 3), pady=2)
                box = ttk.Spinbox(frame, from_=0 if name == "R" else -LIMIT, to=LIMIT, increment=1,
                                  width=6, textvariable=var, command=self.apply)
                box.grid(row=k // 2, column=(k % 2) * 2 + 1, pady=2)
                box.bind("<Return>", self.apply)
                box.bind("<FocusOut>", self.apply)
                widgets += [label, box]
            self.params[kind] = widgets

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Закрепить", command=self.on_pin).pack(side="left")
        ttk.Button(buttons, text="Очистить", command=self.on_clear).pack(side="left", padx=6)

        legend = ttk.Label(panel, justify="left", foreground="#555", padding=(0, 12, 0, 0),
                           text="Целые координаты — центры клеток,\nполуцелые — границы пикселей.\n"
                                "Колесо, «−», «+» — масштаб.\nПеретаскивание — сдвиг.\n"
                                "Строка таблицы — подсветка шага.\n«Закрепить» сохраняет фигуру.")
        legend.pack(anchor="w")

    def _build_trace_panel(self):
        panel = ttk.LabelFrame(self, text="Вычисления", padding=6)
        panel.grid(row=1, column=2, sticky="ns", padx=8, pady=6)
        panel.rowconfigure(2, weight=1)
        self.time_info = ttk.Label(panel, wraplength=350, justify="left", foreground="#1f4e9a")
        self.time_info.grid(row=0, column=0, columnspan=2, sticky="w")
        self.notes = ttk.Label(panel, wraplength=350, justify="left", padding=(0, 6))
        self.notes.grid(row=1, column=0, columnspan=2, sticky="w")
        self.table = ttk.Treeview(panel, show="headings", height=12, selectmode="extended")
        self.table.grid(row=2, column=0, sticky="ns")
        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.table.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<<TreeviewSelect>>", self.on_row)
        self.more = ttk.Label(panel, foreground="#555")
        self.more.grid(row=3, column=0, columnspan=2, sticky="w")
        self.diff_info = ttk.Label(panel, wraplength=350, justify="left", padding=(0, 6))
        self.diff_info.grid(row=4, column=0, columnspan=2, sticky="w")
        self.diff_table = ttk.Treeview(panel, show="headings", height=3,
                                      columns=("i", "step", "dda", "bres", "castle"))
        for col, title in zip(self.diff_table["columns"], ("Шаг", "Пошаг.", "ЦДА", "Брез.", "Кастл")):
            self.diff_table.heading(col, text=title)
            self.diff_table.column(col, width=66, stretch=False, anchor="center")
        self.diff_table.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.diff_table.bind("<<TreeviewSelect>>", self.on_difference)

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        for name in ("TFrame", "TLabelframe", "TLabelframe.Label", "TLabel", "TRadiobutton", "TCheckbutton"):
            style.configure(name, background=BG)
        style.configure("TLabelframe.Label", font="TkHeadingFont")
        style.configure("TSpinbox", fieldbackground="white", arrowsize=12)
        style.map("TSpinbox", fieldbackground=[("disabled", BG)], foreground=[("disabled", "#a0a0a0")])
        style.map("TLabel", foreground=[("disabled", "#a0a0a0")])


if __name__ == "__main__":
    App().mainloop()
