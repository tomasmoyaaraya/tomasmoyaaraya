# ANIMACIONES – videos de terror animados con código (estilo Shorts/TikTok)

Pipeline propio, sin instaladores de terceros:
**guion JSON → voz → escenas dibujadas y animadas en Python → cámara + efectos → música y SFX generados → subtítulos palabra por palabra → MP4**

## Instalar (una sola vez, Windows)
1. Python 3.10+ (python.org, marca "Add to PATH").
2. ffmpeg: `winget install Gyan.FFmpeg`
3. `pip install edge-tts piper-tts pillow numpy scipy`

## Usar
Doble clic en `generar.bat`, o en una terminal dentro de esta carpeta:

```
python hacer_video.py guion_paralisis.json                       # vertical 1080x1920 (Shorts/TikTok/Reels)
python hacer_video.py guion_paralisis.json --formato horizontal  # 1920x1080 para YouTube normal
python hacer_video.py guion_paralisis.json --rapido              # vista previa a media resolución
python hacer_video.py guion_paralisis.json --motor piper         # forzar voz offline
python escenas.py                                                # PNG de todas las escenas en previas/
```
Resultado en `salidas\`. Temporales en `trabajo\` (se pueden borrar).

### Voz
`auto` prueba en orden: **edge-tts** (online, la más natural; marca el tiempo de cada palabra) →
**Piper** (offline, neuronal; la primera vez descarga ~18 MB a `voces\`) → espeak-ng.

## Qué lo hace "viral"
- **Gancho en el segundo 1**: la imagen más fuerte + frase que obliga a seguir mirando + texto rojo arriba.
- **Nunca hay silencio muerto**: música (drone + piano disonante), latidos que se aceleran, tic-tac,
  crujidos, susurros, pasos, respiración; la música baja sola cuando habla el narrador.
- **Subtítulos grandes palabra por palabra** con la palabra actual en amarillo y efecto "pop".
- **Cortes cada 2–4 s** y cámara siempre en movimiento (zoom, paneo, golpes de zoom, temblor).
- **Primera persona**: párpados que se abren al despertar y parpadeos (la figura se acerca en cada uno).
- **Susto**: silencio → subida de tensión → flash, glitch RGB, temblor fuerte y golpe sonoro.
- **Final en bucle**: termina en el mismo 3:33 con que empieza, para que el video se repita.
- ~60 s: el punto dulce de retención en Shorts/TikTok.

## Hacer un video nuevo
Copia `guion_paralisis.json` y edita `lineas`. Cada línea es una toma:

| campo | qué hace |
|---|---|
| `texto` | lo que dice el narrador (vacío + `duracion` = toma sin voz) |
| `dibujo` | escena: dormitorio, amanecer, reloj, reloj_cambia, puerta, puerta_abre, figura_puerta, figura_aparece, figura_cama, figura_acerca, presion, presion_baja, ojos, ojos_cerrados, ojos_abren, oscuridad, sabanas, sabanas_aparecen, titulo, final |
| `zoom` | `[inicio, fin]` (1 = encuadre completo) |
| `foco`, `fy` | `[inicio, fin]` posición horizontal/vertical del centro (0–1) → paneos |
| `pantalla` | texto rojo grande arriba (`\n` = salto de línea) |
| `musica` | normal, tension, baja, calma, silencio |
| `sfx` | `[["nombre", cuándo, volumen, {opciones}]]` – cuándo: segundos, `"p0.5"` (mitad de la toma) o `"fin"`. Nombres: latido, tictac, crujido, pasos, susurro, respiracion, subida, golpe, braam, silbido |
| `susto` | segundo dentro de la toma del susto (flash + glitch + temblor + golpe) |
| `despertar` | párpados que se abren al empezar la toma |
| `parpadeos` | `[0.33, 0.66]` parpadeos en esas fracciones de la toma |
| `glitch` | `[[segundo, duración], …]` |
| `golpe_zoom`, `temblor`, `tinte` | golpe de zoom al inicio · temblor 0–5 · `[r, g, b]` multiplicadores |
| `pausa`, `pausa_antes`, `min` | silencio después / antes de la voz · duración mínima |

Para dibujos nuevos: `def escena_<nombre>(w, h)` (estática) o `def anim_<nombre>(w, h)` que
devuelve `función(p, t) -> imagen` (animada) en `escenas.py`.

Voces edge-tts útiles: `es-MX-JorgeNeural`, `es-ES-AlvaroNeural`, `es-AR-TomasNeural`,
`es-CL-LorenzoNeural` (lista: `edge-tts --list-voices`).

La fuente Inter Black (`fuentes/`) es de licencia libre OFL.
