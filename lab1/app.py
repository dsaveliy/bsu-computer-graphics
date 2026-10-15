import base64
import struct
import tkinter as tk
import zlib
from tkinter import ttk, colorchooser

from converters import rgb_to_cmyk, cmyk_to_rgb, rgb_to_hsv, hsv_to_rgb, rgb_to_hex, hex_to_rgb

BG, BORDER = "#f0f0f0", "#808080"   # классическая светлая тема

# модель -> компоненты (имя, максимум, единица измерения)
MODELS = {
    "RGB": [("R", 255, ""), ("G", 255, ""), ("B", 255, "")],
    "CMYK": [("C", 100, "%"), ("M", 100, "%"), ("Y", 100, "%"), ("K", 100, "%")],
    "HSV": [("H", 360, "°"), ("S", 100, "%"), ("V", 100, "%")],
}
TITLES = {
    "RGB": "RGB — аддитивная модель",
    "CMYK": "CMYK — субтрактивная модель",
    "HSV": "HSV — тон, насыщенность, яркость",
}
PRESETS = ["#FF3B30", "#FF9500", "#FFCC00", "#34C759", "#00C7BE", "#007AFF", "#5856D6", "#AF52DE",
           "#FF2D55", "#A2845E", "#FFFFFF", "#C7C7CC", "#8E8E93", "#48484A", "#1C1C1E", "#000000"]

SV, P = 220, 8     # размер квадрата палитры и отступ под маркер
HUE_W = 22         # ширина полосы тона
EPS = 1e-6


def to_rgb(model, v):
    """Значения модели (в единицах интерфейса) -> RGB в [0, 1]."""
    if model == "RGB":
        return tuple(x / 255 for x in v)
    if model == "CMYK":
        return cmyk_to_rgb(*(x / 100 for x in v))
    return hsv_to_rgb(v[0], v[1] / 100, v[2] / 100)


def from_rgb(model, rgb):
    """RGB в [0, 1] -> значения модели в единицах интерфейса."""
    if model == "RGB":
        return [x * 255 for x in rgb]
    if model == "CMYK":
        return [x * 100 for x in rgb_to_cmyk(*rgb)]
    h, s, v = rgb_to_hsv(*rgb)
    return [h, s * 100, v * 100]


def fmt(model, x):
    return f"{abs(round(x, 0 if model == 'RGB' else 1)):g}"


def clamp01(t):
    return min(max(t, 0.0), 1.0)


def sv_overlay_png(n):
    """Полупрозрачный PNG, который поверх заливки чистым тоном даёт квадрат S×V.

    Цвет пикселя в HSV: v·(1 − s) + v·s·тон. Значит, достаточно положить на тон серый слой
    с непрозрачностью a = 1 − v·s и яркостью v·(1 − s) / a. Тогда при смене тона
    меняется только заливка под ним, а сам слой считается один раз.
    """
    raw = bytearray()
    for y in range(n):
        v = 1 - y / (n - 1)
        raw.append(0)                                   # тип фильтра строки PNG
        for x in range(n):
            s = x / (n - 1)
            a = 1 - v * s
            gray = v * (1 - s) / a if a else 0
            raw += bytes((round(gray * 255), round(a * 255)))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", n, n, 8, 4, 0, 0, 0)   # 8 бит, «серый + альфа»
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(png)


