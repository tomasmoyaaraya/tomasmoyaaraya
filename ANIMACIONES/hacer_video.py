"""Generador de videos de terror animados estilo Shorts/TikTok: guion JSON -> MP4.

Uso:
    python hacer_video.py guion_paralisis.json
    python hacer_video.py guion_paralisis.json --formato horizontal
    python hacer_video.py guion_paralisis.json --motor piper      (voz offline)
    python hacer_video.py guion_paralisis.json --rapido          (vista previa)

Requisitos: Python 3.9+, ffmpeg en el PATH y
    pip install edge-tts piper-tts pillow numpy scipy

Qué hace:
  * Voz: edge-tts (online, la mejor) -> Piper (offline, neuronal; baja el
    modelo solo la 1ª vez) -> espeak-ng (último recurso).
  * Escenas dibujadas en código (escenas.py), algunas animadas (puertas que
    se abren, figuras que se acercan, ojos que se abren…).
  * Cámara con zoom/paneo continuo, golpes de zoom, temblor, parpadeos en
    primera persona, glitch y flash en los sustos, luz que titila.
  * Subtítulos grandes palabra por palabra (resalta la palabra que se dice).
  * Música y efectos generados (sonido.py): nunca hay silencio muerto.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import wave

import numpy as np
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import escenas  # noqa: E402
import sonido  # noqa: E402

FPS = 30
SR = sonido.SR
PIPER_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{}.tar.gz"
NIVELES_MUSICA = {"normal": 0.75, "tension": 1.0, "baja": 0.45, "calma": 0.55, "silencio": 0.0}


def ff(args, cwd=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args
    if subprocess.run(cmd, cwd=cwd).returncode != 0:
        raise SystemExit("Falló ffmpeg: " + " ".join(cmd))


def leer_wav(ruta):
    with wave.open(ruta) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def escribir_wav(ruta, x):
    x = np.clip(x, -1, 1)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


# =================================================================== VOZ
def voz_edge(texto, salida, cfg):
    import edge_tts
    com = edge_tts.Communicate(texto, cfg.get("edge", "es-MX-JorgeNeural"),
                               rate=cfg.get("velocidad", "-5%"), pitch=cfg.get("tono", "-4Hz"),
                               boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY") or None)
    palabras = []

    async def correr():
        with open(salida, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    palabras.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    asyncio.run(correr())
    if os.path.getsize(salida) == 0:
        raise RuntimeError("edge-tts no devolvió audio")
    # edge devuelve palabras sin puntuación: se la devolvemos desde el texto
    orig = texto.split()
    if len(orig) == len(palabras):
        palabras = [(a, b, o) for (a, b, _), o in zip(palabras, orig)]
    return palabras


def modelo_piper(nombre):
    carpeta = os.path.join(AQUI, "voces")
    onnx = os.path.join(carpeta, nombre + ".onnx")
    if not os.path.exists(onnx):
        os.makedirs(carpeta, exist_ok=True)
        print(f"  descargando voz Piper '{nombre}' (solo la primera vez)…")
        tgz = os.path.join(carpeta, nombre + ".tar.gz")
        urllib.request.urlretrieve(PIPER_URL.format(nombre), tgz)
        with tarfile.open(tgz) as t:
            for m in t.getmembers():
                if m.name.endswith((".onnx", ".onnx.json")):
                    m.name = os.path.basename(m.name)
                    try:
                        t.extract(m, carpeta, filter="data")
                    except TypeError:  # Python antiguo sin 'filter'
                        t.extract(m, carpeta)
        os.remove(tgz)
    return onnx


def voz_piper(texto, salida, cfg):
    onnx = modelo_piper(cfg.get("piper", "es-carlfm-x-low"))
    subprocess.run([sys.executable, "-m", "piper", "-m", onnx, "-f", salida,
                    "--length-scale", str(cfg.get("piper_lentitud", 1.25)),
                    "--sentence-silence", "0.3"],
                   input=texto.encode("utf-8"), check=True, capture_output=True)
    return None


def voz_espeak(texto, salida, cfg):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng no está instalado")
    subprocess.run([exe, "-v", "es-419", "-s", "150", "-p", "28", "-w", salida, texto],
                   check=True, capture_output=True)
    return None


MOTORES = {"edge": voz_edge, "piper": voz_piper, "espeak": voz_espeak}
_motor_ok = {}


def generar_voz(texto, base, cfg, motor, trabajo):
    """Devuelve (audio estéreo 48k recortado, [(t0, t1, palabra)] o None, motor usado)."""
    orden = ["edge", "piper", "espeak"] if motor == "auto" else [motor]
    usado = None
    for m in orden:
        if _motor_ok.get(m) is False:
            continue
        crudo = os.path.join(trabajo, f"{base}_{m}.{'mp3' if m == 'edge' else 'wav'}")
        try:
            palabras = MOTORES[m](texto, crudo, cfg)
            _motor_ok[m] = True
            usado = m
            break
        except Exception as e:
            if len(orden) == 1:
                raise
            print(f"  ! voz '{m}' no disponible ({type(e).__name__}); pruebo la siguiente")
            _motor_ok[m] = False
    if usado is None:
        raise SystemExit("Ningún motor de voz funcionó.")
    cadena = "highpass=f=70,equalizer=f=140:t=q:w=1.2:g=4,acompressor=threshold=0.1:ratio=3:attack=5:release=80"
    if usado == "piper":  # un poco más grave
        cadena = "aresample=48000,asetrate=45600,aresample=48000," + cadena
    if usado == "espeak":
        cadena = "aresample=48000,asetrate=42240,aresample=48000,atempo=1.12,lowpass=f=5200," + cadena
    cadena += ",aecho=0.8:0.55:55|110:0.14|0.07"
    wav = os.path.join(trabajo, base + ".wav")
    ff(["-i", crudo, "-af", cadena, "-ar", str(SR), "-ac", "2", wav])
    x = leer_wav(wav)
    # recorta silencios al inicio y al final
    rms = np.sqrt(np.convolve(x[:, 0] ** 2, np.ones(480) / 480, "same"))
    voz = np.where(rms > rms.max() * 0.04)[0]
    a, b = (max(0, voz[0] - 960), min(len(x), voz[-1] + 4800)) if len(voz) else (0, len(x))
    if palabras:
        palabras = [(t0 - a / SR, t1 - a / SR, w) for t0, t1, w in palabras]
    return x[a:b], palabras, usado


def tiempos_estimados(texto, dur):
    """Sin marcas de tiempo (Piper/espeak): reparte según largo y puntuación."""
    pal = texto.split()

    def pausa(p):
        return 6.0 if re.search(r"[.!?…]$", p) else 3.5 if re.search(r"[,;:]$", p) else 0.0
    pesos = [len(re.sub(r"\W", "", p)) + 2.5 + pausa(p) for p in pal]
    total = sum(pesos)
    out, t = [], 0.0
    for p, w in zip(pal, pesos):
        d = dur * w / total
        out.append((t, t + max(0.08, d - dur * pausa(p) / total), p))
        t += d
    return out


# ============================================================ SUBTÍTULOS
def limpiar(p):
    return re.sub(r"[.,;:…\"]", "", p).upper()


def agrupar(palabras, max_pal=3):
    grupos, act = [], []
    for t0, t1, w in palabras:
        act.append((t0, t1, w))
        if len(act) >= max_pal or re.search(r"[.,;:!?…]$", w):
            grupos.append(act)
            act = []
    if act:
        grupos.append(act)
    return grupos


class Subtitulos:
    def __init__(self, W, H, vertical):
        self.W, self.H = W, H
        self.tam = int(min(W, H) * (0.085 if vertical else 0.075))
        self.f = escenas.fuente(self.tam, serif=False, px=True)
        self.y = int(H * (0.66 if vertical else 0.80))
        self.cache = {}

    def sprite(self, grupo, activa):
        clave = (tuple(w for _, _, w in grupo), activa)
        if clave in self.cache:
            return self.cache[clave]
        palabras = [limpiar(w) for _, _, w in grupo]
        esp = self.tam * 0.28
        anchos = [self.f.getbbox(p)[2] for p in palabras]
        lineas, act, ancho = [], [], 0
        for i, a in enumerate(anchos):  # corta en 2 líneas si no cabe
            if act and ancho + esp + a > self.W * 0.86:
                lineas.append(act)
                act, ancho = [], 0
            act.append(i)
            ancho += a + (esp if len(act) > 1 else 0)
        lineas.append(act)
        alto_l = int(self.tam * 1.2)
        ancho_max = int(max(sum(anchos[i] for i in l) + esp * (len(l) - 1) for l in lineas)) + self.tam
        img = Image.new("RGBA", (ancho_max, alto_l * len(lineas) + self.tam // 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        borde = max(3, self.tam // 9)
        for k, l in enumerate(lineas):
            x = (ancho_max - (sum(anchos[i] for i in l) + esp * (len(l) - 1))) / 2
            for i in l:
                color = (255, 214, 0) if i == activa else (255, 255, 255)
                d.text((x, k * alto_l + self.tam * 0.1), palabras[i], font=self.f, fill=color,
                       stroke_width=borde, stroke_fill=(0, 0, 0))
                x += anchos[i] + esp
        self.cache[clave] = img
        return img

    def dibujar(self, frame, grupo, activa, edad):
        spr = self.sprite(grupo, activa)
        esc = 1 + 0.22 * np.exp(-edad * 22)  # "pop" al aparecer
        if esc > 1.01:
            spr = spr.resize((int(spr.width * esc), int(spr.height * esc)), Image.BILINEAR)
        frame.paste(spr, ((self.W - spr.width) // 2, self.y - spr.height // 2), spr)


def texto_pantalla(W, H, txt):
    tam = int(min(W, H) * 0.095)
    f = escenas.fuente(tam, serif=False, px=True)
    lineas = txt.split("\n")
    anchos = [f.getbbox(l)[2] for l in lineas]
    img = Image.new("RGBA", (max(anchos) + tam, int(tam * 1.25) * len(lineas) + tam // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for k, l in enumerate(lineas):
        d.text(((img.width - anchos[k]) / 2, k * tam * 1.25), l, font=f, fill=(225, 25, 30),
               stroke_width=max(3, tam // 10), stroke_fill=(0, 0, 0))
    return img


# =============================================================== EFECTOS
class Parpados:
    """Párpados en primera persona (negro desde arriba y abajo con borde curvo)."""

    def __init__(self, W, H):
        x = np.linspace(-1, 1, W)
        self.perfil = ((1.3 - 0.3 * x ** 2) * (H / 2))[None, :].astype(np.float32)
        self.y = np.minimum(np.arange(H), H - 1 - np.arange(H))[:, None].astype(np.float32)
        self.pluma = H * 0.03

    def aplicar(self, arr, c):
        m = np.clip((c * self.perfil - self.y) / self.pluma + 0.5, 0, 1)
        arr *= (1 - m)[..., None]


def cierre_parpadeo(t, centros):
    c = 0.0
    for tb in centros:
        c = max(c, max(0.0, 1 - abs(t - tb) / 0.16) ** 0.6)
    return c


def cierre_despertar(t):
    s = escenas.suave
    if t < 0.35:
        return 1 - 0.6 * s(t / 0.35)
    if t < 0.6:
        return 0.4 + 0.35 * s((t - 0.35) / 0.25)
    return 0.75 * (1 - s((t - 0.6) / 0.6))


def glitch(arr, rng, fuerza=1.0):
    d = int(18 * fuerza)
    arr[..., 0] = np.roll(arr[..., 0], d, axis=1)
    arr[..., 2] = np.roll(arr[..., 2], -d, axis=1)
    H = arr.shape[0]
    for _ in range(rng.integers(3, 7)):
        y0 = rng.integers(0, H - 20)
        h = rng.integers(8, max(9, H // 12))
        arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], int(rng.integers(-80, 80) * fuerza), axis=1)


def momento_susto(L):
    s = L.get("susto")
    if s is None or s is False:
        return None
    return 0.0 if s is True else float(s)


# ================================================================ PRINCIPAL
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guion")
    ap.add_argument("--motor", choices=["auto", "edge", "piper", "espeak"], default="auto")
    ap.add_argument("--formato", choices=["vertical", "horizontal"], default=None)
    ap.add_argument("--rapido", action="store_true", help="vista previa a media resolución")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg no está en el PATH.")

    with open(a.guion, encoding="utf-8") as f:
        g = json.load(f)
    formato = a.formato or g.get("formato", "vertical")
    vertical = formato == "vertical"
    W, H = (1080, 1920) if vertical else (1920, 1080)
    if a.rapido:
        W, H = W // 2, H // 2
    nombre = os.path.splitext(os.path.basename(a.guion))[0]
    trabajo = os.path.join(AQUI, "trabajo", nombre)
    os.makedirs(trabajo, exist_ok=True)
    os.makedirs(os.path.join(AQUI, "salidas"), exist_ok=True)
    salida = os.path.abspath(a.salida or os.path.join(
        AQUI, "salidas", g.get("salida", nombre) + ("" if vertical else "_horizontal") + ".mp4"))
    cfg_voz = g.get("voz", {})
    lineas = g["lineas"]

    # ------------------------------------------------ 1. voces y línea de tiempo
    print(f"[1/4] Voces ({len(lineas)} líneas)…")
    tomas, t, motores = [], 0.0, set()
    for i, L in enumerate(lineas):
        pre = float(L.get("pausa_antes", 0.0))
        voz, palabras = None, []
        if L.get("texto"):
            voz, pal, m = generar_voz(L["texto"], f"voz_{i:02d}", cfg_voz, a.motor, trabajo)
            motores.add(m)
            palabras = pal or tiempos_estimados(L["texto"], len(voz) / SR)
            dur = pre + len(voz) / SR + float(L.get("pausa", 0.15))
        else:
            dur = float(L.get("duracion", 2.0))
        dur = max(dur, float(L.get("min", 0)))
        tomas.append({"L": L, "t0": t, "dur": dur, "voz": voz, "tv": t + pre,
                      "palabras": [(t + pre + p0, t + pre + p1, w) for p0, p1, w in palabras]})
        t += dur
    total = t
    print(f"      duración: {total:.1f} s · voz: {', '.join(sorted(motores))} · {formato} {W}x{H}")

    # ------------------------------------------------------------- 2. audio
    print("[2/4] Música y efectos…")
    n = int(total * SR) + SR
    pista_voz = np.zeros((n, 2), np.float32)
    efectos = np.zeros((n, 2), np.float32)
    for tm in tomas:
        L = tm["L"]
        if tm["voz"] is not None:
            sonido.colocar(pista_voz, tm["voz"], tm["tv"])
        for ef in L.get("sfx", []):
            off = ef[1] if len(ef) > 1 else 0
            vol = ef[2] if len(ef) > 2 else 1.0
            s = sonido.EFECTOS[ef[0]](**(ef[3] if len(ef) > 3 else {}))
            if off == "fin":
                t0 = tm["t0"] + tm["dur"] - len(s) / SR
            elif isinstance(off, str) and off.startswith("p"):
                t0 = tm["t0"] + tm["dur"] * float(off[1:])
            else:
                t0 = tm["t0"] + float(off)
            sonido.colocar(efectos, s, max(0.0, t0), vol)
        ts = momento_susto(L)
        if ts is not None:
            sonido.colocar(efectos, sonido.golpe(), tm["t0"] + ts, 1.0)
    bordes = [tm["t0"] for tm in tomas] + [total]
    nivel = [NIVELES_MUSICA.get(tm["L"].get("musica", "normal"), 0.75) for tm in tomas]

    def niveles(x):
        k = int(max(0, min(len(tomas) - 1, np.searchsorted(bordes, x, "right") - 1)))
        prev = nivel[k - 1] if k > 0 else nivel[k]
        return prev + (nivel[k] - prev) * min(1.0, (x - bordes[k]) / 0.4)
    musica = sonido.musica(total + 1, niveles)
    m = min(len(musica), n)
    env = np.convolve(np.abs(pista_voz[:, 0]), np.ones(4800) / 4800, "same")
    env = np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
    mezcla = pista_voz + efectos * 0.8
    mezcla[:m] += musica[:m] * (1 - 0.5 * env[:m, None])
    mezcla = np.tanh(mezcla / (np.abs(mezcla).max() + 1e-9) * 1.3) * 0.95
    escribir_wav(os.path.join(trabajo, "audio.wav"), mezcla[: int(total * SR)])

    # ------------------------------------------------------------- 3. video
    print("[3/4] Animando y componiendo cuadros…")
    subs = Subtitulos(W, H, vertical)
    parpados = Parpados(W, H)
    rng = np.random.default_rng(7)
    grupos = []
    for tm in tomas:
        fin_toma = tm["t0"] + tm["dur"]
        gs = agrupar(tm["palabras"])
        for j, gr in enumerate(gs):
            fin = gs[j + 1][0][0] if j + 1 < len(gs) else min(fin_toma, gr[-1][1] + 0.6)
            grupos.append((gr[0][0], fin, gr))

    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", os.path.join(trabajo, "audio.wav"),
         "-vf", "noise=alls=9:allf=t+u,vignette=PI/5,format=yuv420p",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "10M", "-bufsize", "20M",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", salida],
        stdin=subprocess.PIPE)

    k_act, escena, pant = -1, None, None
    for fi in range(int(total * FPS)):
        tg = fi / FPS
        k = int(max(0, min(len(tomas) - 1, np.searchsorted(bordes, tg, "right") - 1)))
        tm = tomas[k]
        L = tm["L"]
        if k != k_act:
            escena = escenas.preparar(L["dibujo"])
            pant = texto_pantalla(W, H, L["pantalla"]) if L.get("pantalla") else None
            k_act = k
            print(f"      toma {k + 1}/{len(tomas)}: {L['dibujo']}", flush=True)
        tl = tg - tm["t0"]
        p = tl / tm["dur"]
        base = escena(p, tl)
        Wb, Hb = base.size
        ts = momento_susto(L)
        golpe_activo = ts is not None and tl >= ts

        # --- cámara: zoom, paneo, golpes y temblor
        z0, z1 = L.get("zoom", [1.0, 1.1])
        fx, fy = L.get("foco", [0.5, 0.5]), L.get("fy", [0.5, 0.5])
        z = z0 + (z1 - z0) * p
        if L.get("golpe_zoom"):
            z *= 1 + 0.10 * np.exp(-tl * 7)
        if golpe_activo:
            z *= 1 + 0.18 * np.exp(-(tl - ts) * 5)
        sp = escenas.suave(p)
        cx = (fx[0] + (fx[1] - fx[0]) * sp) * Wb
        cy = (fy[0] + (fy[1] - fy[0]) * sp) * Hb
        if W / H < Wb / Hb:
            ch = Hb / z
            cw = ch * W / H
        else:
            cw = Wb / z
            ch = cw * H / W
        amp = 4 + float(L.get("temblor", 0)) * 4
        if golpe_activo:
            amp += 45 * np.exp(-(tl - ts) * 3)
        rapido = 0.4 if amp > 6 else 0.0
        dx = amp * (np.sin(tg * 1.7) * 0.6 + np.sin(tg * 23.1) * rapido) * cw / W
        dy = amp * (np.cos(tg * 1.3) * 0.6 + np.cos(tg * 19.7) * rapido) * ch / H
        cx = min(max(cx + dx, cw / 2), Wb - cw / 2)
        cy = min(max(cy + dy, ch / 2), Hb - ch / 2)
        frame = base.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))

        # --- efectos por píxel (solo si hacen falta)
        arr = None

        def A():
            nonlocal arr
            if arr is None:
                arr = np.asarray(frame, dtype=np.float32).copy()
            return arr
        if L.get("parpadeo_luz", L["dibujo"] not in ("amanecer", "sabanas", "sabanas_aparecen")) \
                and rng.random() < 0.07:
            A()[:] *= rng.uniform(0.55, 0.85)
        if L.get("tinte"):
            A()[:] *= np.array(L["tinte"], np.float32)
        en_glitch = any(g0 <= tl < g0 + gd for g0, gd in L.get("glitch", []))
        if golpe_activo and tl < ts + 0.6:
            en_glitch = True
        if en_glitch and rng.random() < 0.8:
            glitch(A(), rng, rng.uniform(0.5, 1.5))
        if golpe_activo and tl < ts + 0.5:  # flash blanco que vira a rojo
            f = np.exp(-(tl - ts) * 12)
            A()[:] = A() * (1 - f) + 255 * f
            A()[..., 1:] *= 1 - 0.35 * np.exp(-(tl - ts) * 4)
        c = 0.0
        if L.get("despertar"):
            c = cierre_despertar(tl)
        if L.get("parpadeos"):
            c = max(c, cierre_parpadeo(tl, [q * tm["dur"] for q in L["parpadeos"]]))
        if c > 0.001:
            parpados.aplicar(A(), c)
        if arr is not None:
            frame = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

        # --- textos
        if pant is not None:
            jit = int(rng.integers(-2, 3))
            frame.paste(pant, ((W - pant.width) // 2 + jit, int(H * (0.14 if vertical else 0.07)) + jit), pant)
        for g0, g1, gr in grupos:
            if g0 <= tg < g1:
                activa = max([i for i, (w0, _, _) in enumerate(gr) if w0 <= tg] or [0])
                subs.dibujar(frame, gr, activa, tg - g0)
                break
        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("Falló la codificación con ffmpeg.")
    print(f"[4/4] Listo -> {salida}")


if __name__ == "__main__":
    main()
