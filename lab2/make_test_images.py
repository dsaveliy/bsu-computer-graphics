"""Сборка тестовой базы изображений в папку images/.

Исходные снимки берутся из scikit-image (лежат внутри пакета, интернет не нужен),
искажения — шум, сжатие диапазона, затемнение, цветовой оттенок — накладываются здесь же.
Чистые версии сохраняются с суффиксом _ref: по ним считается PSNR после фильтрации.

Запуск: python make_test_images.py  (нужен пакет scikit-image, приложению он не нужен)
"""
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import data

OUT = Path(__file__).with_name("images")
rng = np.random.default_rng(2)          # фиксированное зерно — база воспроизводима


def save(name, img):
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8)).save(OUT / f"{name}.png")


def compress_range(img, low, high):
    """Сжать яркости [0, 255] в узкий диапазон [low, high] — малоконтрастный снимок."""
    return low + img.astype(float) / 255 * (high - low)


def salt_and_pepper(img, fraction):
    noisy = img.copy()
    mask = rng.random(img.shape[:2])
    noisy[mask < fraction / 2] = 0
    noisy[mask > 1 - fraction / 2] = 255
    return noisy


def gaussian_noise(img, sigma):
    return img + rng.normal(0, sigma, img.shape)


def grating(size=384):
    """Синусоидальная решётка, частота которой растёт слева направо (0 → 0,5 цикла/пиксель).

    На ней видно, какие частоты фильтр гасит, а какие пропускает или инвертирует.
    """
    x = np.arange(size)
    phase = np.pi * x ** 2 / (2 * size)  # мгновенная частота x / (2·size)
    row = 127.5 + 127.5 * np.cos(phase)
    return np.tile(row, (size // 2, 1))


def main():
    OUT.mkdir(exist_ok=True)
    camera, moon = data.camera(), data.moon()
    astronaut, coffee, chelsea = data.astronaut(), data.coffee(), data.chelsea()

    # контраст
    save("01_moon_low_contrast", moon)                                       # естественно тусклый
    save("02_camera_low_contrast", compress_range(camera, 90, 160))
    save("03_camera_low_contrast_outliers", salt_and_pepper(compress_range(camera, 90, 160), 0.002))
    save("04_coffee_dark", 255 * (coffee / 255) ** 2.2)                      # недоэкспонирован
    tinted = compress_range(chelsea, 60, 200) * np.array([1.0, 0.85, 0.55])  # жёлтый оттенок
    save("05_chelsea_yellow_tint", tinted)
    save("06_astronaut", astronaut)                                          # контрастный; эталон для 10

    # сглаживание (рядом — чистый эталон для PSNR)
    save("07_camera_ref", camera)
    save("08_camera_gauss_noise", gaussian_noise(camera, 20))
    save("09_camera_salt_pepper", salt_and_pepper(camera, 0.05))
    save("10_astronaut_gauss_noise", gaussian_noise(astronaut, 25))
    save("11_grating", grating())

    # сочетание: тусклый и шумный одновременно
    save("12_camera_low_contrast_noisy", gaussian_noise(compress_range(camera, 90, 160), 6))
    print(f"Готово: {len(list(OUT.glob('*.png')))} файлов в {OUT}")


if __name__ == "__main__":
    main()
