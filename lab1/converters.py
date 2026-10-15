"""Переводы между цветовыми моделями.

Все компоненты нормированы в [0, 1], кроме тона H — он в градусах [0, 360).
"""


def rgb_to_cmyk(r, g, b):
    k = 1 - max(r, g, b)               # чёрный — то, чего не хватает до самого яркого канала
    if k == 1:                          # чистый чёрный: C, M, Y не определены
        return 0.0, 0.0, 0.0, 1.0
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return c, m, y, k


def cmyk_to_rgb(c, m, y, k):
    return (1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)


def rgb_to_hsv(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn                         # «хроматичность» — разброс каналов
    if d == 0:
        h = 0.0                         # оттенок серого: тон не определён
    elif mx == r:
        h = 60 * (((g - b) / d) % 6)
    elif mx == g:
        h = 60 * ((b - r) / d + 2)
    else:
        h = 60 * ((r - g) / d + 4)
    s = 0.0 if mx == 0 else d / mx
    return h, s, mx                     # V — это просто максимальный канал


def hsv_to_rgb(h, s, v):
    c = v * s                           # хроматичность
    x = c * (1 - abs(h / 60 % 2 - 1))   # вторая по величине компонента
    m = v - c                           # добавка серого до нужной яркости
    sector = int(h // 60) % 6           # в каком из 6 секторов цветового круга лежит тон
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][sector]
    return r + m, g + m, b + m


def rgb_to_hex(r, g, b):
    return "#{:02X}{:02X}{:02X}".format(*(round(t * 255) for t in (r, g, b)))


def hex_to_rgb(text):
    text = text.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError("ожидается #RRGGBB")
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
