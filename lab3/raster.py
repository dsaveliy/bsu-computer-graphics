"""Базовые растровые алгоритмы.

Привязка к сетке: пиксель (i, j) — квадрат со стороной 1 и центром в целочисленной точке (i, j),
то есть [i − 0,5; i + 0,5] × [j − 0,5; j + 0,5]. Концы отрезков и центр окружности задаются
целыми числами, значит, лежат точно в центрах пикселей. Алгоритм решает, какие квадраты закрасить.

Каждая функция возвращает список пикселей (x, y) в порядке построения; алгоритм Ву — (x, y, яркость).
Если передан trace (объект Trace), в него пишутся исходные величины и таблица вычислений по шагам.
Без trace функции работают «начисто» — так и замеряется время.
"""
import math
from math import floor


class Trace:
    """Протокол вычислений для показа в приложении и в отчёте."""

    def __init__(self):
        self.notes = []      # строки с исходными величинами и правилами шага
        self.columns = ()    # заголовки колонок таблицы
        self.rows = []       # [(значения колонок, [пиксели, построенные на этом шаге])]

    def row(self, values, pixels=()):
        self.rows.append((tuple(str(v).replace("-", "−") for v in values), list(pixels)))

    def text(self):
        """Исходные величины одним текстом, минус — типографский."""
        return "\n".join(self.notes).replace("-", "−")


def rnd(v):
    """Округление к ближайшему целому, половина — вверх. Встроенный round() округляет 2.5 до 2
    («банковское» округление), из-за чего соседние половинки округлялись бы в разные стороны.
    В циклах алгоритмов то же самое записано прямо: floor(v + 0.5) — лишний вызов функции
    на каждый пиксель в Python стоит дороже самой арифметики и исказил бы замеры времени."""
    return floor(v + 0.5)


def num(v, digits=3):
    """Число для таблицы: 0,429; 1,5; −2."""
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s.replace(".", ",").replace("-", "−")


def pt(x, y):
    return f"({num(x)}; {num(y)})"


# --- 1. Пошаговый алгоритм --------------------------------------------------------------------

def step_by_step(x0, y0, x1, y1, trace=None):
    """Прямо по уравнению прямой y = kx + b: x идёт с шагом 1, y вычисляется и округляется.
    Если отрезок крутой (|dy| > |dx|), шагать по x нельзя — между пикселями будут дыры,
    поэтому оси меняются ролями: шаг по y, x = k'y + b'."""
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        if trace is not None:
            trace.notes.append("Отрезок вырожден в точку")
            trace.columns = ("i", "пиксель")
            trace.row((0, pt(x0, y0)), [(x0, y0)])
        return [(x0, y0)]
    points = []
    if abs(dx) >= abs(dy):                     # пологий: главная ось x
        k = dy / dx
        b = y0 - k * x0
        s = 1 if dx > 0 else -1
        if trace is not None:
            trace.notes += [f"dx = {dx}, dy = {dy}: |dx| ≥ |dy| — шаг по x на {s:+d}",
                            f"k = dy/dx = {num(k)},  b = y₀ − k·x₀ = {num(b)}",
                            "y = k·x + b, пиксель (x, round(y))"]
            trace.columns = ("i", "x", "y = kx + b", "пиксель")
        for x in range(x0, x1 + s, s):
            y = k * x + b
            py = floor(y + 0.5)
            points.append((x, py))
            if trace is not None:
                trace.row((len(points) - 1, x, num(y), pt(x, py)), [(x, py)])
    else:                                      # крутой: главная ось y
        k = dx / dy
        b = x0 - k * y0
        s = 1 if dy > 0 else -1
        if trace is not None:
            trace.notes += [f"dx = {dx}, dy = {dy}: |dy| > |dx| — шаг по y на {s:+d}",
                            f"k' = dx/dy = {num(k)},  b' = x₀ − k'·y₀ = {num(b)}",
                            "x = k'·y + b', пиксель (round(x), y)"]
            trace.columns = ("i", "y", "x = k'y + b'", "пиксель")
        for y in range(y0, y1 + s, s):
            x = k * y + b
            px = floor(x + 0.5)
            points.append((px, y))
            if trace is not None:
                trace.row((len(points) - 1, y, num(x), pt(px, y)), [(px, y)])
    return points


