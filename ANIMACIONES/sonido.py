"""Música y efectos de sonido de terror generados con código (numpy + scipy).

Nada se descarga: todo es síntesis. Cada efecto devuelve un array estéreo
(n, 2) float32 a 48 kHz que luego se coloca en la línea de tiempo.
"""
import numpy as np
from scipy import signal

SR = 48000
_rng = np.random.default_rng(33)


def _t(d):
    return np.arange(int(d * SR)) / SR


def estereo(x, pan=0.0):
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * l * 1.414, x * r * 1.414], axis=1).astype(np.float32)


def filtro(x, tipo, f, orden=2):
    sos = signal.butter(orden, f, btype=tipo, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def ruido(d, color="blanco"):
    x = _rng.standard_normal(int(d * SR))
    if color == "marron":
        x = np.cumsum(x)
        x = filtro(x, "highpass", 20)
        x /= np.abs(x).max() + 1e-9
    return x


def reverb(x, seg=1.8, mezcla=0.35):
    """Reverb por convolución con una cola de ruido que decae."""
    n = int(seg * SR)
    cola = _rng.standard_normal((n, 2)) * np.exp(-np.linspace(0, 7, n))[:, None]
    cola = filtro(cola, "lowpass", 5000)
    cola /= np.sqrt((cola ** 2).sum(axis=0))
    mojado = np.stack([signal.fftconvolve(x[:, c], cola[:, c])[: len(x)] for c in range(2)], axis=1)
    return (x * (1 - mezcla) + mojado * mezcla * 3).astype(np.float32)


# ------------------------------------------------------------------ efectos
def latido(d, bpm0=70, bpm1=110):
    out = np.zeros(int(d * SR))
    t, k = 0.0, 0
    while t < d - 0.4:
        for off, amp in ((0, 1.0), (0.16, 0.7)):
            tt = _t(0.25)
            golpe = np.sin(2 * np.pi * (48 + 30 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 18) * amp
            i = int((t + off) * SR)
            out[i:i + len(golpe)] += golpe[: len(out) - i]
        bpm = bpm0 + (bpm1 - bpm0) * (t / d)
        t += 60 / bpm
        k += 1
    return estereo(out * 0.9)


def tictac(d):
    out = np.zeros(int(d * SR))
    for k in range(int(d)):
        tt = _t(0.03)
        clic = filtro(_rng.standard_normal(len(tt)), "bandpass", [2500, 6000]) * np.exp(-tt * 250)
        i = int(k * SR)
        out[i:i + len(clic)] += clic * (0.5 if k % 2 else 0.35)
    return estereo(out, 0.3)


def crujido(d=1.6):
    """Bisagra de puerta: tren de impulsos de frecuencia variable por resonadores."""
    n = int(d * SR)
    tt = np.arange(n) / SR
    f = 18 + 70 * np.abs(np.sin(tt * 2.1)) + 25 * np.sin(tt * 13) ** 2
    fase = np.cumsum(f / SR)
    tren = (np.diff(np.floor(fase), prepend=0) > 0).astype(float)
    tren *= 0.6 + 0.4 * _rng.random(n)
    out = 0
    for fc, q in ((650, 30), (1300, 25), (2100, 20)):
        b, a = signal.iirpeak(fc, q, fs=SR)
        out = out + signal.lfilter(b, a, tren)
    env = np.minimum(1, tt / 0.1) * np.minimum(1, (d - tt) / 0.3)
    return estereo(out * env * 0.9, -0.4)


def pasos(n=2, sep=0.55):
    out = np.zeros(int((n * sep + 0.5) * SR))
    for k in range(n):
        tt = _t(0.35)
        g = filtro(_rng.standard_normal(len(tt)), "lowpass", 300) * np.exp(-tt * 14)
        g += np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 20) * 0.6
        i = int(k * sep * SR)
        out[i:i + len(g)] += g
    return estereo(out * 1.2, 0.1)


def susurro(d=2.5, pan=0.6):
    x = filtro(ruido(d), "bandpass", [1800, 7000], 3)
    tt = _t(d)
    silabas = np.clip(np.sin(2 * np.pi * (4.5 + 2 * np.sin(tt * 1.3)) * tt), 0, None) ** 2
    env = silabas * np.minimum(1, tt / 0.3) * np.minimum(1, (d - tt) / 0.5)
    return estereo(x * env * 0.35, pan)


def respiracion(d=3.0):
    x = filtro(ruido(d), "bandpass", [300, 2500])
    tt = _t(d)
    env = np.clip(np.sin(2 * np.pi * tt / 1.6), 0, None) ** 1.5
    return estereo(x * env * 0.3, -0.2)


def subida(d=2.5):
    """Tensión creciente (riser) que termina de golpe."""
    tt = _t(d)
    x = filtro(ruido(d), "highpass", 800) * (tt / d) ** 2 * 0.5
    f = 150 + 1100 * (tt / d) ** 2
    x += np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / d) ** 1.5 * 0.35
    x += np.sin(2 * np.pi * np.cumsum(f * 1.06) / SR) * (tt / d) ** 1.5 * 0.25
    return estereo(x)


