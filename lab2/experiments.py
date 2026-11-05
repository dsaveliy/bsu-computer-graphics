"""Численные эксперименты для отчёта: печатает все таблицы, на которые опираются выводы.

Запуск: python experiments.py  (после make_test_images.py)
"""
import time
from pathlib import Path

import numpy as np
from PIL import Image

import processing as proc

IMAGES = Path(__file__).with_name("images")


def load(name):
    return np.array(Image.open(IMAGES / f"{name}.png"))


def hue_shift(a, b):
    """Медианный сдвиг тона в градусах по заметно окрашенным пикселям (S > 0,2, V > 0,1)."""
    def hue(img):
        x = img.astype(float) / 255
        mx, mn = x.max(-1), x.min(-1)
        d = np.where(mx > mn, mx - mn, 1)
        r, g, b = np.moveaxis(x, -1, 0)
        h = np.select([mx == r, mx == g], [((g - b) / d) % 6, (b - r) / d + 2], (r - g) / d + 4)
        return h * 60, np.divide(mx - mn, mx, out=np.zeros_like(mx), where=mx > 0), mx

    ha, sa, va = hue(a)
    hb = hue(b)[0]
    diff = np.abs(ha - hb)
    diff = np.minimum(diff, 360 - diff)
    return float(np.median(diff[(sa > 0.2) & (va > 0.1)]))


def contrast_table():
    print("Контраст: СКО яркости / число уровней")
    for name in ["01_moon_low_contrast", "02_camera_low_contrast",
                 "03_camera_low_contrast_outliers", "04_coffee_dark", "06_astronaut"]:
        img = load(name)
        row = [("исходное", img), ("лин. 0 %", proc.linear_stretch(img)),
               ("лин. 1 %", proc.linear_stretch(img, 1)), ("эквализ.", proc.equalize(img, "hsv"))]
        cells = [f"{t}: {proc.stats(x)['std']:5.1f} / {proc.stats(x)['levels']:3d}" for t, x in row]
        print(f"  {name:34s}", " | ".join(cells))


def color_table():
    print("Цвет: средние (R, G, B) и медианный сдвиг тона, °")
    for name in ["04_coffee_dark", "05_chelsea_yellow_tint", "06_astronaut"]:
        img = load(name)
        print(f"  {name}: исходное {img.reshape(-1, 3).mean(0).round()}")
        for title, out in [("лин. RGB", proc.linear_stretch(img, 1, "rgb")),
                           ("лин. V", proc.linear_stretch(img, 1, "hsv")),
                           ("экв. RGB", proc.equalize(img, "rgb")),
                           ("экв. V", proc.equalize(img, "hsv"))]:
            print(f"    {title:9s} {out.reshape(-1, 3).mean(0).round()}  сдвиг {hue_shift(img, out):5.1f}")


def smoothing_table():
    print("Сглаживание: PSNR, дБ")
    camera = load("07_camera_ref")
    cases = [("гаусс. шум σ=20", load("08_camera_gauss_noise"), camera),
             ("соль-перец 5 %", load("09_camera_salt_pepper"), camera),
             ("без шума", camera, camera),
             ("цветной, σ=25", load("10_astronaut_gauss_noise"), load("06_astronaut"))]
    for title, noisy, ref in cases:
        box = " ".join(f"k{k}={proc.psnr(ref, proc.box_filter(noisy, k)):.2f}" for k in (3, 5, 7, 9, 15))
        gauss = " ".join(f"σ{s}={proc.psnr(ref, proc.gaussian_filter(noisy, s)):.2f}" for s in (0.5, 1, 1.5, 2, 3))
        print(f"  {title:16s} исходное {proc.psnr(ref, noisy):.2f} | среднее: {box} | Гаусс: {gauss}")


def frequency_response():
    print("Коэффициент передачи на решётке (теория / измерено)")
    grating = load("11_grating")
    row = grating[0].astype(float) - 127.5
    for title, kernel in [("среднее 5", proc.box_kernel(5)), ("Гаусс σ=1,5", proc.gaussian_kernel(1.5))]:
        out = proc.convolve_separable(grating, kernel)[0].astype(float) - 127.5
        cells = []
        for f in (0.1, 0.2, 0.25, 0.3, 0.4, 0.45):
            i = int(f * 2 * len(row))
            w = slice(i - 6, i + 6)
            theory = np.sum(kernel * np.cos(2 * np.pi * f * (np.arange(len(kernel)) - len(kernel) // 2)))
            cells.append(f"{f}: {theory:+.2f}/{np.dot(row[w], out[w]) / np.dot(row[w], row[w]):+.2f}")
        print(f"  {title:12s}", "  ".join(cells))


def noise_and_order():
    print("Шум при эквализации и порядок операций")
    clean, noisy = load("02_camera_low_contrast"), load("12_camera_low_contrast_noisy")
    target = proc.equalize(clean)
    print(f"  СКО шума: до {np.std(noisy - clean.astype(float)):.1f}, "
          f"после эквализации {np.std(proc.equalize(noisy) - target.astype(float)):.1f}")
    for title, out in [("только эквализация", proc.equalize(noisy)),
                       ("эквализация → Гаусс σ=1,5", proc.gaussian_filter(proc.equalize(noisy), 1.5)),
                       ("Гаусс σ=1,5 → эквализация", proc.equalize(proc.gaussian_filter(noisy, 1.5)))]:
        print(f"  {title:28s} PSNR {proc.psnr(target, out):.2f}")


def timing():
    print("Время усредняющего фильтра на 512×512, мс: разделимая свёртка / прямая двумерная")
    img = load("06_astronaut")[:, :, 0]
    for k in (3, 9, 15, 31):
        t = time.perf_counter()
        proc.box_filter(img, k)
        sep = time.perf_counter() - t
        t = time.perf_counter()
        r = k // 2
        padded = np.pad(img.astype(float), r, mode="reflect")
        sum(padded[i:i + img.shape[0], j:j + img.shape[1]] for i in range(k) for j in range(k)) / k ** 2
        full = time.perf_counter() - t
        print(f"  k={k:2d}: {sep * 1000:6.0f} / {full * 1000:6.0f}")


if __name__ == "__main__":
    for experiment in (contrast_table, color_table, smoothing_table, frequency_response, noise_and_order, timing):
        experiment()
        print()