# --- 2. ЦДА (цифровой дифференциальный анализатор) -------------------------------------------

def dda(x0, y0, x1, y1, trace=None):
    """Делим отрезок на L = max(|dx|, |dy|) равных шагов. За шаг x и y получают постоянные
    приращения (одно из них ±1, второе по модулю ≤ 1) — умножение заменено сложением."""
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        if trace is not None:
            trace.notes.append("Отрезок вырожден в точку")
            trace.columns = ("i", "пиксель")
            trace.row((0, pt(x0, y0)), [(x0, y0)])
        return [(x0, y0)]
    ix, iy = dx / steps, dy / steps
    x, y = float(x0), float(y0)
    if trace is not None:
        trace.notes += [f"dx = {dx}, dy = {dy},  L = max(|dx|, |dy|) = {steps}",
                        f"Δx = dx/L = {num(ix)},  Δy = dy/L = {num(iy)}",
                        "x += Δx, y += Δy, пиксель (round(x), round(y))"]
        trace.columns = ("i", "x", "y", "пиксель")
    points = []
    for i in range(steps + 1):
        px, py = floor(x + 0.5), floor(y + 0.5)
        points.append((px, py))
        if trace is not None:
            trace.row((i, num(x), num(y), pt(px, py)), [(px, py)])
        x += ix
        y += iy
    return points


# --- 3. Брезенхем, отрезок ---------------------------------------------------------------------

