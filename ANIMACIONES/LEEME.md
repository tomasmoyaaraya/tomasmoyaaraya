# ANIMACIONES – videos de terror animados con código

Pipeline propio (sin instaladores de terceros):
**guion JSON → voz edge-tts → escenas dibujadas en Python → zoom lento + grano + viñeta + parpadeo → ambiente sonoro → subtítulos → MP4 1080p**.

## Instalar (una sola vez, Windows)
1. Python 3.10+ (python.org, marca "Add to PATH").
2. ffmpeg: `winget install Gyan.FFmpeg` (o descarga de gyan.dev y añade `bin` al PATH).
3. `pip install edge-tts pillow numpy`

## Usar
Doble clic en `generar.bat` o, en una terminal dentro de esta carpeta:

```
python hacer_video.py guion_paralisis.json            # 1080p final
python hacer_video.py guion_paralisis.json --rapido   # vista previa 720p
python hacer_video.py guion_paralisis.json --motor espeak   # voz offline (requiere espeak-ng)
python escenas.py                                     # PNG de todas las escenas en previas/
```
El MP4 queda en `salidas\`. Los temporales en `trabajo\` (se pueden borrar).

## Hacer un video nuevo
Copia `guion_paralisis.json`, cambia los textos y elige para cada escena:
- `dibujo`: titulo, dormitorio, reloj, puerta, figura_puerta, figura_cama, presion, ojos, amanecer, sabanas, final
- `zoom`: `in`, `out` o `pan` · `fuerza_zoom` (por defecto 0.12)
- `susto: true` → flash blanco, temblor y golpe sonoro
- `extra`: segundos adicionales de pausa tras la voz

Para dibujos nuevos, añade `def escena_<nombre>(w, h)` en `escenas.py`.

Voces útiles de edge-tts: `es-MX-JorgeNeural`, `es-ES-AlvaroNeural`, `es-AR-TomasNeural`,
`es-CL-LorenzoNeural`, `es-MX-DaliaNeural` (lista completa: `edge-tts --list-voices`).
