# Tablero CADIZ — Cesim Global Automotive

## Cómo cargar una ronda nueva
1. Descargá el `.xls` de resultados de la ronda desde Cesim.
2. Subilo a `data/raw/` en este repo (drag & drop en github.com, o `git add` + commit + push).
3. Listo — la app lee todos los `.xls` de `data/raw/` en cada carga y arma el histórico sola.
   No hace falta correr ningún script aparte.

## Deploy
1. Subir esta carpeta como repo a GitHub.
2. En share.streamlit.io: New app → apuntar a este repo → `app.py` como entry point.
3. Cada `git push` (incluido subir una ronda nueva) redeploya la app sola en 1-2 min.

## Estructura
- `cesim_parser.py` — toda la lógica de parseo del .xls de Cesim (reutilizable).
- `app.py` — la app Streamlit (sidebar con los módulos, lee data/raw/ automáticamente).
- `data/raw/` — los .xls de cada ronda, tal cual los bajás de Cesim.
