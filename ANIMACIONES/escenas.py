"""Escenas dibujadas 100% con código (Pillow + numpy). Sin imágenes externas.

Cada función recibe (ancho, alto) y devuelve una imagen RGB. Se dibujan a 4K
para que el zoom lento posterior quede nítido en 1080p.
Las coordenadas se piensan en un lienzo de 1920x1080 y se escalan con S().

Para agregar una escena nueva: escribe una función `escena_<nombre>(w, h)` y
úsala en el guion con "dibujo": "<nombre>".
"""
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

_ESCALA = 2.0


def S(v):
    return int(round(v * _ESCALA))


def P(pts):
    return [(S(x), S(y)) for x, y in pts]


# ----------------------------------------------------------------- utilidades
def fuente(tam, serif=True):
    candidatas = [
        "C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/timesbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    ] if serif else [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for c in candidatas:
        if os.path.exists(c):
            return ImageFont.truetype(c, S(tam))
    return ImageFont.load_default()


def degradado(w, h, arriba, abajo):
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(arriba, float)[None, None, :]
    b = np.array(abajo, float)[None, None, :]
    arr = (a * (1 - t) + b * t) * np.ones((1, w, 1))
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def niebla(w, h, color, fuerza=0.35, semilla=1, escala=24):
    rng = np.random.default_rng(semilla)
    peq = rng.random((max(2, h // (escala * 9)), max(2, w // (escala * 9))))
    m = Image.fromarray((peq * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    m = m.filter(ImageFilter.GaussianBlur(S(30)))
    capa = Image.new("RGB", (w, h), color)
    mask = m.point(lambda v: int(v * fuerza))
    return capa, mask


def aplicar_niebla(img, color, fuerza=0.35, semilla=1):
    capa, mask = niebla(img.width, img.height, color, fuerza, semilla)
    img.paste(capa, (0, 0), mask)
    return img


def resplandor(img, dibujar, color, radio, intensidad=1.0):
    """Dibuja una forma con `dibujar(draw)` y la suma difuminada (luz)."""
    capa = Image.new("RGB", img.size, (0, 0, 0))
    dibujar(ImageDraw.Draw(capa), color)
    glow = capa.filter(ImageFilter.GaussianBlur(radio))
    if intensidad != 1.0:
        glow = glow.point(lambda v: min(255, int(v * intensidad)))
    return ImageChops.add(ImageChops.add(img, glow), capa.filter(ImageFilter.GaussianBlur(2)))


def oscurecer_bordes(img, fuerza=0.75):
    w, h = img.size
    y, x = np.ogrid[:h, :w]
    d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    m = np.clip(1 - fuerza * (d / 1.25) ** 2, 0, 1)
    arr = np.asarray(img).astype(float) * m[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def silueta(d, cx, base_y, alto, color, brazos=True, inclinacion=0):
    """Figura alta y delgada sin rostro. cx/base_y en coords 1920x1080."""
    a = alto
    cab_r = a * 0.055
    cab_y = base_y - a + cab_r
    hx = cx + inclinacion
    d.ellipse([S(hx - cab_r * 0.85), S(cab_y - cab_r * 1.1),
               S(hx + cab_r * 0.85), S(cab_y + cab_r * 1.1)], fill=color)
    cuello = cab_y + cab_r
    hombro = cuello + a * 0.05
    cuerpo = [
        (hx - a * 0.018, cuello), (hx + a * 0.018, cuello),
        (cx + a * 0.11, hombro), (cx + a * 0.085, base_y - a * 0.42),
        (cx + a * 0.06, base_y), (cx + a * 0.02, base_y),
        (cx, base_y - a * 0.38), (cx - a * 0.02, base_y),
        (cx - a * 0.06, base_y), (cx - a * 0.085, base_y - a * 0.42),
        (cx - a * 0.11, hombro),
    ]
    d.polygon(P(cuerpo), fill=color)
    if brazos:
        for lado in (-1, 1):
            br = [
                (cx + lado * a * 0.10, hombro), (cx + lado * a * 0.125, hombro + a * 0.02),
                (cx + lado * a * 0.15, base_y - a * 0.28), (cx + lado * a * 0.16, base_y - a * 0.12),
                (cx + lado * a * 0.135, base_y - a * 0.12), (cx + lado * a * 0.12, base_y - a * 0.28),
                (cx + lado * a * 0.085, hombro + a * 0.06),
            ]
            d.polygon(P(br), fill=color)
            # dedos largos
            for k in range(4):
                fx = cx + lado * a * (0.137 + k * 0.007)
                d.line(P([(fx, base_y - a * 0.125), (fx + lado * a * 0.01 * (k - 1), base_y - a * 0.04)]),
                       fill=color, width=S(a * 0.006) + 1)


def ventana(img, x, y, w, h, luz=(150, 175, 230), luna=True):
    def forma(d, c):
        d.rectangle([S(x), S(y), S(x + w), S(y + h)], fill=c)
    img = resplandor(img, forma, tuple(int(v * 0.55) for v in luz), S(70))
    d = ImageDraw.Draw(img)
    d.rectangle([S(x), S(y), S(x + w), S(y + h)], fill=tuple(int(v * 0.45) for v in luz))
    if luna:
        img = resplandor(img, lambda dd, c: dd.ellipse([S(x + w * 0.55), S(y + h * 0.15),
                                                        S(x + w * 0.55 + 70), S(y + h * 0.15 + 70)], fill=c),
                         (235, 240, 255), S(35))
        d = ImageDraw.Draw(img)
    marco = (8, 10, 18)
    d.rectangle([S(x), S(y), S(x + w), S(y + h)], outline=marco, width=S(14))
    d.line([S(x + w / 2), S(y), S(x + w / 2), S(y + h)], fill=marco, width=S(10))
    d.line([S(x), S(y + h / 2), S(x + w), S(y + h / 2)], fill=marco, width=S(10))
    # ramas secas detrás del vidrio
    rnd = random.Random(7)
    for _ in range(5):
        x0, y0 = x + rnd.random() * w, y + h
        for _ in range(4):
            x1, y1 = x0 + rnd.uniform(-60, 60), y0 - rnd.uniform(40, 110)
            d.line([S(x0), S(y0), S(x1), S(y1)], fill=(12, 14, 24), width=S(4))
            x0, y0 = x1, y1
    return img


def haz_de_luz(img, pts, color=(120, 140, 200), fuerza=70):
    capa = Image.new("L", img.size, 0)
    ImageDraw.Draw(capa).polygon(P(pts), fill=fuerza)
    capa = capa.filter(ImageFilter.GaussianBlur(S(40)))
    img.paste(Image.new("RGB", img.size, color), (0, 0), capa)
    return img


def cama_vista(d, tinte=1.0, colores=None):
    c = colores or {"cab": (14, 14, 22), "col": (34, 38, 58), "man": (46, 52, 78), "alm": (60, 66, 92)}
    d.rectangle(P([(1050, 560), (1800, 640)]), fill=c["cab"])
    d.polygon(P([(1000, 700), (1850, 700), (1920, 1080), (900, 1080)]), fill=c["col"])
    d.ellipse(P([(1120, 600), (1420, 720)]), fill=c["alm"])
    d.ellipse(P([(1450, 600), (1750, 720)]), fill=c["alm"])
    d.polygon(P([(980, 760), (1880, 760), (1940, 1080), (880, 1080)]), fill=c["man"])
    for i in range(5):
        d.arc(P([(1000 + i * 150, 780), (1250 + i * 150, 900)]), 200, 340, fill=c["col"], width=S(6))


def mesita(d, x=820, y=760, color=(18, 18, 28)):
    d.rectangle(P([(x, y), (x + 170, y + 320)]), fill=color)
    d.rectangle(P([(x - 10, y - 15), (x + 180, y + 5)]), fill=tuple(c + 6 for c in color))


# --------------------------------------------------------------------- escenas
def escena_titulo(w, h):
    img = degradado(w, h, (4, 4, 10), (14, 10, 22))
    img = aplicar_niebla(img, (60, 55, 85), 0.45, 3)
    d = ImageDraw.Draw(img)
    f = fuente(130)
    txt = "PARÁLISIS DEL SUEÑO"
    bw = d.textbbox((0, 0), txt, font=f)
    x = (w - (bw[2] - bw[0])) // 2

    def t(dd, c):
        dd.text((x, S(390)), txt, font=f, fill=c)
    img = resplandor(img, t, (150, 20, 25), S(25))
    d = ImageDraw.Draw(img)
    d.text((x, S(390)), txt, font=f, fill=(225, 215, 210))
    f2 = fuente(52, serif=False)
    sub = "3:33 AM"
    bw = d.textbbox((0, 0), sub, font=f2)
    d.text(((w - (bw[2] - bw[0])) // 2, S(600)), sub, font=f2, fill=(170, 30, 35))
    return oscurecer_bordes(img, 0.9)


def _cuarto(w, h, noche=True, puerta_abierta=0.0, figura=False):
    if noche:
        img = degradado(w, h, (10, 12, 24), (4, 5, 10))
    else:
        img = degradado(w, h, (120, 105, 95), (60, 52, 50))
    d = ImageDraw.Draw(img)
    piso = (6, 6, 12) if noche else (55, 45, 40)
    d.polygon(P([(0, 820), (1920, 820), (1920, 1080), (0, 1080)]), fill=piso)
    # puerta a la izquierda
    marco = (3, 3, 8) if noche else (40, 32, 30)
    hoja = (16, 16, 28) if noche else (95, 80, 70)
    d.rectangle(P([(170, 230), (540, 830)]), fill=marco)
    abertura = 330 * puerta_abierta
    d.rectangle(P([(185, 245), (525, 830)]), fill=(0, 0, 0) if noche else (30, 25, 25))
    d.polygon(P([(185 + abertura, 245), (525, 230), (525, 830), (185 + abertura, 815)]), fill=hoja)
    d.ellipse(P([(200 + abertura, 520), (225 + abertura, 545)]), fill=(40, 40, 50) if noche else (150, 130, 90))
    if figura:
        silueta(d, 185 + abertura * 0.5, 830, 560, (0, 0, 0), brazos=False)
    # ventana
    if noche:
        img = ventana(img, 1250, 200, 420, 330)
        img = haz_de_luz(img, [(1250, 530), (1670, 530), (1500, 1080), (700, 1080)])
    else:
        img = ventana(img, 1250, 200, 420, 330, luz=(255, 215, 160), luna=False)
        img = haz_de_luz(img, [(1250, 530), (1670, 530), (1500, 1080), (700, 1080)], (255, 200, 140), 90)
    d = ImageDraw.Draw(img)
    if noche:
        cama_vista(d)
    else:
        cama_vista(d, colores={"cab": (60, 45, 40), "col": (130, 115, 110),
                               "man": (165, 150, 140), "alm": (190, 180, 170)})
    mesita(d, color=(18, 18, 28) if noche else (70, 55, 45))
    reloj = (180, 20, 20) if noche else (110, 40, 30)
    d.rectangle(P([(860, 700), (950, 745)]), fill=(10, 10, 12))
    d.text((S(868), S(703)), "3:33", font=fuente(30, serif=False), fill=reloj)
    img = aplicar_niebla(img, (40, 45, 70) if noche else (170, 150, 130), 0.18, 5)
    return oscurecer_bordes(img, 0.85 if noche else 0.55)


def escena_dormitorio(w, h):
    return _cuarto(w, h)


def escena_reloj(w, h):
    img = degradado(w, h, (6, 6, 12), (2, 2, 5))
    d = ImageDraw.Draw(img)
    d.polygon(P([(250, 640), (1670, 640), (1920, 1080), (0, 1080)]), fill=(16, 13, 16))
    d.rounded_rectangle(P([(560, 330), (1360, 690)]), radius=S(40), fill=(12, 12, 14))
    d.rounded_rectangle(P([(610, 380), (1310, 640)]), radius=S(20), fill=(4, 2, 2))
    f = fuente(230, serif=False)

    def num(dd, c):
        dd.text((S(700), S(375)), "3:33", font=f, fill=c)
    img = resplandor(img, num, (230, 25, 20), S(45), 1.3)
    d = ImageDraw.Draw(img)
    d.text((S(1245), S(395)), "AM", font=fuente(34, serif=False), fill=(150, 20, 20))
    # reflejo rojo en la mesa
    img = haz_de_luz(img, [(560, 700), (1360, 700), (1500, 1000), (420, 1000)], (120, 10, 10), 60)
    return oscurecer_bordes(img, 0.95)


def escena_puerta(w, h):
    img = degradado(w, h, (9, 10, 20), (3, 3, 7))
    d = ImageDraw.Draw(img)
    d.polygon(P([(0, 900), (1920, 900), (1920, 1080), (0, 1080)]), fill=(5, 5, 10))
    d.rectangle(P([(660, 90), (1260, 910)]), fill=(2, 2, 6))
    d.rectangle(P([(690, 120), (1230, 910)]), fill=(0, 0, 0))
    d.polygon(P([(820, 125), (1230, 110), (1230, 910), (820, 890)]), fill=(20, 20, 34))
    for y in (220, 520):
        d.rectangle(P([(870, y), (1180, y + 230)]), outline=(14, 14, 24), width=S(8))
    d.ellipse(P([(835, 500), (865, 530)]), fill=(55, 55, 70))
    img = haz_de_luz(img, [(1300, 0), (1920, 0), (1920, 1080), (1150, 1080)], (90, 110, 170), 45)
    img = aplicar_niebla(img, (35, 40, 65), 0.2, 9)
    return oscurecer_bordes(img, 0.9)


def escena_figura_puerta(w, h):
    img = escena_puerta(w, h)
    d = ImageDraw.Draw(img)
    # borde de luz tenue alrededor para que la silueta "se lea"
    img = resplandor(img, lambda dd, c: silueta(dd, 755, 905, 760, c, brazos=False), (28, 30, 48), S(18))
    d = ImageDraw.Draw(img)
    silueta(d, 755, 905, 760, (0, 0, 0), brazos=False)
    d.polygon(P([(820, 125), (1230, 110), (1230, 910), (820, 890)]), fill=(20, 20, 34))
    for y in (220, 520):
        d.rectangle(P([(870, y), (1180, y + 230)]), outline=(14, 14, 24), width=S(8))
    return img


def escena_figura_cama(w, h):
    img = degradado(w, h, (16, 20, 38), (6, 7, 14))
    img = ventana(img, 760, 120, 400, 320)
    img = haz_de_luz(img, [(760, 440), (1160, 440), (1500, 900), (420, 900)], (110, 130, 190), 80)
    d = ImageDraw.Draw(img)
    silueta(d, 960, 860, 820, (0, 0, 0), inclinacion=25)
    # pies de la cama (POV): bultos de la frazada
    d.polygon(P([(0, 760), (1920, 760), (1920, 1080), (0, 1080)]), fill=(24, 27, 44))
    d.ellipse(P([(520, 700), (900, 900)]), fill=(30, 34, 54))
    d.ellipse(P([(1020, 700), (1400, 900)]), fill=(30, 34, 54))
    d.polygon(P([(0, 900), (1920, 900), (1920, 1080), (0, 1080)]), fill=(20, 22, 36))
    img = aplicar_niebla(img, (50, 55, 85), 0.18, 11)
    return oscurecer_bordes(img, 1.0)


def escena_presion(w, h):
    img = degradado(w, h, (20, 6, 8), (4, 2, 3))
    d = ImageDraw.Draw(img)
    # masa oscura que se inclina desde arriba
    d.ellipse(P([(560, -420), (1360, 520)]), fill=(0, 0, 0))
    d.ellipse(P([(820, 180), (1100, 520)]), fill=(0, 0, 0))
    # dedos largos entrando por los lados
    for lado, x0 in ((1, -40), (-1, 1960)):
        for k in range(5):
            y = 420 + k * 70
            pts = [(x0, y), (x0 + lado * 380, y + 30), (x0 + lado * 520, y + 70 + k * 6)]
            d.line(P(pts), fill=(0, 0, 0), width=S(26 - k * 2), joint="curve")
    img = img.filter(ImageFilter.GaussianBlur(S(4)))
    img = aplicar_niebla(img, (90, 10, 15), 0.25, 13)
    return oscurecer_bordes(img, 1.1)


def escena_ojos(w, h):
    img = Image.new("RGB", (w, h), (2, 1, 2))
    d = ImageDraw.Draw(img)
    d.ellipse(P([(560, 80), (1360, 1200)]), fill=(9, 7, 9))

    def ojos(dd, c):
        for cx in (790, 1130):
            dd.ellipse(P([(cx - 85, 470), (cx + 85, 560)]), fill=c)
    img = resplandor(img, ojos, (235, 235, 225), S(40), 1.2)
    d = ImageDraw.Draw(img)
    for cx in (790, 1130):
        d.ellipse(P([(cx - 9, 506), (cx + 9, 524)]), fill=(0, 0, 0))
        for k in range(7):  # venas
            ang = k * 0.9
            d.line(P([(cx + 80 * np.cos(ang), 515 + 40 * np.sin(ang)),
                      (cx + 45 * np.cos(ang + 0.2), 515 + 22 * np.sin(ang + 0.2))]),
                   fill=(150, 30, 30), width=S(2))
    return oscurecer_bordes(img, 0.8)


def escena_amanecer(w, h):
    return _cuarto(w, h, noche=False)


def escena_sabanas(w, h):
    img = degradado(w, h, (150, 145, 145), (90, 85, 88))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    for i in range(14):  # pliegues
        y = 60 + i * 75 + rnd.uniform(-20, 20)
        d.arc(P([(-200 + rnd.uniform(-80, 80), y), (2100, y + 260)]), 190, 350,
              fill=(110, 105, 108), width=S(rnd.uniform(6, 16)))
    img = img.filter(ImageFilter.GaussianBlur(S(9)))
    # marcas de dedos largos
    capa = Image.new("L", img.size, 0)
    dc = ImageDraw.Draw(capa)
    for k, (x, ang) in enumerate([(700, -0.18), (820, -0.06), (940, 0.05), (1060, 0.16)]):
        L = 520 - abs(k - 1.5) * 60
        x2, y2 = x + np.sin(ang) * L, 300 + np.cos(ang) * L
        dc.line(P([(x, 300), (x2, y2)]), fill=200, width=S(34))
        dc.ellipse(P([(x2 - 17, y2 - 17), (x2 + 17, y2 + 17)]), fill=200)
    capa = capa.filter(ImageFilter.GaussianBlur(S(10)))
    img.paste(Image.new("RGB", img.size, (45, 30, 30)), (0, 0), capa)
    return oscurecer_bordes(img, 0.9)


def escena_final(w, h):
    img = Image.new("RGB", (w, h), (2, 2, 4))
    img = aplicar_niebla(img, (30, 25, 40), 0.35, 21)
    d = ImageDraw.Draw(img)
    f = fuente(120)
    txt = "NO ABRAS LOS OJOS"
    bw = d.textbbox((0, 0), txt, font=f)
    x = (w - (bw[2] - bw[0])) // 2

    def t(dd, c):
        dd.text((x, S(440)), txt, font=f, fill=c)
    img = resplandor(img, t, (140, 15, 20), S(30))
    d = ImageDraw.Draw(img)
    d.text((x, S(440)), txt, font=f, fill=(200, 190, 185))
    for cx in (900, 1020):
        d.ellipse(P([(cx - 14, 250), (cx + 14, 262)]), fill=(120, 120, 115))
    return oscurecer_bordes(img, 0.9)


def dibujar(nombre, w=3840, h=2160):
    global _ESCALA
    _ESCALA = w / 1920
    fn = globals().get(f"escena_{nombre}")
    if fn is None:
        raise SystemExit(f"No existe la escena '{nombre}'. Disponibles: "
                         + ", ".join(k[7:] for k in globals() if k.startswith("escena_")))
    return fn(w, h)


if __name__ == "__main__":  # vista previa rápida: python escenas.py
    os.makedirs("previas", exist_ok=True)
    for k in [k for k in list(globals()) if k.startswith("escena_")]:
        dibujar(k[7:], 1920, 1080).save(f"previas/{k[7:]}.png")
        print("ok", k)
