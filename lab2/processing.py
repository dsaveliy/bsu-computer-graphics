"""Алгоритмы обработки изображений.

Изображение — массив numpy uint8: (h, w) для полутонового или (h, w, 3) для RGB.
Все функции возвращают новый массив того же вида и не меняют входной.
"""
import numpy as np

LEVELS = 256


# --- гистограмма ---------------------------------------------------------------------------

def histogram(channel):
    """Число пикселей каждого уровня яркости 0..255."""
    return np.bincount(channel.ravel(), minlength=LEVELS)


def luminance(img):
    """Взвешенная яркость (ITU-R BT.601) — для гистограммы цветного изображения."""
    if img.ndim == 2:
        return img
    return np.round(img @ np.array([0.299, 0.587, 0.114])).astype(np.uint8)


def stats(img):
    """Минимум, максимум, среднее, СКО и число различных уровней яркости."""
    y = luminance(img)
    return {
        "min": int(y.min()), "max": int(y.max()),
        "mean": float(y.mean()), "std": float(y.std()),
        "levels": int(np.count_nonzero(histogram(y))),
    }


# --- поэлементные преобразования яркости ---------------------------------------------------

def linear_stretch_lut(channel, clip=0.0):
    """Таблица линейного контрастирования: [low, high] -> [0, 255].

    low и high — процентили clip и 100 − clip. При clip = 0 это просто min и max;
    при clip > 0 отбрасываются редкие выбросы, которые иначе «держат» диапазон.
    """
    low, high = np.percentile(channel, [clip, 100 - clip])
    if high <= low:                              # однотонный канал — растягивать нечего
        return np.arange(LEVELS, dtype=np.uint8)
    x = np.arange(LEVELS)
    return np.clip(np.round((x - low) / (high - low) * 255), 0, 255).astype(np.uint8)


def equalize_lut(channel):
    """Таблица эквализации: уровень -> нормированная накопленная гистограмма (CDF).

    Первый непустой уровень уходит в 0, последний — в 255. Отображение монотонно,
    поэтому порядок яркостей сохраняется, а растягиваются участки, где пикселей много.
    """
    cdf = np.cumsum(histogram(channel))
    cdf_min = cdf[np.nonzero(cdf)[0][0]]
    if cdf[-1] == cdf_min:                       # все пиксели одного уровня
        return np.arange(LEVELS, dtype=np.uint8)
    return np.round((cdf - cdf_min) / (cdf[-1] - cdf_min) * 255).clip(0, 255).astype(np.uint8)


def apply_to_brightness(img, make_lut, mode="rgb"):
    """Применить преобразование яркости, построенное по каналу функцией make_lut.

    mode = "rgb": таблица строится и применяется к каждому каналу R, G, B отдельно.
    mode = "hsv": меняется только V = max(R, G, B). Тон и насыщенность в HSV не зависят
    от общего множителя каналов, поэтому достаточно умножить (R, G, B) на V'/V —
    без явного перевода в HSV и обратно.
    """
    if img.ndim == 2:
        return make_lut(img)[img]
    if mode == "rgb":
        return np.stack([make_lut(img[..., c])[img[..., c]] for c in range(3)], axis=-1)
    v = img.max(axis=-1)
    new_v = make_lut(v)[v].astype(float)
    scale = np.divide(new_v, v, out=np.zeros_like(new_v), where=v > 0)
    return np.clip(np.round(img * scale[..., None]), 0, 255).astype(np.uint8)


def linear_stretch(img, clip=0.0, mode="rgb"):
    return apply_to_brightness(img, lambda ch: linear_stretch_lut(ch, clip), mode)


def equalize(img, mode="rgb"):
    return apply_to_brightness(img, equalize_lut, mode)


# --- низкочастотные (сглаживающие) фильтры -------------------------------------------------

def box_kernel(size):
    """Одномерное ядро усредняющего фильтра: size одинаковых весов."""
    return np.full(size, 1 / size)


def gaussian_kernel(sigma):
    """Одномерное ядро Гаусса радиусом 3σ (за ним остаётся < 0,3 % веса)."""
    radius = max(1, int(np.ceil(3 * sigma)))
    x = np.arange(-radius, radius + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2))
    return k / k.sum()                           # сумма весов 1 — средняя яркость не меняется


def convolve_separable(img, kernel):
    """Свёртка с ядром kernel × kernelᵀ: сначала по строкам, потом по столбцам.

    Оба фильтра разделимы, поэтому вместо k² умножений на пиксель нужно 2k.
    Края дополняются зеркальным отражением: при дополнении нулями рамка темнела бы.
    """
    r = len(kernel) // 2
    out = img.astype(float)
    for axis in (0, 1):
        pad = [(0, 0)] * out.ndim
        pad[axis] = (r, r)
        padded = np.pad(out, pad, mode="reflect")
        n = out.shape[axis]
        out = sum(w * padded.take(range(i, i + n), axis=axis) for i, w in enumerate(kernel))
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def box_filter(img, size):
    return convolve_separable(img, box_kernel(size))


def gaussian_filter(img, sigma):
    return convolve_separable(img, gaussian_kernel(sigma))


# --- оценка качества -----------------------------------------------------------------------

def psnr(reference, img):
    """Пиковое отношение сигнал/шум в дБ относительно эталона (больше — ближе к эталону)."""
    mse = np.mean((reference.astype(float) - img.astype(float)) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
