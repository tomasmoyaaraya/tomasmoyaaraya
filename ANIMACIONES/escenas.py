"""Escenas dibujadas 100% con código (Pillow + numpy). Sin imágenes externas.

Se dibujan a 4K (3840x2160) pensando en un lienzo de 1920x1080 (coordenadas
escaladas con S()). De ese 4K la cámara recorta tanto un encuadre horizontal
(16:9) como uno vertical (9:16) para Shorts/TikTok, con zoom y paneo.

Dos tipos de escena:
  * estática:  def escena_<nombre>(w, h) -> Image
  * animada:   def anim_<nombre>(w, h) -> función(p, t) -> Image
               (p = progreso 0..1 de la toma, t = segundos desde que empezó)

En el guion se usa "dibujo": "<nombre>" y se busca primero la animada.
Vista previa de todo:  python escenas.py
"""
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

_ESCALA = 2.0
AQUI = os.path.dirname(os.path.abspath(__file__))


def S(v):
    return int(round(v * _ESCALA))


def P(pts):
    return [(S(x), S(y)) for x, y in pts]


def suave(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def tramo(p, a, b):
    """0 antes de a, 1 después de b, suave entre medio."""
    return suave((p - a) / max(1e-6, b - a))


# ----------------------------------------------------------------- utilidades
def fuente(tam, serif=True, px=False):
    candidatas = [
        "C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/timesbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    ] if serif else [
        os.path.join(AQUI, "fuentes", "Inter-Black.otf"),
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidatas:
        if os.path.exists(c):
            return ImageFont.truetype(c, int(tam) if px else S(tam))
    return ImageFont.load_default()


def degradado(w, h, arriba, abajo):
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(arriba, float)[None, None, :]
    b = np.array(abajo, float)[None, None, :]
    arr = (a * (1 - t) + b * t) * np.ones((1, w, 1))
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def aplicar_niebla(img, color, fuerza=0.35, semilla=1, escala=24):
    w, h = img.size
    rng = np.random.default_rng(semilla)
    peq = rng.random((max(2, h // (escala * 9)), max(2, w // (escala * 9))))
    m = Image.fromarray((peq * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    m = m.filter(ImageFilter.GaussianBlur(S(30))).point(lambda v: int(v * fuerza))
    img.paste(Image.new("RGB", (w, h), color), (0, 0), m)
    return img


def resplandor(img, dibujar, color, radio, intensidad=1.0):
    """Dibuja una forma con `dibujar(draw, color)` y la suma difuminada (luz)."""
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
    arr = np.asarray(img).astype(np.float32) * m[..., None]
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
        (cx + a * 0.10, hombro), (cx + a * 0.075, base_y - a * 0.45),
        (cx + a * 0.05, base_y), (cx + a * 0.018, base_y),
        (cx, base_y - a * 0.38), (cx - a * 0.018, base_y),
        (cx - a * 0.05, base_y), (cx - a * 0.075, base_y - a * 0.45),
        (cx - a * 0.10, hombro),
    ]
    d.polygon(P(cuerpo), fill=color)
    if brazos:
        for lado in (-1, 1):
            br = [
                (cx + lado * a * 0.09, hombro), (cx + lado * a * 0.115, hombro + a * 0.02),
                (cx + lado * a * 0.135, base_y - a * 0.30), (cx + lado * a * 0.14, base_y - a * 0.16),
                (cx + lado * a * 0.118, base_y - a * 0.16), (cx + lado * a * 0.108, base_y - a * 0.30),
                (cx + lado * a * 0.075, hombro + a * 0.06),
            ]
            d.polygon(P(br), fill=color)
            for k in range(4):  # dedos largos y finos
                fx = cx + lado * a * (0.118 + k * 0.007)
                d.line(P([(fx, base_y - a * 0.165), (fx + lado * a * 0.012 * (k - 1), base_y - a * 0.07)]),
                       fill=color, width=max(1, S(a * 0.005)))


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
    rnd = random.Random(7)  # ramas secas detrás del vidrio
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


def cama_vista(d, colores=None):
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
    f = fuente(70)
    for i, txt in enumerate(["PARÁLISIS", "DEL SUEÑO"]):
        bw = d.textbbox((0, 0), txt, font=f)
        x = (w - (bw[2] - bw[0])) // 2
        y = S(400 + i * 95)
        img = resplandor(img, lambda dd, c: dd.text((x, y), txt, font=f, fill=c), (150, 20, 25), S(25))
        d = ImageDraw.Draw(img)
        d.text((x, y), txt, font=f, fill=(225, 215, 210))
    return oscurecer_bordes(img, 0.9)


def _cuarto(w, h, noche=True):
    img = degradado(w, h, (10, 12, 24), (4, 5, 10)) if noche else degradado(w, h, (120, 105, 95), (60, 52, 50))
    d = ImageDraw.Draw(img)
    d.polygon(P([(0, 820), (1920, 820), (1920, 1080), (0, 1080)]), fill=(6, 6, 12) if noche else (55, 45, 40))
    marco = (3, 3, 8) if noche else (40, 32, 30)
    hoja = (16, 16, 28) if noche else (95, 80, 70)
    d.rectangle(P([(170, 230), (540, 830)]), fill=marco)
    d.rectangle(P([(185, 245), (525, 830)]), fill=hoja)
    d.ellipse(P([(200, 520), (225, 545)]), fill=(40, 40, 50) if noche else (150, 130, 90))
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
        cama_vista(d, {"cab": (60, 45, 40), "col": (130, 115, 110), "man": (165, 150, 140), "alm": (190, 180, 170)})
    mesita(d, color=(18, 18, 28) if noche else (70, 55, 45))
    d.rectangle(P([(860, 700), (950, 745)]), fill=(10, 10, 12))
    d.text((S(868), S(703)), "3:33", font=fuente(30, serif=False), fill=(180, 20, 20) if noche else (110, 40, 30))
    img = aplicar_niebla(img, (40, 45, 70) if noche else (170, 150, 130), 0.18, 5)
    return oscurecer_bordes(img, 0.85 if noche else 0.55)


def escena_dormitorio(w, h):
    return _cuarto(w, h)


def escena_amanecer(w, h):
    return _cuarto(w, h, noche=False)


def escena_reloj(w, h, hora="3:33"):
    img = degradado(w, h, (6, 6, 12), (2, 2, 5))
    d = ImageDraw.Draw(img)
    d.polygon(P([(250, 640), (1670, 640), (1920, 1080), (0, 1080)]), fill=(16, 13, 16))
    d.rounded_rectangle(P([(680, 380), (1240, 660)]), radius=S(34), fill=(12, 12, 14))
    d.rounded_rectangle(P([(715, 415), (1205, 625)]), radius=S(18), fill=(4, 2, 2))
    f = fuente(165, serif=False)
    bw = d.textbbox((0, 0), hora, font=f)
    x = (w - (bw[2] - bw[0])) // 2 - bw[0]
    img = resplandor(img, lambda dd, c: dd.text((x, S(418)), hora, font=f, fill=c), (230, 25, 20), S(45), 1.3)
    d = ImageDraw.Draw(img)
    d.text((S(1160), S(428)), "AM", font=fuente(24, serif=False), fill=(150, 20, 20))
    img = haz_de_luz(img, [(680, 680), (1240, 680), (1400, 1000), (520, 1000)], (120, 10, 10), 60)
    return oscurecer_bordes(img, 0.95)


def anim_reloj_cambia(w, h):
    a, b = escena_reloj(w, h, "3:32"), escena_reloj(w, h, "3:33")
    return lambda p, t: b if p > 0.55 else a


def escena_puerta(w, h, apertura=1.0, figura=0.0):
    """apertura 0 = cerrada, 1 = entreabierta. figura 0..1 = opacidad de la silueta."""
    img = degradado(w, h, (9, 10, 20), (3, 3, 7))
    d = ImageDraw.Draw(img)
    d.polygon(P([(0, 900), (1920, 900), (1920, 1080), (0, 1080)]), fill=(5, 5, 10))
    d.rectangle(P([(660, 90), (1260, 910)]), fill=(2, 2, 6))
    d.rectangle(P([(690, 120), (1230, 910)]), fill=(0, 0, 0))
    pas = degradado(S(540), S(790), (10, 12, 22), (34, 38, 62))
    img.paste(pas, (S(690), S(120)))
    img = resplandor(img, lambda dd, c: dd.ellipse(P([(820, 300), (1000, 700)]), fill=c), (40, 45, 75), S(60))
    d = ImageDraw.Draw(img)
    if figura > 0:
        # halo frío alrededor (se suma) + silueta negra encima, ambos con opacidad `figura`
        halo = Image.new("L", img.size, 0)
        silueta(ImageDraw.Draw(halo), 760, 905, 760, 255, brazos=False)
        forma = halo.copy()
        halo = halo.filter(ImageFilter.GaussianBlur(S(16))).point(lambda v: int(v * 0.35 * figura))
        img.paste(Image.new("RGB", img.size, (90, 98, 150)), (0, 0), halo)
        img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), forma.point(lambda v: int(v * figura)))
        d = ImageDraw.Draw(img)
    x0 = 695 + 130 * apertura
    d.polygon(P([(x0, 122 + 3 * apertura), (1230, 110), (1230, 910), (x0, 908 - 18 * apertura)]),
              fill=(20, 20, 34))
    ancho = 1230 - x0
    for y in (220, 520):
        d.rectangle(P([(x0 + ancho * 0.12, y), (x0 + ancho * 0.88, y + 230)]), outline=(14, 14, 24), width=S(8))
    d.ellipse(P([(x0 + 15, 500), (x0 + 45, 530)]), fill=(55, 55, 70))
    img = haz_de_luz(img, [(1300, 0), (1920, 0), (1920, 1080), (1150, 1080)], (90, 110, 170), 45)
    img = aplicar_niebla(img, (35, 40, 65), 0.2, 9)
    return oscurecer_bordes(img, 0.9)


def _cache_por_pasos(fn, pasos):
    cache = {}

    def f(v):
        k = round(v * pasos) / pasos
        if k not in cache:
            cache[k] = fn(k)
        return cache[k]
    return f


def anim_puerta_abre(w, h):
    get = _cache_por_pasos(lambda a: escena_puerta(w, h, apertura=a), 24)
    return lambda p, t: get(tramo(p, 0.08, 0.85))


def escena_figura_puerta(w, h):
    return escena_puerta(w, h, figura=1.0)


def anim_figura_aparece(w, h):
    a, b = escena_puerta(w, h, figura=0.0), escena_puerta(w, h, figura=1.0)
    return lambda p, t: Image.blend(a, b, tramo(p, 0.05, 0.6))


def escena_figura_cama(w, h, tam=1.0):
    img = degradado(w, h, (16, 20, 38), (6, 7, 14))
    img = ventana(img, 760, 120, 400, 320)
    img = haz_de_luz(img, [(760, 440), (1160, 440), (1500, 900), (420, 900)], (110, 130, 190), 80)
    d = ImageDraw.Draw(img)
    alto = 820 * tam
    silueta(d, 960, 760 + 100 * tam, alto, (0, 0, 0), inclinacion=25 * tam)
    d.polygon(P([(0, 760), (1920, 760), (1920, 1080), (0, 1080)]), fill=(24, 27, 44))
    d.ellipse(P([(560, 700), (900, 900)]), fill=(30, 34, 54))
    d.ellipse(P([(1020, 700), (1360, 900)]), fill=(30, 34, 54))
    d.polygon(P([(0, 900), (1920, 900), (1920, 1080), (0, 1080)]), fill=(20, 22, 36))
    img = aplicar_niebla(img, (50, 55, 85), 0.18, 11)
    return oscurecer_bordes(img, 1.0)


def anim_figura_acerca(w, h):
    """La figura salta más cerca en cada parpadeo (p = 0.33 y 0.66)."""
    fr = [escena_figura_cama(w, h, s) for s in (0.45, 0.7, 1.0)]
    return lambda p, t: fr[0] if p < 0.33 else fr[1] if p < 0.66 else fr[2]


def escena_figura_cerca(w, h):
    return escena_figura_cama(w, h, 1.3)


def escena_presion(w, h, masa=1.0):
    img = degradado(w, h, (70, 14, 16), (12, 3, 4))
    d = ImageDraw.Draw(img)
    if masa > 0:
        capa = Image.new("L", img.size, 0)
        dc = ImageDraw.Draw(capa)
        bajada = 260 * masa
        dc.ellipse(P([(560, -420 - 260 + bajada), (1360, 520 - 260 + bajada)]), fill=255)
        dc.ellipse(P([(820, 180 - 260 + bajada), (1100, 520 - 260 + bajada)]), fill=255)
        for lado, x0 in ((1, 300), (-1, 1620)):  # dedos que entran por los lados
            for k in range(5):
                y = 430 + k * 62
                L = (420 + 60 * (2 - abs(k - 2))) * masa
                pts = [(x0, y), (x0 + lado * L * 0.7, y + 25), (x0 + lado * L, y + 60 + k * 6)]
                dc.line(P(pts), fill=255, width=S(22 - k * 2), joint="curve")
        capa = capa.filter(ImageFilter.GaussianBlur(S(5)))
        img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), capa.point(lambda v: int(v * min(1, masa * 1.2))))
    img = aplicar_niebla(img, (90, 10, 15), 0.25, 13)
    return oscurecer_bordes(img, 1.1)


def anim_presion_baja(w, h):
    get = _cache_por_pasos(lambda m: escena_presion(w, h, m), 20)
    return lambda p, t: get(tramo(p, 0.0, 0.8))


OJOS_X = (840, 1080)


def escena_ojos(w, h, apertura=1.0):
    img = Image.new("RGB", (w, h), (2, 1, 2))
    d = ImageDraw.Draw(img)
    d.ellipse(P([(600, 80), (1320, 1200)]), fill=(9, 7, 9))
    img = resplandor(img, lambda dd, c: dd.ellipse(P([(600, 80), (1320, 1200)]), outline=c, width=S(6)), (35, 30, 40), S(20))
    d = ImageDraw.Draw(img)
    if apertura <= 0.02:
        for cx in OJOS_X:
            d.arc(P([(cx - 75, 470), (cx + 75, 530)]), 20, 160, fill=(60, 52, 55), width=S(4))
        return oscurecer_bordes(img, 0.8)
    ab = 45 * apertura

    def ojos(dd, c):
        for cx in OJOS_X:
            dd.ellipse(P([(cx - 75, 515 - ab), (cx + 75, 515 + ab)]), fill=c)
    img = resplandor(img, ojos, (235, 235, 225), S(40), 1.2)
    d = ImageDraw.Draw(img)
    for cx in OJOS_X:
        r = 9 * min(1, apertura * 1.5)
        d.ellipse(P([(cx - r, 515 - r), (cx + r, 515 + r)]), fill=(0, 0, 0))
        for k in range(7):  # venas
            ang = k * 0.9
            d.line(P([(cx + 70 * np.cos(ang), 515 + ab * 0.9 * np.sin(ang)),
                      (cx + 40 * np.cos(ang + 0.2), 515 + ab * 0.5 * np.sin(ang + 0.2))]),
                   fill=(150, 30, 30), width=S(2))
    return oscurecer_bordes(img, 0.8)


def escena_ojos_cerrados(w, h):
    return escena_ojos(w, h, 0.0)


def anim_ojos_abren(w, h):
    """Ojos cerrados que se abren de golpe al 15% de la toma."""
    get = _cache_por_pasos(lambda a: escena_ojos(w, h, a), 8)
    return lambda p, t: get(tramo(t, 0.25, 0.42))


def escena_oscuridad(w, h):
    img = Image.new("RGB", (w, h), (2, 2, 4))
    img = aplicar_niebla(img, (30, 25, 40), 0.35, 21)
    d = ImageDraw.Draw(img)
    for cx in (930, 990):
        d.ellipse(P([(cx - 9, 470), (cx + 9, 478)]), fill=(110, 110, 105))
    return oscurecer_bordes(img, 0.9)


def escena_sabanas(w, h, marcas=1.0):
    img = degradado(w, h, (150, 145, 145), (90, 85, 88))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    for i in range(14):  # pliegues
        y = 60 + i * 75 + rnd.uniform(-20, 20)
        d.arc(P([(-200 + rnd.uniform(-80, 80), y), (2100, y + 260)]), 190, 350,
              fill=(110, 105, 108), width=S(rnd.uniform(6, 16)))
    img = img.filter(ImageFilter.GaussianBlur(S(9)))
    if marcas > 0:
        capa = Image.new("L", img.size, 0)
        dc = ImageDraw.Draw(capa)
        for k, (x, ang) in enumerate([(760, -0.18), (870, -0.06), (980, 0.05), (1090, 0.16)]):
            L = 520 - abs(k - 1.5) * 60
            x2, y2 = x + np.sin(ang) * L, 280 + np.cos(ang) * L
            dc.line(P([(x, 280), (x2, y2)]), fill=200, width=S(34))
            dc.ellipse(P([(x2 - 17, y2 - 17), (x2 + 17, y2 + 17)]), fill=200)
        capa = capa.filter(ImageFilter.GaussianBlur(S(10))).point(lambda v: int(v * marcas))
        img.paste(Image.new("RGB", img.size, (45, 30, 30)), (0, 0), capa)
    return oscurecer_bordes(img, 0.9)


def anim_sabanas_aparecen(w, h):
    a, b = escena_sabanas(w, h, 0.0), escena_sabanas(w, h, 1.0)
    return lambda p, t: Image.blend(a, b, tramo(p, 0.15, 0.55))


def escena_final(w, h):
    img = Image.new("RGB", (w, h), (2, 2, 4))
    img = aplicar_niebla(img, (30, 25, 40), 0.35, 21)
    d = ImageDraw.Draw(img)
    f = fuente(80)
    for i, txt in enumerate(["NO ABRAS", "LOS OJOS"]):
        bw = d.textbbox((0, 0), txt, font=f)
        x = (w - (bw[2] - bw[0])) // 2
        y = S(400 + i * 110)
        img = resplandor(img, lambda dd, c: dd.text((x, y), txt, font=f, fill=c), (140, 15, 20), S(30))
        d = ImageDraw.Draw(img)
        d.text((x, y), txt, font=f, fill=(200, 190, 185))
    return oscurecer_bordes(img, 0.9)


# ------------------------------------------------------------------ interfaz
def preparar(nombre, w=3840, h=2160):
    """Devuelve función(p, t) -> Image 4K para la escena (animada o estática)."""
    global _ESCALA
    _ESCALA = w / 1920
    g = globals()
    if f"anim_{nombre}" in g:
        return g[f"anim_{nombre}"](w, h)
    if f"escena_{nombre}" in g:
        img = g[f"escena_{nombre}"](w, h)
        return lambda p, t: img
    disp = sorted({k.split("_", 1)[1] for k in g if k.startswith(("anim_", "escena_"))})
    raise SystemExit(f"No existe la escena '{nombre}'. Disponibles: {', '.join(disp)}")


def dibujar(nombre, w=3840, h=2160, p=1.0, t=99.0):
    return preparar(nombre, w, h)(p, t)


if __name__ == "__main__":
    os.makedirs("previas", exist_ok=True)
    nombres = sorted({k.split("_", 1)[1] for k in list(globals()) if k.startswith(("anim_", "escena_"))})
    for n in nombres:
        dibujar(n, 1920, 1080).save(f"previas/{n}.png")
        print("ok", n)
