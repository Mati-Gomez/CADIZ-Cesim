# -*- coding: utf-8 -*-
"""
gap_analysis.py -- Control de gestión: compara la PROYECCIÓN de CADIZ (leída DIRECTAMENTE de
CADIZ_Gestion_v2.xlsx!DATA_EXPORT -- ver Adenda 10 / hotfix README) contra el dato REAL (el df tidy
que ya arma cesim_parser.build_historico() a partir de los RDOS oficiales) para los KPIs listados en
metric_crosswalk.py.

DISEÑO (corregido): ya no hay un CSV intermedio que mantener sincronizado a mano. El usuario sube el
Excel de gestión directamente a la raíz del repo (siempre con el mismo nombre, `CADIZ_Gestion_v2.xlsx`)
cada vez que hay una versión nueva; `load_proyeccion()` lo lee de ahí en cada carga de la app, así que
la versión presente en el repo es automáticamente "la más actual" -- sin exportar nada a mano.

Solo tiene sentido para RONDAS OFICIALES con número de ronda (el modelo de Excel de CADIZ proyecta
rondas oficiales, no las de práctica) -- para una ronda de práctica, o una ronda oficial que el
modelo todavía no cubre, calcular_gaps() devuelve estado='sin_proyeccion' para cada KPI en vez de
inventar un cruce.

"Real" puede no estar disponible todavía aunque haya proyección (CESIM no publicó los RDOS de esa
ronda) -- ese caso es distinto y se reporta como estado='sin_real', no como error.
"""
import os
import re

import pandas as pd

from export_proyeccion import read_dataframe, DEFAULT_EXCEL
from metric_crosswalk import CROSSWALK_FINANZAS

_RONDA_OFICIAL_RE = re.compile(r"^Ronda\s+(\d+)$")

# Mismo archivo que lee export_proyeccion.py -- vive en la raíz del repo, al lado de app.py. El
# usuario lo reemplaza (mismo nombre) cada vez que hay una versión nueva del modelo de gestión.
DEFAULT_PROYECCION_EXCEL = DEFAULT_EXCEL


def load_proyeccion(path=DEFAULT_PROYECCION_EXCEL, team="CADIZ"):
    """Lee la proyección de CADIZ directamente de CADIZ_Gestion_v2.xlsx!DATA_EXPORT. Devuelve None
    si el archivo todavía no fue subido al repo, o si algo falla al leerlo (hoja faltante, encabezado
    desalineado, archivo corrupto) -- el tablero debe poder arrancar igual, mostrando la sección de
    Control de Gestión como no disponible en vez de romper toda la app."""
    if not os.path.exists(path):
        return None
    try:
        return read_dataframe(path, team=team)
    except Exception:
        return None


def _valor_proyeccion(df_proy, ronda_num, spec, team="CADIZ"):
    if df_proy is None or ronda_num is None:
        return None, None
    sub = df_proy[(df_proy["round"] == ronda_num) & (df_proy["team"] == team) &
                  (df_proy["metric"] == spec["metric"]) & (df_proy["region"] == spec["region"])]
    if sub.empty:
        return None, None
    row = sub.iloc[0]
    val = row["value"]
    # La columna 'value' de DATA_EXPORT mezcla números y texto (p.ej. la calificación crediticia, o
    # el enfoque de marketing en otras filas) en una sola columna. Se intenta convertir a número acá;
    # si falla (texto real, como la calificación crediticia) se deja tal cual.
    try:
        val = float(val)
    except (TypeError, ValueError):
        pass
    return val, row["status"]   # status: REAL (histórico) o PLAN (proyección propia)


def _valor_real(df_real, ronda_nombre, spec, team="CADIZ"):
    if df_real is None or ronda_nombre is None:
        return None
    sub = df_real[(df_real["Ronda"] == ronda_nombre) & (df_real["Empresa"] == team) &
                  (df_real["Estado"] == spec["estado"]) & (df_real["Metrica"] == spec["metrica"])]
    if spec.get("seccion"):
        sub = sub[sub["Seccion"] == spec["seccion"]]
    if sub.empty:
        return None
    val = sub.iloc[0]["Valor"]
    try:
        return float(val)
    except (TypeError, ValueError):
        return val   # texto (p.ej. calificación crediticia)