def golpe(d=3.0):
    """Impacto del susto: bajo profundo + ruido + chirrido disonante."""
    tt = _t(d)
    sub = np.sin(2 * np.pi * (38 + 60 * np.exp(-tt * 8)) * tt) * np.exp(-tt * 1.3) * 1.2
    rui = filtro(ruido(d), "lowpass", 6000) * np.exp(-tt * 5) * 0.6
    chir = sum(np.sin(2 * np.pi * (f + 25 * np.sin(tt * 40)) * tt) for f in (1180, 1250, 1333, 1410))
    chir = chir * np.exp(-tt * 2.2) * 0.12
    return reverb(estereo(sub + rui + chir), 2.5, 0.3)


def braam(d=3.5):
    """Golpe grave de tráiler para el gancho."""
    tt = _t(d)
    x = signal.sawtooth(2 * np.pi * 55 * tt) + signal.sawtooth(2 * np.pi * 55.7 * tt)
    x = filtro(x, "lowpass", 600) * np.exp(-tt * 1.1) * np.minimum(1, tt / 0.02)
    return reverb(estereo(x * 0.5), 2.0, 0.3)


def silbido(d=0.45):
    """Whoosh corto para los cortes."""
    tt = _t(d)
    x = ruido(d)
    sos = signal.butter(2, [600, 3000], btype="bandpass", fs=SR, output="sos")
    x = signal.sosfilt(sos, x) * np.sin(np.pi * tt / d) ** 2
    return estereo(x * 0.25)


EFECTOS = {
    "latido": latido, "tictac": tictac, "crujido": crujido, "pasos": pasos,
    "susurro": susurro, "respiracion": respiracion, "subida": subida,
    "golpe": golpe, "braam": braam, "silbido": silbido,
}


# ------------------------------------------------------------------- música
def _nota(f, d=3.0, vol=0.3):
    tt = _t(d)
    x = sum((1 / k ** 1.6) * np.sin(2 * np.pi * f * k * tt) * np.exp(-tt * (1.2 + 0.9 * k)) for k in range(1, 7))
    return x * np.minimum(1, tt / 0.004) * vol


def musica(total, niveles):
    """Fondo continuo: drone grave + piano lúgubre en La menor con notas disonantes.

    niveles: función(t) -> 0..1 para el volumen de la música en cada instante.
    """
    n = int(total * SR)
    tt = np.arange(n) / SR
    dron = (np.sin(2 * np.pi * 55 * tt) * 0.5 + np.sin(2 * np.pi * 82.4 * tt) * 0.3
            + np.sin(2 * np.pi * 110.6 * tt) * 0.2)  # 110.6: levemente desafinado
    dron *= 0.55 + 0.45 * np.sin(2 * np.pi * tt / 7.0)
    dron += filtro(ruido(total, "marron"), "lowpass", 250) * 0.8
    izq, der = dron.copy(), dron.copy()
    melodia = [220.0, 261.6, 329.6, 311.1, 220.0, 246.9, 174.6, 207.7]  # A C E D# A B F G#
    paso, i = 1.7, 0
    t = 0.6
    while t < total - 1:
        nota = _nota(melodia[i % len(melodia)], 3.0, 0.22)
        if i % 4 == 3:
            nota += _nota(melodia[i % len(melodia)] * 2.12, 3.0, 0.06)  # golpe disonante
        a = int(t * SR)
        m = min(len(nota), n - a)
        pan = 0.3 * np.sin(i)
        izq[a:a + m] += nota[:m] * (1 - pan)
        der[a:a + m] += nota[:m] * (1 + pan)
        t += paso
        i += 1
    est = reverb(np.stack([izq, der], axis=1).astype(np.float32), 2.8, 0.45)
    vol = np.array([niveles(x) for x in np.arange(0, total, 0.05)])
    vol = np.interp(tt, np.arange(len(vol)) * 0.05, vol)
    return (est * vol[:, None] * 0.35).astype(np.float32)


def colocar(pista, sonido, t0, vol=1.0):
    i = int(t0 * SR)
    if i >= len(pista):
        return
    m = min(len(sonido), len(pista) - i)
    pista[i:i + m] += sonido[:m] * vol
