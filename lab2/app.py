import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk

import processing as proc

BG = "#f0f0f0"
VIEW = 400                 # сторона области показа изображения
HIST_H = 110               # высота гистограммы
MAX_ZOOM = 16              # при наибольшем увеличении пиксель — квадрат 16×16 точек экрана
IMAGES = Path(__file__).with_name("images")

METHODS = {
    "linear": "Линейное контрастирование",
    "equalize": "Эквализация гистограммы",
    "box": "Усредняющий фильтр",
    "gauss": "Фильтр Гаусса",
}


def load(path):
    """Файл -> uint8 (h, w) или (h, w, 3); прозрачность и палитра отбрасываются."""
    img = Image.open(path)
    img = img.convert("L" if img.mode in ("1", "L", "I;16", "I") else "RGB")
    return np.array(img)


class HistogramView(tk.Canvas):
    """Гистограмма яркости (серые столбцы), каналы R, G, B (линии) и CDF (чёрный пунктир)."""

    def __init__(self, master):
        super().__init__(master, width=VIEW, height=HIST_H, bg="white",
                         highlightthickness=1, highlightbackground="#808080")

    def show(self, img):
        self.delete("all")
        sx = VIEW / proc.LEVELS
        y_hist = proc.histogram(proc.luminance(img))
        channels = [img[..., c] for c in range(3)] if img.ndim == 3 else []
        hists = [proc.histogram(ch) for ch in channels]
        peak = max(h.max() for h in [y_hist, *hists])

        def y(count):
            return HIST_H - 2 - count / peak * (HIST_H - 6)

        for level, count in enumerate(y_hist):
            if count:
                self.create_rectangle(level * sx, y(count), (level + 1) * sx, HIST_H,
                                      fill="#9a9a9a", outline="")
        for h, color in zip(hists, ("#d03030", "#30a030", "#3050d0")):
            self.create_line(*[(i * sx + sx / 2, y(c)) for i, c in enumerate(h)], fill=color)
        cdf = np.cumsum(y_hist) / y_hist.sum()
        self.create_line(*[(i * sx + sx / 2, y(c * peak)) for i, c in enumerate(cdf)], dash=(3, 2))


