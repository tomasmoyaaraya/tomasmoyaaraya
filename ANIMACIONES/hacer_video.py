"""Generador de videos animados de terror: guion JSON -> MP4 1080p.

Uso:
    python hacer_video.py guion_paralisis.json
    python hacer_video.py guion_paralisis.json --motor espeak   (voz offline)
    python hacer_video.py guion_paralisis.json --rapido         (vista previa 720p)

Requisitos: Python 3.9+, ffmpeg en el PATH, y
    pip install edge-tts pillow numpy

Pipeline por escena: voz (edge-tts) -> dibujo en código (escenas.py, 4K) ->
zoom lento + grano + viñeta + parpadeo (ffmpeg). Luego se unen las escenas, se
mezcla un ambiente sonoro generado (drone + ruido + golpe en los sustos) y se
queman los subtítulos.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import escenas  # noqa: E402

FPS = 30
PAUSA_ANTES = 0.45   # segundos de silencio antes de la voz en cada escena
PAUSA_DESPUES = 0.9  # segundos después de la voz


def ff(args, cwd):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit("Falló ffmpeg: " + " ".join(cmd))


def duracion(ruta):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", ruta])
    return float(out.strip())


# ---------------------------------------------------------------------- voz
def voz_edge(texto, salida, g):
    import edge_tts
    proxy = os.environ.get("HTTPS_PROXY") or None
    com = edge_tts.Communicate(texto, g.get("voz", "es-MX-JorgeNeural"),
                               rate=g.get("velocidad", "+0%"), pitch=g.get("tono", "+0Hz"),
                               proxy=proxy)
    asyncio.run(com.save(salida))
    if not os.path.exists(salida) or os.path.getsize(salida) == 0:
        raise RuntimeError("edge-tts no devolvió audio")


def voz_espeak(texto, salida, g):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise SystemExit("No hay edge-tts disponible ni espeak-ng instalado.")
    subprocess.run([exe, "-v", "es-419", "-s", "138", "-p", "28", "-a", "160",
                    "-w", salida, texto], check=True, capture_output=True)


def generar_voz(texto, base, g, motor, trabajo):
    """Devuelve la ruta a un WAV procesado (eco suave, tono oscuro)."""
    crudo = os.path.join(trabajo, base + "_crudo")
    usado = motor
    if motor in ("auto", "edge"):
        try:
            voz_edge(texto, crudo + ".mp3", g)
            crudo += ".mp3"
            usado = "edge"
        except Exception as e:  # sin internet / bloqueado
            if motor == "edge":
                raise
            print(f"  ! edge-tts no disponible ({type(e).__name__}); uso espeak-ng offline")
            usado = "espeak"
    if usado == "espeak":
        voz_espeak(texto, crudo + ".wav", g)
        crudo += ".wav"
    filtro = "highpass=f=70,aecho=0.8:0.6:70|140:0.16|0.08"
    if usado == "espeak":  # baja el tono y le quita lo metálico
        filtro = "aresample=48000,asetrate=42240,aresample=48000,atempo=1.08,lowpass=f=5200," + filtro
    wav = os.path.join(trabajo, base + ".wav")
    ff(["-i", os.path.basename(crudo), "-af", filtro, "-ar", "48000", "-ac", "2",
        os.path.basename(wav)], trabajo)
    return wav, usado


# -------------------------------------------------------------------- video
def render_clip(i, esc, dur, trabajo, w, h):
    png = f"escena_{i:02d}.png"
    escenas.dibujar(esc["dibujo"], w * 2, h * 2).save(os.path.join(trabajo, png))
    n = int(round(dur * FPS))
    modo = esc.get("zoom", "in")
    fuerza = 0.30 if esc.get("susto") else float(esc.get("fuerza_zoom", 0.12))
    if modo == "out":
        z = f"{1 + fuerza}-{fuerza}*on/{n}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif modo == "pan":
        z = "1.12"
        x, y = f"(iw-iw/zoom)*(0.15+0.7*on/{n})", "ih/2-(ih/zoom/2)"
    else:
        z = f"1+{fuerza}*on/{n}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if esc.get("susto"):  # temblor
        x = f"{x}+12*sin(on*2.7)"
        y = f"{y}+9*cos(on*3.3)"
    vf = [
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={FPS}",
        # parpadeo de luz irregular
        "eq=brightness='-0.025+0.03*random(1)*gt(random(2),0.55)':eval=frame",
        "noise=alls=16:allf=t+u",  # grano de película
        "vignette=PI/4.5",
    ]
    if esc.get("susto"):
        vf.append("fade=t=in:st=0:d=0.35:color=white")
    else:
        vf.append("fade=t=in:st=0:d=0.6")
    vf.append(f"fade=t=out:st={dur - 0.5:.3f}:d=0.5")
    vf.append("format=yuv420p")
    mp4 = f"clip_{i:02d}.mp4"
    ff(["-loop", "1", "-framerate", str(FPS), "-i", png, "-vf", ",".join(vf),
        "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", mp4], trabajo)
    return mp4


# --------------------------------------------------------------- subtítulos
def trozos(texto, max_palabras=7):
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()]
    out = []
    for f in frases:
        pal = f.split()
        k = max(1, -(-len(pal) // max_palabras))
        tam = -(-len(pal) // k)
        out += [" ".join(pal[j:j + tam]) for j in range(0, len(pal), tam)]
    return out


def t_ass(s):
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def escribir_ass(eventos, ruta, w, h):
    tam = int(h * 0.052)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Terror,Arial,{tam},&H00F0F0F0,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,{max(2, tam // 14)},2,2,80,80,{int(h * 0.08)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab)
        for ini, fin, txt in eventos:
            f.write(f"Dialogue: 0,{t_ass(ini)},{t_ass(fin)},Terror,,0,0,0,,{{\\fad(120,120)}}{txt}\n")


# -------------------------------------------------------------------- audio
def mezclar_audio(wavs, durs, sustos, total, trabajo):
    entradas, partes = [], []
    for k, (wv, d) in enumerate(zip(wavs, durs)):
        entradas += ["-i", os.path.basename(wv)]
        ms = int(PAUSA_ANTES * 1000)
        partes.append(f"[{k}:a]adelay={ms}|{ms},apad,atrim=0:{d:.3f}[v{k}]")
    n = len(wavs)
    filtro = ";".join(partes) + ";" + "".join(f"[v{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[voz]"
    # ambiente: ruido marrón grave + drone con batido + latido lento
    filtro += (f";anoisesrc=d={total:.2f}:c=brown:a=0.5:r=48000,lowpass=f=320,volume=0.22[r]"
               f";sine=f=46:d={total:.2f}:r=48000,volume=0.35[s1]"
               f";sine=f=49.5:d={total:.2f}:r=48000,volume=0.30[s2]"
               f";[r][s1][s2]amix=inputs=3:normalize=0,tremolo=f=0.25:d=0.5,"
               f"afade=t=in:d=3,afade=t=out:st={total - 3:.2f}:d=3,aformat=channel_layouts=stereo[amb]")
    mezcla = ["[voz]", "[amb]"]
    for j, t0 in enumerate(sustos):  # golpe + chirrido descendente en los sustos
        ms = int(t0 * 1000)
        filtro += (f";aevalsrc='0.9*sin(2*PI*(55+900*exp(-4*t))*t)*exp(-1.6*t)|"
                   f"0.9*sin(2*PI*(57+880*exp(-4*t))*t)*exp(-1.6*t)':d=3:s=48000[g{j}a]"
                   f";anoisesrc=d=1.2:c=white:a=0.6:r=48000,highpass=f=1500,afade=t=out:d=1.2,"
                   f"aformat=channel_layouts=stereo[g{j}b]"
                   f";[g{j}a][g{j}b]amix=inputs=2:normalize=0,adelay={ms}|{ms}[g{j}]")
        mezcla.append(f"[g{j}]")
    filtro += f";{''.join(mezcla)}amix=inputs={len(mezcla)}:normalize=0,alimiter=limit=0.95[out]"
    ff(entradas + ["-filter_complex", filtro, "-map", "[out]", "-ar", "48000",
                   "-t", f"{total:.3f}", "audio.wav"], trabajo)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guion")
    ap.add_argument("--motor", choices=["auto", "edge", "espeak"], default="auto")
    ap.add_argument("--rapido", action="store_true", help="vista previa 720p")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg no está en el PATH.")

    with open(a.guion, encoding="utf-8") as f:
        g = json.load(f)
    w, h = (1280, 720) if a.rapido else (1920, 1080)
    nombre = os.path.splitext(os.path.basename(a.guion))[0]
    trabajo = os.path.join(AQUI, "trabajo", nombre)
    os.makedirs(trabajo, exist_ok=True)
    os.makedirs(os.path.join(AQUI, "salidas"), exist_ok=True)
    salida = os.path.abspath(a.salida or os.path.join(AQUI, "salidas", g.get("salida", nombre + ".mp4")))

    esc = g["escenas"]
    print(f"[1/4] Voces ({len(esc)} escenas)…")
    wavs, durs, motores = [], [], set()
    for i, e in enumerate(esc):
        wv, usado = generar_voz(e["texto"], f"voz_{i:02d}", g, a.motor, trabajo)
        motores.add(usado)
        wavs.append(wv)
        durs.append(PAUSA_ANTES + duracion(wv) + PAUSA_DESPUES + float(e.get("extra", 0)))
    total = sum(durs)
    print(f"      duración total: {total:.1f} s  (voz: {', '.join(sorted(motores))})")

    print("[2/4] Dibujando y animando escenas…")
    hilos = max(1, (os.cpu_count() or 2) // 2)
    with ThreadPoolExecutor(hilos) as ex:
        clips = list(ex.map(lambda k: render_clip(k, esc[k], durs[k], trabajo, w, h), range(len(esc))))
    with open(os.path.join(trabajo, "lista.txt"), "w") as f:
        f.writelines(f"file '{c}'\n" for c in clips)
    ff(["-f", "concat", "-safe", "0", "-i", "lista.txt", "-c", "copy", "video.mp4"], trabajo)

    print("[3/4] Subtítulos y sonido…")
    eventos, t0, sustos = [], 0.0, []
    for i, e in enumerate(esc):
        if e.get("susto"):
            sustos.append(t0)
        voz = duracion(wavs[i])
        partes = trozos(e["texto"])
        largo = sum(len(p) for p in partes)
        t = t0 + PAUSA_ANTES
        for p in partes:
            d = voz * len(p) / largo
            eventos.append((t, t + d, p))
            t += d
        t0 += durs[i]
    escribir_ass(eventos, os.path.join(trabajo, "subs.ass"), w, h)
    mezclar_audio(wavs, durs, sustos, total, trabajo)

    print("[4/4] Render final…")
    ff(["-i", "video.mp4", "-i", "audio.wav", "-vf", "ass=subs.ass",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", salida], trabajo)
    print(f"Listo -> {salida}")


if __name__ == "__main__":
    main()