def _to_absoluto(valor, spec_tipo, fuente):
    """cesim_parser reporta USD en 'miles USD' (RDOS nativo) y % en escala 0-100 (p.ej. 19.99, no
    0.1999) -- misma convención canónica de unidades que build_gestion_v2.py (Cambio 3, ver
    Informe_V2.md): USD -> x1000, ratio -> /100. La proyección (DATA_EXPORT del Excel) ya viene en
    esa convención canónica (USD absoluto, ratio 0-1) -- normalizar acá el lado 'real' para poder
    restar directamente."""
    if fuente != "real" or not isinstance(valor, (int, float)):
        return valor
    if spec_tipo == "usd":
        return valor * 1000.0
    if spec_tipo == "ratio":
        return valor / 100.0
    return valor


def ronda_a_num(ronda_nombre):
    """CADIZ_Gestion_v2.xlsx proyecta únicamente rondas OFICIALES ('Ronda N', round=N en
    DATA_EXPORT) -- una ronda de Práctica no tiene equivalente ahí, así que para esas
    devuelve None a propósito (fuerza 'sin_proyeccion'/'sin_datos' en calcular_gaps, y el panel cae
    al gráfico de evolución en vez de mostrar un gap inexistente). Se parsea del NOMBRE de la ronda
    (convención ya usada en app.py: rondas_timeline = ['Ronda 1', ..., 'Ronda 12']), no de si ya hay
    un RDOS real cargado para ella -- el selector de ronda deja elegir 'Ronda 2' aunque CESIM todavía
    no haya publicado ese resultado, que es exactamente el caso que el control de gestión necesita
    poder mostrar ('proyectado ya cargado, real pendiente')."""
    m = _RONDA_OFICIAL_RE.match(ronda_nombre or "")
    return int(m.group(1)) if m else None


def calcular_gaps(df_real, df_proy, ronda_nombre, ronda_num, team="CADIZ", crosswalk=None):
    """Devuelve {clave_kpi: {label, tipo, gap_favorable, proyectado, proyectado_status, real,
    gap_abs, gap_pct, estado}} para cada entrada del crosswalk.

    estado: 'ok' (hay proyección y real), 'sin_proyeccion' (no hay fila en DATA_EXPORT para
    esta ronda/KPI -- p.ej. ronda de práctica, o ronda oficial que el modelo Excel todavía no cubre),
    'sin_real' (hay proyección pero CESIM no publicó todavía el RDOS real de esta ronda), 'sin_datos'
    (no hay ninguna de las dos)."""
    crosswalk = crosswalk or CROSSWALK_FINANZAS
    out = {}
    for clave, spec in crosswalk.items():
        proy_val, proy_status = _valor_proyeccion(df_proy, ronda_num, spec["proyeccion"], team)
        real_val = _valor_real(df_real, ronda_nombre, spec["real"], team)
        real_val = _to_absoluto(real_val, spec["tipo"], "real")

        if proy_val is None and real_val is None:
            estado = "sin_datos"
        elif proy_val is None:
            estado = "sin_proyeccion"
        elif real_val is None:
            estado = "sin_real"
        else:
            estado = "ok"

        gap_abs = gap_pct = None
        if estado == "ok" and spec["tipo"] in ("usd", "ratio") and isinstance(real_val, (int, float)) and isinstance(proy_val, (int, float)):
            gap_abs = real_val - proy_val
            if proy_val not in (0, None):
                gap_pct = gap_abs / abs(proy_val) * 100.0

        out[clave] = {
            "label": spec["label"], "tipo": spec["tipo"], "gap_favorable": spec["gap_favorable"],
            "proyectado": proy_val, "proyectado_status": proy_status, "real": real_val,
            "gap_abs": gap_abs, "gap_pct": gap_pct, "estado": estado,
        }
    return out