class ImagePanel(ttk.LabelFrame):
    """Изображение, его гистограмма и числовые характеристики."""

    def __init__(self, master, title, on_click):
        super().__init__(master, text=title, padding=6)
        self.img = None
        self.photo = tk.PhotoImage(width=VIEW, height=VIEW)  # пустое место, пока ничего не открыто
        self.picture = tk.Label(self, image=self.photo, bg="#d8d8d8", bd=0, highlightthickness=0,
                                cursor="crosshair")
        self.picture.pack()
        # левая кнопка — приблизить, правая — отдалить; правая кнопка в Tk на macOS — Button-2,
        # на Windows и Linux — Button-3, на Mac ещё бывает Ctrl+клик
        self.picture.bind("<Button-1>", lambda e: on_click(self.to_image(e), 2))
        for button in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.picture.bind(button, lambda e: on_click(self.to_image(e), 0.5))
        self.hist = HistogramView(self)
        self.hist.pack(pady=(6, 2))
        self.info = ttk.Label(self, font="TkFixedFont")
        self.info.pack(anchor="w")

    def show(self, img, zoom, center):
        self.img = img
        self.render(zoom, center)
        self.hist.show(img)                               # гистограмма и числа — по всему изображению
        s = proc.stats(img)
        self.info.configure(text=f"яркость {s['min']}–{s['max']}, среднее {s['mean']:.1f}, "
                                 f"СКО {s['std']:.1f}, уровней {s['levels']}")

    def render(self, zoom, center):
        """zoom = 1 — изображение целиком вписано в окно; zoom = k — каждый пиксель показан
        квадратом k×k точек экрана, видна окрестность точки center (в пикселях изображения)."""
        h, w = self.img.shape[:2]
        self.scale = zoom if zoom > 1 else min(1, VIEW / w, VIEW / h)    # точек экрана на пиксель
        bw, bh = min(w, VIEW / self.scale), min(h, VIEW / self.scale)    # видимая часть, в пикселях
        cx, cy = center or (w / 2, h / 2)
        x0 = round(min(max(cx - bw / 2, 0), w - bw))     # прижимаем, чтобы не вылезти за край
        y0 = round(min(max(cy - bh / 2, 0), h - bh))
        self.origin = (x0, y0)
        size = (round(bw * self.scale), round(bh * self.scale))
        # при увеличении NEAREST: пиксели остаются чёткими квадратами, показ ничего не сглаживает;
        # при уменьшении LANCZOS, как раньше (расчёт всё равно идёт по оригиналу)
        resample = Image.NEAREST if zoom > 1 else Image.LANCZOS
        preview = Image.fromarray(self.img).resize(size, resample, box=(x0, y0, x0 + bw, y0 + bh))
        self.photo = ImageTk.PhotoImage(preview)          # ссылка нужна, иначе Tk потеряет картинку
        self.picture.configure(image=self.photo, width=VIEW, height=VIEW)

    def to_image(self, event):
        """Точка клика на экране -> координаты в пикселях изображения."""
        if self.img is None:
            return None
        h, w = self.img.shape[:2]
        # картинка стоит по центру поля, вокруг могут быть серые полосы
        ox = (self.picture.winfo_width() - self.photo.width()) / 2
        oy = (self.picture.winfo_height() - self.photo.height()) / 2
        x = self.origin[0] + (event.x - ox) / self.scale
        y = self.origin[1] + (event.y - oy) / self.scale
        return min(max(x, 0), w), min(max(y, 0), h)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Лабораторная 2: гистограмма, контраст, сглаживание")
        self.configure(bg=BG)
        self._setup_style()
        self.source = self.result = None
        self.zoom, self.center = 1, None      # общие для обеих картинок, чтобы сравнивать одно место

        self.method = tk.StringVar(value="linear")
        self.mode = tk.StringVar(value="rgb")
        self.clip = tk.DoubleVar(value=0.0)
        self.size = tk.IntVar(value=3)
        self.sigma = tk.DoubleVar(value=1.0)
        self.test_image = tk.StringVar()

        self._build_toolbar()
        self._build_controls()
        self.source_view = ImagePanel(self, "Исходное", self.on_zoom)
        self.source_view.grid(row=1, column=1, padx=4, pady=6, sticky="n")
        self.result_view = ImagePanel(self, "Результат", self.on_zoom)
        self.result_view.grid(row=1, column=2, padx=(4, 8), pady=6, sticky="n")
        self.status = ttk.Label(self, relief="sunken", padding=(6, 2))
        self.status.grid(row=2, column=0, columnspan=3, sticky="ew")

        tests = sorted(IMAGES.glob("*.png"))
        if tests:
            self.test_image.set(tests[0].name)
            self.open(tests[0])

    # --- действия ----------------------------------------------------------------------------

    def open(self, path):
        try:
            self.source = load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("Не удалось открыть", str(e))
            return
        h, w = self.source.shape[:2]
        kind = "полутоновое" if self.source.ndim == 2 else "цветное"
        self.status.configure(text=f"{Path(path).name}: {w}×{h}, {kind}")
        self._set_zoom(1, None)               # новая картинка — снова целиком
        self.source_view.show(self.source, self.zoom, self.center)
        self.apply()

    def apply(self, *_):
        if self.source is None:
            return
        try:
            method, mode = self.method.get(), self.mode.get()
            if method == "linear":
                clip = min(max(self.clip.get(), 0.0), 49.0)
                self.result = proc.linear_stretch(self.source, clip, mode)
            elif method == "equalize":
                self.result = proc.equalize(self.source, mode)
            elif method == "box":
                self.result = proc.box_filter(self.source, self.size.get())
            else:
                self.result = proc.gaussian_filter(self.source, self.sigma.get())
        except tk.TclError:                 # в поле параметра сейчас не число — ждём ввода
            return
        self.result_view.show(self.result, self.zoom, self.center)
        self._update_controls()

    def on_zoom(self, point, factor):
        """Клик по любой из картинок: обе приближаются (factor = 2) или отдаляются (0.5) вокруг point."""
        if point is None:
            return
        zoom = int(min(max(self.zoom * factor, 1), MAX_ZOOM))
        if zoom == self.zoom:
            return
        self._set_zoom(zoom, point)
        for view in (self.source_view, self.result_view):
            if view.img is not None:
                view.render(self.zoom, self.center)

    def _set_zoom(self, zoom, center):
        self.zoom, self.center = zoom, center
        self.zoom_info.configure(text="Масштаб: целиком" if zoom == 1 else
                                 f"Масштаб: ×{zoom} (пиксель = {zoom}×{zoom} точек экрана)")

    def on_open_file(self):
        path = filedialog.askopenfilename(
            initialdir=IMAGES, filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Все", "*")])
        if path:
            self.open(path)

    def on_save(self):
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            Image.fromarray(self.result).save(path)

    def on_chain(self):
        """Сделать результат исходным, чтобы применить следующий метод поверх него."""
        if self.result is not None:
            self.source = self.result
            self.status.configure(text=f"Исходным стал результат: {METHODS[self.method.get()].lower()}")
            self.source_view.show(self.source, self.zoom, self.center)
            self.apply()

    # --- построение окна ---------------------------------------------------------------------

    def _update_controls(self):
        """Включить только те параметры, которые использует выбранный метод."""
        method = self.method.get()
        used = {
            "clip": method == "linear",
            "mode": method in ("linear", "equalize") and self.source.ndim == 3,
            "size": method == "box",
            "sigma": method == "gauss",
        }
        for name, widgets in self.params.items():
            for widget in widgets:
                widget.state(["!disabled"] if used[name] else ["disabled"])
        if method == "gauss":
            k = len(proc.gaussian_kernel(self.sigma.get()))
            self.kernel_info.configure(text=f"ядро {k}×{k}")
        else:
            self.kernel_info.configure(text="")

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(8, 6))
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(bar, text="Открыть…", command=self.on_open_file).pack(side="left")
        ttk.Label(bar, text="Тестовые:").pack(side="left", padx=(12, 4))
        names = [p.name for p in sorted(IMAGES.glob("*.png"))]
        box = ttk.Combobox(bar, textvariable=self.test_image, values=names, state="readonly", width=34)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: self.open(IMAGES / self.test_image.get()))
        self.zoom_info = ttk.Label(bar, foreground="#555")
        self.zoom_info.pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Сохранить результат…", command=self.on_save).pack(side="right")
        ttk.Button(bar, text="Результат → исходное", command=self.on_chain).pack(side="right", padx=6)

    def _build_controls(self):
        panel = ttk.Frame(self, padding=(8, 0))
        panel.grid(row=1, column=0, sticky="n", pady=6)

        methods = ttk.LabelFrame(panel, text="Метод", padding=6)
        methods.pack(fill="x")
        for key, title in METHODS.items():
            ttk.Radiobutton(methods, text=title, value=key, variable=self.method,
                            command=self.apply).pack(anchor="w", pady=1)

        contrast = ttk.LabelFrame(panel, text="Контраст", padding=6)
        contrast.pack(fill="x", pady=(8, 0))
        clip_label = ttk.Label(contrast, text="Отсечь с каждого края, %:")
        clip_label.pack(anchor="w")
        clip = ttk.Spinbox(contrast, from_=0, to=10, increment=0.5, width=6, textvariable=self.clip,
                           command=self.apply)
        clip.pack(anchor="w", pady=(2, 6))
        mode_label = ttk.Label(contrast, text="Цветное изображение:")
        mode_label.pack(anchor="w")
        rgb = ttk.Radiobutton(contrast, text="RGB — каждый канал", value="rgb", variable=self.mode,
                              command=self.apply)
        rgb.pack(anchor="w")
        hsv = ttk.Radiobutton(contrast, text="HSV — только яркость V", value="hsv", variable=self.mode,
                              command=self.apply)
        hsv.pack(anchor="w")

        smooth = ttk.LabelFrame(panel, text="Сглаживание", padding=6)
        smooth.pack(fill="x", pady=(8, 0))
        size_label = ttk.Label(smooth, text="Размер ядра (нечётный):")
        size_label.pack(anchor="w")
        size = ttk.Spinbox(smooth, from_=3, to=31, increment=2, width=6, textvariable=self.size,
                           command=self.apply, state="readonly")
        size.pack(anchor="w", pady=(2, 6))
        sigma_label = ttk.Label(smooth, text="σ фильтра Гаусса:")
        sigma_label.pack(anchor="w")
        sigma = ttk.Spinbox(smooth, from_=0.5, to=5, increment=0.5, width=6, textvariable=self.sigma,
                            command=self.apply, state="readonly")
        sigma.pack(anchor="w", pady=(2, 0))
        self.kernel_info = ttk.Label(smooth)
        self.kernel_info.pack(anchor="w")

        clip.bind("<Return>", self.apply)
        clip.bind("<FocusOut>", self.apply)
        self.params = {
            "clip": [clip_label, clip],
            "mode": [mode_label, rgb, hsv],
            "size": [size_label, size],
            "sigma": [sigma_label, sigma],
        }

        legend = ttk.Label(panel, justify="left", foreground="#555", padding=(0, 12, 0, 0),
                           text="Гистограмма:\nсерые столбцы — яркость\n"
                                "линии — каналы R, G, B\nпунктир — накопленная (CDF)\n\n"
                                "Клик по картинке — приблизить\nв 2 раза, правый клик — отдалить")
        legend.pack(anchor="w")

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        for name in ("TFrame", "TLabelframe", "TLabelframe.Label", "TLabel", "TRadiobutton"):
            style.configure(name, background=BG)
        style.configure("TLabelframe.Label", font="TkHeadingFont")
        style.configure("TSpinbox", fieldbackground="white", arrowsize=12)
        # выключенный параметр должен выглядеть выключенным, а не просто белым полем
        style.map("TSpinbox", fieldbackground=[("disabled", BG)], foreground=[("disabled", "#a0a0a0")])
        style.map("TLabel", foreground=[("disabled", "#a0a0a0")])
        style.map("TRadiobutton", foreground=[("disabled", "#a0a0a0")])


if __name__ == "__main__":
    App().mainloop()