def bresenham_line(x0, y0, x1, y1, trace=None):
    """Только целые числа. По главной оси шаг всегда, по второй — когда ошибка e ≥ 0.
    e — это (отклонение прямой от центра текущего пикселя − 1/2), умноженное на 2·dx,
    чтобы все величины стали целыми: e₀ = 2dy − dx, шаг: e += 2dy, сдвиг по второй оси: e −= 2dx.
    Для крутого отрезка dx и dy меняются ролями (главная ось y), поэтому циклов два."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 >= x0 else -1
    sy = 1 if y1 >= y0 else -1
    steep = dy > dx
    if trace is not None:
        a, b, s1, s2 = ("y", "x", sy, sx) if steep else ("x", "y", sx, sy)
    if steep:
        dx, dy = dy, dx        # дальше dx — длина по главной оси, dy — по второй
    e = 2 * dy - dx
    dx2, dy2 = 2 * dx, 2 * dy  # удвоенные приращения считаются один раз, до цикла
    if trace is not None:
        trace.notes += [f"dx = {abs(x1 - x0)}, dy = {abs(y1 - y0)}: главная ось {a} (шаг {s1:+d}), "
                        f"вторая {b} (шаг {s2:+d})",
                        f"e₀ = 2·{dy} − {dx} = {num(e)};  2·{dy} = {dy2},  2·{dx} = {dx2}",
                        f"e ≥ 0: сдвиг по {b}, e −= {dx2};  всегда e += {dy2}"]
        trace.columns = ("i", "пиксель", "e", f"сдвиг по {b}?", "новое e")
    x, y = x0, y0
    points = []
    if not steep:
        for i in range(dx + 1):
            points.append((x, y))
            if trace is not None:
                _bresenham_row(trace, i, dx, (x, y), e, dx2, dy2)
            if e >= 0:
                y += sy
                e -= dx2
            e += dy2
            x += sx
    else:
        for i in range(dx + 1):
            points.append((x, y))
            if trace is not None:
                _bresenham_row(trace, i, dx, (x, y), e, dx2, dy2)
            if e >= 0:
                x += sx
                e -= dx2
            e += dy2
            y += sy
    return points


def _bresenham_row(trace, i, n, pixel, e, dx2, dy2):
    """Строка таблицы для шага i: решение и новое e — по тем же правилам, что в цикле.
    После последнего пикселя решение уже не нужно."""
    if i == n:
        trace.row((i, pt(*pixel), num(e), "—", "—"), [pixel])
    else:
        shift = e >= 0
        trace.row((i, pt(*pixel), num(e), "да" if shift else "нет", num(e - dx2 * shift + dy2)), [pixel])


# --- 4. Брезенхем, окружность -------------------------------------------------------------------

def bresenham_circle(xc, yc, r, trace=None):
    """Строится дуга второго октанта: от (0, R) по часовой стрелке, пока x ≤ y; x растёт на 1
    каждый шаг. Кандидаты на следующем шаге: T = (x+1, y) и S = (x+1, y−1).
    d = D(T) + D(S), где D(p) = px² + py² − R² (> 0 — снаружи, < 0 — внутри).
    d < 0 — ближе T, иначе S. Остальные 7 октантов — по симметрии (±x, ±y), (±y, ±x)."""
    x, y, d = 0, r, 3 - 2 * r
    if trace is not None:
        trace.notes += [f"Центр {pt(xc, yc)}, R = {r}.  Старт: x = 0, y = R = {r}, d = 3 − 2R = {num(d)}",
                        "d < 0 → T = (x+1, y), d += 4x + 6;  d ≥ 0 → S = (x+1, y−1), d += 4(x − y) + 10",
                        "Пока x ≤ y; каждая точка даёт 8 пикселей по симметрии"]
        trace.columns = ("i", "(x; y)", "d", "выбор", "новое d")
    points = []
    i = 0
    while x <= y:
        octs = [(xc + x, yc + y), (xc + y, yc + x), (xc + y, yc - x), (xc + x, yc - y),
                (xc - x, yc - y), (xc - y, yc - x), (xc - y, yc + x), (xc - x, yc + y)]
        points += octs
        if trace is not None:
            old, cur = d, (x, y)
        if d < 0:
            d += 4 * x + 6
            choice = "T"
        else:
            d += 4 * (x - y) + 10
            y -= 1
            choice = "S"
        if trace is not None:
            trace.row((i, pt(*cur), num(old), choice, num(d)), octs)
        x += 1
        i += 1
    return list(dict.fromkeys(points))      # убрать повторы на осях и диагоналях, сохранив порядок


# --- 5. Кастл–Питвей -----------------------------------------------------------------------------

def castle_pitteway_moves(a, b, trace=None):
    """Строка ходов для отрезка (0, 0) → (a, b), 0 ≤ b ≤ a: s — шаг по главной оси, d — по диагонали.
    Ходов всего a, из них d — ровно b. Строка строится как в алгоритме Евклида: пока x ≠ y,
    из большего вычитается меньшее, а соответствующая подстрока удлиняется. ᴿ — запись наоборот."""
    if b == 0:
        return "s" * a
    if b == a:
        return "d" * a
    x, y = a - b, b
    m1, m2 = "s", "d"
    if trace is not None:
        trace.notes.append(f"x = a − b = {x},  y = b = {y},  m1 = s,  m2 = d")
    while x != y:
        if x > y:
            x -= y
            m2 = m1 + m2[::-1]
            if trace is not None:
                trace.notes.append(f"x > y:  x = {x},  m2 = m1·m2ᴿ = {short(m2)}")
        else:
            y -= x
            m1 = m2 + m1[::-1]
            if trace is not None:
                trace.notes.append(f"x < y:  y = {y},  m1 = m2·m1ᴿ = {short(m1)}")
    moves = (m2 + m1[::-1]) * x
    if trace is not None:
        trace.notes.append(f"x = y = {x}:  ходы = (m2·m1ᴿ)^{x} = {short(moves)}")
    return moves


def short(s, limit=40):
    return s if len(s) <= limit else s[:limit] + f"… ({len(s)} симв.)"


def castle_pitteway(x0, y0, x1, y1, trace=None):
    """Отрезок приводится к первому октанту (отражения по знакам и обмен осей), там строится
    строка ходов, затем ходы переводятся обратно в шаги исходного отрезка."""
    dx, dy = x1 - x0, y1 - y0
    sx = 1 if dx >= 0 else -1
    sy = 1 if dy >= 0 else -1
    a, b = abs(dx), abs(dy)
    steep = b > a
    if steep:
        a, b = b, a
    step_s = (0, sy) if steep else (sx, 0)    # ход s — по главной оси
    step_d = (sx, sy)                         # ход d — по диагонали
    if trace is not None:
        trace.notes.append(f"dx = {dx}, dy = {dy} → первый октант: a = {a}, b = {b}"
                           + (" (оси поменяны)" if steep else ""))
        sg = lambda v: f"{v:+d}" if v else "0"
        trace.notes.append(f"s = шаг ({sg(step_s[0])}; {sg(step_s[1])}),  d = шаг ({sg(step_d[0])}; {sg(step_d[1])})")
    moves = castle_pitteway_moves(a, b, trace)
    x, y = x0, y0
    points = [(x, y)]
    if trace is not None:
        trace.columns = ("i", "ход", "пиксель")
        trace.row((0, "старт", pt(x, y)), [(x, y)])
    for i, m in enumerate(moves, 1):
        mx, my = step_s if m == "s" else step_d
        x += mx
        y += my
        points.append((x, y))
        if trace is not None:
            trace.row((i, m, pt(x, y)), [(x, y)])
    return points


# --- 6. Сглаженный отрезок: алгоритм Ву ---------------------------------------------------------

def wu_line(x0, y0, x1, y1, trace=None):
    """На каждом шаге по главной оси прямая проходит между центрами двух соседних пикселей.
    Яркость делится между ними пропорционально близости: при y = [y] + f нижний получает 1 − f,
    верхний f. Концы целые, поэтому y считается точно в целых: y = y₀ + q + r/dx (divmod),
    без накопления ошибки плавающей точки."""
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        if trace is not None:
            trace.notes.append("Отрезок вырожден в точку")
            trace.columns = ("i", "пиксель")
            trace.row((0, pt(x0, y0)), [(x0, y0)])
        return [(x0, y0, 1.0)]
    steep = abs(dy) > abs(dx)
    if steep:                                  # работаем с отражённым отрезком, пиксели отражаем обратно
        x0, y0, x1, y1, dx, dy = y0, x0, y1, x1, dy, dx
    if dx < 0:                                 # идём слева направо
        x0, y0, x1, y1, dx, dy = x1, y1, x0, y0, -dx, -dy
    a, b = ("y", "x") if steep else ("x", "y")
    if trace is not None:
        trace.notes += [f"главная ось {a}, k = d{b}/d{a} = {num(dy / dx)}",
                        f"{b} = {b}₀ + k·({a} − {a}₀) = [{b}] + f,  [{b}] — целая часть",
                        f"яркость ({a}, [{b}]) = 1 − f,  ({a}, [{b}] + 1) = f"]
        trace.columns = (a, f"{b} точн.", f"[{b}]", "f", "1 − f")
    points = []
    for x in range(x0, x1 + 1):
        q, r = divmod(dy * (x - x0), dx)       # dy·(x − x0) / dx = q + r/dx, 0 ≤ r < dx
        y = y0 + q
        f = r / dx
        if steep:                              # пиксели отражаем обратно
            points.append((y, x, 1.0 - f))
            if r:
                points.append((y + 1, x, f))
        else:
            points.append((x, y, 1.0 - f))
            if r:
                points.append((x, y + 1, f))
        if trace is not None:
            pair = points[-2:] if r else points[-1:]
            trace.row((num(x), num(y + f), num(y), num(f), num(1 - f)), [(p[0], p[1]) for p in pair])
    return points


# --- реестр для приложения --------------------------------------------------------------------

ALGORITHMS = {
    "step": ("Пошаговый", "line", step_by_step),
    "dda": ("ЦДА", "line", dda),
    "bresenham": ("Брезенхем (отрезок)", "line", bresenham_line),
    "circle": ("Брезенхем (окружность)", "circle", bresenham_circle),
    "castle": ("Кастл–Питвей", "line", castle_pitteway),
    "wu": ("Ву (сглаживание)", "line", wu_line),
}