class GradientSlider(tk.Canvas):
    """Ползунок, полоса которого показывает, каким станет цвет при сдвиге компоненты."""
    STEPS, STEP_W, BAR_H = 64, 4, 10
    W = STEPS * STEP_W

    def __init__(self, master, on_change):
        super().__init__(master, width=self.W + 2 * P, height=24, bg=BG,
                         highlightthickness=0, cursor="hand2")
        self.on_change = on_change
        self.img = tk.PhotoImage(width=self.W, height=self.BAR_H)
        y0 = 12 - self.BAR_H // 2
        self.create_image(P, y0, image=self.img, anchor="nw")
        self.create_rectangle(P - 1, y0 - 1, P + self.W, y0 + self.BAR_H, outline=BORDER)
        self.thumb = self.create_rectangle(0, 0, 0, 0, fill="white", outline="black")
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)

    def _drag(self, e):
        self.focus_set()   # чтобы недописанное значение в поле ввода применилось
        self.on_change(clamp01((e.x - P) / self.W))

    def show(self, t, colors):
        row = " ".join(c for c in colors for _ in range(self.STEP_W))
        self.img.put("{" + row + "}", to=(0, 0, self.W, self.BAR_H))   # строка размножается по высоте
        x = P + t * self.W
        self.coords(self.thumb, x - 3, 2, x + 3, 22)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Цветовые модели: CMYK · RGB · HSV")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._setup_style()

        self.values = {m: [0.0] * len(comps) for m, comps in MODELS.items()}
        self.sliders, self.vars = {}, {}

        left = ttk.LabelFrame(self, text="Палитра", padding=8)
        left.grid(row=0, column=0, sticky="ns", padx=(10, 5), pady=(10, 5))
        self._build_palette(left)

        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="n", padx=(5, 10), pady=(10, 5))
        for i, model in enumerate(MODELS):
            self._build_model(right, model).pack(fill="x", pady=(0 if i == 0 else 8, 0))

        # строка состояния с подсказкой
        ttk.Label(self, text="Измените цвет любым способом — остальные модели пересчитаются автоматически",
                  relief="sunken", padding=(6, 2)).grid(row=1, column=0, columnspan=2, sticky="ew")

        self.set_color("RGB", [255, 122, 48])



    def set_color(self, model, vals):
        """Главная функция: цвет задан в одной модели -> пересчитываем две другие."""
        self.values[model] = list(vals)
        rgb = to_rgb(model, vals)
        for other in MODELS:
            if other != model:
                self.values[other] = self._keep_undefined(other, from_rgb(other, rgb))
        self.refresh()

    def _keep_undefined(self, model, new):
        """Тон серого и C, M, Y чёрного не определены — оставляем прежние, чтобы ползунки не прыгали."""
        old = self.values[model]
        if model == "HSV":
            if new[2] < EPS:                 # чёрный: не определены H и S
                new[:2] = old[:2]
            elif new[1] < EPS:               # серый: не определён H
                new[0] = old[0]
        if model == "CMYK" and new[3] > 100 - EPS:
            new[:3] = old[:3]
        return new

    def gradient(self, model, i):
        """Цвета вдоль ползунка i-й компоненты при остальных компонентах неизменными."""
        vals, mx, n = list(self.values[model]), MODELS[model][i][1], GradientSlider.STEPS
        colors = []
        for k in range(n):
            vals[i] = mx * k / (n - 1)
            colors.append(rgb_to_hex(*to_rgb(model, vals)))
        return colors

    def refresh(self):
        """Перерисовать все элементы по текущему цвету."""
        rgb = to_rgb("RGB", self.values["RGB"])
        current = rgb_to_hex(*rgb)
        for model, comps in MODELS.items():
            for i, (_, mx, _) in enumerate(comps):
                self.sliders[model][i].show(self.values[model][i] / mx, self.gradient(model, i))
                self.vars[model][i].set(fmt(model, self.values[model][i]))

        dark_text = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 0.6
        self.preview.configure(bg=current)
        self.preview.itemconfig(self.preview_text, text=current, fill="#111111" if dark_text else "#FFFFFF")
        self.hex_var.set(current)

        h, s, v = self.values["HSV"]
        self.sv.itemconfig(self.sv_base, fill=rgb_to_hex(*hsv_to_rgb(h, 1, 1)))
        x, y = P + s / 100 * SV, P + (1 - v / 100) * SV
        self.sv.coords(self.sv_marker, x - 6, y - 6, x + 6, y + 6)
        self.sv.coords(self.sv_marker_in, x - 5, y - 5, x + 5, y + 5)
        y = P + h / 360 * SV
        self.hue.coords(self.hue_marker, P - 3, y - 3, P + HUE_W + 3, y + 3)

    def on_slider(self, model, i, t):
        vals = list(self.values[model])
        vals[i] = round(t * MODELS[model][i][1])
        self.set_color(model, vals)

    def on_entry(self, model, i):
        text = self.vars[model][i].get()
        if text == fmt(model, self.values[model][i]):
            return                                           # ничего не изменилось
        try:
            x = float(text.replace(",", "."))
        except ValueError:
            return self.refresh()                            # некорректный ввод — откат
        vals = list(self.values[model])
        vals[i] = min(max(x, 0), MODELS[model][i][1])        # выход за диапазон — обрезаем
        self.set_color(model, vals)

    def on_hex(self, _=None):
        try:
            rgb = hex_to_rgb(self.hex_var.get())
        except ValueError:
            return self.refresh()
        self.set_color("RGB", [x * 255 for x in rgb])

    def on_sv(self, e):
        s, v = clamp01((e.x - P) / SV), 1 - clamp01((e.y - P) / SV)
        self.set_color("HSV", [self.values["HSV"][0], round(s * 100), round(v * 100)])

    def on_hue(self, e):
        _, s, v = self.values["HSV"]
        self.set_color("HSV", [round(clamp01((e.y - P) / SV) * 360), s, v])

    def on_system_picker(self):
        _, color = colorchooser.askcolor(color=self.hex_var.get(), title="Выбор цвета")
        if color:
            self.set_color("RGB", [x * 255 for x in hex_to_rgb(color)])

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        for name in ("TFrame", "TLabelframe", "TLabelframe.Label", "TLabel"):
            style.configure(name, background=BG)
        style.configure("TLabelframe.Label", font="TkHeadingFont")
        style.configure("TSpinbox", fieldbackground="white", arrowsize=12)
        style.configure("TEntry", fieldbackground="white")

    def _build_model(self, parent, model):
        frame = ttk.LabelFrame(parent, text=TITLES[model], padding=(8, 4))
        self.sliders[model], self.vars[model] = [], []
        for i, (name, mx, unit) in enumerate(MODELS[model]):
            ttk.Label(frame, text=name, width=2).grid(row=i, column=0, sticky="w")

            slider = GradientSlider(frame, lambda t, i=i: self.on_slider(model, i, t))
            slider.grid(row=i, column=1, padx=4, pady=1)

            var = tk.StringVar()
            box = ttk.Spinbox(frame, from_=0, to=mx, increment=1, width=6, textvariable=var,
                              wrap=(name == "H"), command=lambda i=i: self.on_entry(model, i))
            box.grid(row=i, column=2)
            for event in ("<Return>", "<KP_Enter>", "<FocusOut>"):
                box.bind(event, lambda e, i=i: self.on_entry(model, i))

            ttk.Label(frame, text=unit, width=2).grid(row=i, column=3, sticky="w", padx=(4, 0))
            self.sliders[model].append(slider)
            self.vars[model].append(var)
        return frame

    def _build_palette(self, frame):
        # квадрат: по горизонтали насыщенность S, по вертикали яркость V
        self.sv = tk.Canvas(frame, width=SV + 2 * P, height=SV + 2 * P, bg=BG, highlightthickness=0,
                            cursor="crosshair")
        self.sv.grid(row=0, column=0)
        self.sv_base = self.sv.create_rectangle(P, P, P + SV, P + SV, width=0)   # заливка чистым тоном
        self.sv_img = tk.PhotoImage(data=sv_overlay_png(SV))
        self.sv.create_image(P, P, image=self.sv_img, anchor="nw")
        self.sv.create_rectangle(P - 1, P - 1, P + SV, P + SV, outline=BORDER)
        self.sv_marker = self.sv.create_oval(0, 0, 0, 0, outline="black")       # двойное кольцо видно
        self.sv_marker_in = self.sv.create_oval(0, 0, 0, 0, outline="white")    # и на светлом, и на тёмном

        # полоса тона H
        self.hue = tk.Canvas(frame, width=HUE_W + 2 * P, height=SV + 2 * P, bg=BG, highlightthickness=0,
                             cursor="hand2")
        self.hue.grid(row=0, column=1)
        self.hue_img = tk.PhotoImage(width=HUE_W, height=SV)
        rows = (rgb_to_hex(*hsv_to_rgb(360 * y / (SV - 1), 1, 1)) for y in range(SV))
        self.hue_img.put(" ".join("{%s}" % c for c in rows), to=(0, 0, HUE_W, SV))
        self.hue.create_image(P, P, image=self.hue_img, anchor="nw")
        self.hue.create_rectangle(P - 1, P - 1, P + HUE_W, P + SV, outline=BORDER)
        self.hue_marker = self.hue.create_rectangle(0, 0, 0, 0, outline="black", width=2)

        for widget, handler in ((self.sv, self.on_sv), (self.hue, self.on_hue)):
            widget.bind("<Button-1>", handler)
            widget.bind("<B1-Motion>", handler)

        # образец текущего цвета
        self.preview = tk.Canvas(frame, width=SV + HUE_W + 2 * P - 2, height=56,
                                 highlightthickness=1, highlightbackground=BORDER)
        self.preview.grid(row=1, column=0, columnspan=2, pady=(6, 8))
        self.preview_text = self.preview.create_text(12, 29, anchor="w", font=("Helvetica", 16, "bold"))

        # точный HEX и системный диалог
        row = ttk.Frame(frame)
        row.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Label(row, text="HEX:").pack(side="left")
        self.hex_var = tk.StringVar()
        hex_entry = ttk.Entry(row, textvariable=self.hex_var, width=9)
        hex_entry.pack(side="left", padx=6)
        hex_entry.bind("<Return>", self.on_hex)
        hex_entry.bind("<FocusOut>", self.on_hex)
        ttk.Button(row, text="Палитра ОС…", command=self.on_system_picker).pack(side="right")

        # быстрый выбор
        ttk.Label(frame, text="Быстрый выбор:").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 4))
        grid = ttk.Frame(frame)
        grid.grid(row=4, column=0, columnspan=2, sticky="w")
        for k, color in enumerate(PRESETS):
            swatch = tk.Frame(grid, width=24, height=24, bg=color, cursor="hand2",
                              highlightthickness=1, highlightbackground=BORDER)
            swatch.grid(row=k // 8, column=k % 8, padx=(0, 4), pady=(0, 4))
            swatch.bind("<Button-1>", lambda e, c=color: self.set_color("RGB", [x * 255 for x in hex_to_rgb(c)]))

if __name__ == "__main__":
    App().mainloop()
