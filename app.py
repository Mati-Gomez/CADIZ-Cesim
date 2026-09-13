import glob
import os
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from cesim_parser import build_historico
from gap_analysis import (calcular_gaps, load_proyeccion, ronda_a_num, DEFAULT_PROYECCION_EXCEL,
                          precio_volumen_mercado, variacion_precio_volumen_mix, costo_unitario_area,
                          cuota_mercado_objetivo_vs_real, flujo_caja_plan_real_global,
                          TECNOLOGIAS as _TECNOLOGIAS_GAP, MERCADOS as _MERCADOS_GAP, AREAS as _AREAS_GAP,
                          MONEDA_MERCADO as _MONEDA_MERCADO_GAP)
from metric_crosswalk import CROSSWALK_FINANZAS, CROSSWALK_MERCADO, CROSSWALK_OPERACIONES, CROSSWALK_RESULTADOS
# --- IDENTIDAD Y PALETA SEMÁNTICA ---
MY_COMPANY = 'CADIZ'
COMPANIES = ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CUORE', 'FOCUS', 'TOKIO']
BRAND_ACCENT = '#B3261E'       # Rojo CÁDIZ
COLOR_POSITIVE = '#94D02D'     # Verde Lima
BRAND_DARK = '#1A1714'         # Negro Grafito
BRAND_LIGHT = '#F5F2ED'        # Crema
# Tonos apagados pero CON matiz (no gris puro) para distinguir competidores de un vistazo,
# sin competir visualmente con el rojo CADIZ.
MUTED_PALETTE = ['#8C97A6', '#A68C6E', '#7E9E8C', '#9E8CA0', '#A69B6E', '#7E8C9E']
# Color por CONCEPTO, no por orden de aparición. El rojo de marca queda reservado para
# identificar a CÁDIZ entre los equipos; las métricas usan colores con significado propio
# y estable en toda la app (antes el rojo era "Salario" en un gráfico y "Rotación" en el de al lado).
COLOR_METRICA = {
    'dinero':      '#3E7CB1',   # azul  — plata: costos, presupuestos, salarios
    'personas':    '#8C97A6',   # gris azulado — headcount, contrataciones
    'eficiencia':  '#4E9A4E',   # verde — indicadores donde más es mejor
    'riesgo':      '#C9922E',   # ámbar — rotación, deuda, alertas blandas
    'critico':     BRAND_ACCENT # rojo  — problemas y la propia CÁDIZ
}
COLOR_MAP = {MY_COMPANY: BRAND_ACCENT}
for i, c in enumerate([c for c in COMPANIES if c != MY_COMPANY]):
    COLOR_MAP[c] = MUTED_PALETTE[i % len(MUTED_PALETTE)]
CHART_HEIGHT = 260      # alto del área de ploteo de referencia
ALTURA_TARJETA = 370    # alto FIJO de toda tarjeta de gráfico, con o sin leyenda abajo:
                        # es lo que garantiza que dos gráficos en columnas queden parejos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')
st.set_page_config(page_title='CÁDIZ | Tablero Directivo', layout='wide')
# ---------------- Carga de datos y Helpers ----------------
def get_pais(estado: str) -> str:
    if re.search(r'\bGlobal\b', estado) or 'casa matriz' in estado: return 'Global'
    if 'EE.UU.' in estado: return 'EE.UU.'
    if 'China' in estado: return 'China'
    if 'Europa' in estado: return 'Europa'
    return 'General'
@st.cache_data(show_spinner='Procesando rondas...')
def cargar_historico(files_signature: tuple) -> pd.DataFrame:
    data = build_historico(list(files_signature))
    data['Pais'] = data['Estado'].apply(get_pais)
    return data
def get_data(tipo_ronda) -> pd.DataFrame:
    xls_files = sorted(glob.glob(os.path.join(DATA_DIR, '**', '*.xls'), recursive=True) +
                       glob.glob(os.path.join(DATA_DIR, '**', '*.XLS'), recursive=True))
    if not xls_files:
        st.warning(f'No se encontraron archivos .xls en {DATA_DIR} ni en subcarpetas.')
        st.stop()
    df_raw = cargar_historico(tuple(xls_files))
    return df_raw[df_raw['Tipo_Ronda'] == tipo_ronda].copy()
@st.cache_data(show_spinner='Leyendo proyección de CADIZ...')
def _cargar_proyeccion_cached(path: str, mtime: float):
    # `mtime` en la firma de cache -- no se usa dentro de la función, pero cambia cada vez que se
    # reemplaza CADIZ_Gestion_v2.xlsx en el repo (mismo nombre de archivo), así Streamlit invalida
    # el caché y relee el Excel en vez de servir una versión vieja. Devuelve un DataFrame o None.
    return load_proyeccion(path)
def get_proyeccion():
    """CADIZ_Gestion_v2.xlsx vive en la raíz del repo (al lado de este archivo): el usuario lo
    reemplaza (siempre el mismo nombre) cada vez que hay una versión nueva del modelo de gestión, y
    la próxima carga de la app toma automáticamente esa versión como 'la más actual' -- no hace falta
    subir ningún CSV ni correr ningún script aparte."""
    if not os.path.exists(DEFAULT_PROYECCION_EXCEL):
        return None
    return _cargar_proyeccion_cached(DEFAULT_PROYECCION_EXCEL, os.path.getmtime(DEFAULT_PROYECCION_EXCEL))
def num(series):
    return pd.to_numeric(series, errors='coerce')
def format_num(val, dec=1):
    """Al menos un decimal en todos los rangos (antes el corte de miles truncaba a entero, ej.
    '638k' en vez de '638.2k' -- perdía precisión visible justo en el rango donde más se usa)."""
    if pd.isna(val) or val is None: return ""
    try:
        val = float(val)
        dec = max(dec, 1)
        if abs(val) >= 1_000_000: return f"{val/1_000_000:,.1f}M"
        if abs(val) >= 1_000: return f"{val/1_000:,.1f}k"
        return f"{val:,.{dec}f}"
    except (ValueError, TypeError):
        return ""
def valor_de(sub_df, metrica, empresa=None):
    d = sub_df[sub_df['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None
def valor_texto(sub_df, metrica, empresa=None):
    """Como valor_de, pero para campos de texto (ej. calificación crediticia 'A+') —
    no fuerza conversión a número, así que no se rompe en NaN."""
    d = sub_df[sub_df['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    return d['Valor'].iloc[0] if not d.empty else None
def valor_fuzzy(sub_df, keyword, empresa=None):
    d = sub_df[sub_df['Metrica'].str.contains(rf'{keyword}', case=False, na=False)]
    if empresa: d = d[d['Empresa'] == empresa]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None
def es_modo_oscuro():
    """Fuente de verdad única: el tema REAL de Streamlit (nativo, el que el usuario elige en
    Settings o 'usar el del sistema'), no un toggle casero desconectado del resto de la UI."""
    try:
        return st.context.theme.type == 'dark'
    except Exception:
        return True
def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    oscuro = es_modo_oscuro()
    # Si la figura ya trae leyenda propia posicionada abajo (y<0), necesita más alto/margen
    # para que la leyenda no quede tapando el gráfico.
    leyenda_abajo = False
    for ln in ('legend', 'legend2'):
        leg = getattr(fig.layout, ln, None)
        if leg is not None and leg.y is not None and leg.y < 0:
            leyenda_abajo = True
    # Altura ÚNICA para todos los gráficos del tablero. Antes cada figura podía traer la suya
    # (CHART_HEIGHT, +20, +60, 280) y las que tenían leyenda abajo crecían: dos gráficos en
    # columnas contiguas terminaban de distinto alto. Ahora la tarjeta siempre mide lo mismo y
    # lo único que cambia es cuánto de ese alto se reserva abajo para la leyenda.
    altura = ALTURA_TARJETA
    margen_b = 110 if leyenda_abajo else 20
    color_linea_eje = '#4A4642' if oscuro else '#D8D3CC'
    fig.update_layout(template='plotly_dark' if oscuro else 'plotly_white',
                       paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=BRAND_LIGHT if oscuro else BRAND_DARK, family='Plus Jakarta Sans, sans-serif'),
                       title_font=dict(family='Plus Jakarta Sans, sans-serif', size=14, weight=600),
                       margin=dict(l=20, r=20, t=45, b=margen_b),
                       height=altura,
                       bargap=0.4)
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linewidth=1, linecolor=color_linea_eje)
    fig.update_yaxes(showgrid=False, zeroline=False, showline=True, linewidth=1, linecolor=color_linea_eje)

    if ocultar_eje_valores == 'y': fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x': fig.update_xaxes(showticklabels=False, title=None)
    
    if en_card:
        with st.container(border=True): st.plotly_chart(fig, use_container_width=True, **kwargs)
    else: st.plotly_chart(fig, use_container_width=True, **kwargs)
def linea_media(fig, valor, eje='y', etiqueta='Promedio'):
    if pd.isna(valor): return
    color_ref = 'rgba(255,255,255,0.35)' if es_modo_oscuro() else 'rgba(26,23,20,0.35)'
    kwargs = dict(line_dash='dash', line_color=color_ref, line_width=1.5,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color=color_ref)
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)
def chart_comparacion_equipos(sub: pd.DataFrame, titulo: str, ronda=None):
    ronda = ronda or ronda_ultima
    d = sub[sub['Ronda'] == ronda].copy()
    d['Valor'] = num(d['Valor'])
    d = d.dropna(subset=['Valor']).sort_values('Valor', ascending=False)
    if d.empty: return st.info('Sin datos numéricos.')
    d['Etiqueta'] = d['Valor'].apply(format_num)
    fig = px.bar(d, x='Empresa', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP, title=f'{titulo} — {ronda}', text='Etiqueta')
    fig.update_traces(textposition='outside', cliponaxis=False, showlegend=False)
    mostrar(fig, ocultar_eje_valores='y')
def chart_evolucion(sub: pd.DataFrame, titulo: str):
    ev = sub.copy()
    ev['Valor'] = num(ev['Valor'])
    ev = ev.dropna(subset=['Valor'])
    if ev.empty: return st.info('Sin datos para evolución.')
    fig = go.Figure()
    for comp in COMPANIES:
        d = ev[ev['Empresa'] == comp].sort_values('Ronda_Orden')
        if d.empty: continue
        es_cadiz = comp == MY_COMPANY
        fig.add_trace(go.Scatter(x=d['Ronda'], y=d['Valor'], mode='lines+markers', name=comp,
                                  line=dict(color=COLOR_MAP[comp], width=3 if es_cadiz else 1),
                                  marker=dict(size=6 if es_cadiz else 4), opacity=1.0 if es_cadiz else 0.5))
    promedio_x_ronda = ev.groupby('Ronda_Orden').agg(Ronda=('Ronda', 'first'), Valor=('Valor', 'mean')).sort_index()
    if len(promedio_x_ronda) > 0:
        color_ref = 'rgba(255,255,255,0.35)' if es_modo_oscuro() else 'rgba(26,23,20,0.35)'
        fig.add_trace(go.Scatter(x=promedio_x_ronda['Ronda'], y=promedio_x_ronda['Valor'], mode='lines+markers',
                                  name='Promedio', line=dict(color=color_ref, width=1, dash='dash'), marker=dict(size=4)))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)
def chart_evolucion_proyeccion(df_proy: pd.DataFrame, metric: str, region: str, titulo: str, team='CADIZ'):
    """Evolución de una métrica que CADIZ proyecta pero que CESIM nunca publica en el RDOS (ej. FCF) --
    a diferencia de chart_evolucion (que grafica el dato REAL de los 7 equipos), acá solo hay una
    serie: la propia proyección de CADIZ, ronda a ronda. Se muestra igual, sin comparación, para no
    perder de vista la tendencia de un indicador que de otro modo quedaría sin ningún gráfico."""
    if df_proy is None:
        return st.info('Sin proyección cargada.')
    sub = df_proy[(df_proy['team'] == team) & (df_proy['metric'] == metric) & (df_proy['region'] == region)].copy()
    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub = sub.dropna(subset=['value']).sort_values('round')
    if sub.empty:
        return st.info('Sin datos para evolución.')
    fig = go.Figure(go.Scatter(x=sub['round'], y=sub['value'], mode='lines+markers', name=team,
                                line=dict(color=COLOR_MAP.get(team, BRAND_ACCENT), width=3), marker=dict(size=6)))
    fig.update_layout(title=f'Evolución de la proyección — {titulo}', xaxis_title='Ronda')
    mostrar(fig)
def _techo_apilado(y):
    """Techo del eje con ~15% de aire arriba del máximo real -- ver nota en chart_dos_metricas_apiladas
    sobre por qué no alcanza con rangemode='tozero' solo para barras."""
    y_vals = [v for v in y if v is not None and not pd.isna(v)]
    y_max = max(y_vals) if y_vals else 0
    return y_max * 1.15 if y_max > 0 else 1
def chart_dos_metricas_apiladas(titulo, x_a, y_a, nombre_a, color_a, tipo_a,
                                 x_b, y_b, nombre_b, color_b, tipo_b):
    """UN solo gráfico, eje X compartido (misma Ronda), con la primera métrica en el eje Y
    izquierdo y la segunda en el eje Y derecho (doble eje Y superpuesto) -- a pedido explícito del
    equipo, que prefirió esto a la versión anterior (dos paneles apilados, cada uno con su propio
    eje). OJO: esto reintroduce a propósito el patrón de "doble eje Y" que se había evitado acá
    mismo (y que se sacó del todo en Mercado -> Evolución, "Trayectoria de precio y
    características", por el riesgo de sugerir una correlación entre las dos series que no está
    probada) -- queda anotado por si conviene revisar el criterio más adelante, pero el pedido fue
    explícito y puntual para ESTOS gráficos (RRHH y Beneficio vs. Deuda), no una vuelta atrás
    general de criterio."""
    fig = go.Figure()
    def _trace(x, y, nombre, color, tipo, yaxis):
        if tipo == 'bar':
            fig.add_trace(go.Bar(x=x, y=y, name=nombre, marker_color=color, yaxis=yaxis, opacity=0.85))
        else:
            fig.add_trace(go.Scatter(x=x, y=y, name=nombre, mode='lines+markers',
                                      line=dict(color=color, width=3), yaxis=yaxis))
    _trace(x_a, y_a, nombre_a, color_a, tipo_a, 'y1')
    _trace(x_b, y_b, nombre_b, color_b, tipo_b, 'y2')
    fig.update_layout(
        title=titulo,
        yaxis=dict(title=nombre_a, title_font=dict(size=10, color=color_a), tickfont=dict(color=color_a),
                   range=[0, _techo_apilado(y_a)], side='left'),
        yaxis2=dict(title=nombre_b, title_font=dict(size=10, color=color_b), tickfont=dict(color=color_b),
                    range=[0, _techo_apilado(y_b)], overlaying='y', side='right', showgrid=False),
        legend=dict(orientation='h', yanchor='top', y=-0.25, xanchor='center', x=0.5))
    mostrar(fig)
def sparkline(valores, color=None, invertir=False):
    """Minigráfico de tendencia para meter dentro de una tarjeta de KPI.
    Con 12-15 rondas, un número solo no dice nada: la forma de la serie sí."""
    serie = [v for v in valores if v is not None and not pd.isna(v)]
    if len(serie) < 2:
        return None
    color = color or BRAND_ACCENT
    fig = go.Figure(go.Scatter(y=serie, mode='lines', line=dict(color=color, width=2),
                                fill='tozeroy', fillcolor='rgba(179,38,30,0.10)', hoverinfo='skip'))
    fig.update_layout(height=46, margin=dict(l=0, r=0, t=0, b=0),
                       paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       xaxis=dict(visible=False), yaxis=dict(visible=False, autorange='reversed' if invertir else True),
                       showlegend=False)
    return fig
def chart_bullet(titulo, valor_fondo, valor_frente, tipo, nombre_fondo='Proyectado', nombre_frente='Real',
                  color_excedente=None):
    """Barra de progreso con desborde apilado: `valor_fondo` (Proyectado, o Punto de Equilibrio) define
    el 100% = el largo de la pista de referencia. `valor_frente` (Real) se dibuja como relleno DENTRO
    de esa pista; si la supera, el excedente se apila como un segmento aparte que sobresale del final
    de la pista en vez de superponer dos barras independientes (diseño anterior) -- así se ve de un
    vistazo si el Real se pasó del Proyectado y por cuánto, no solo que son distintos.

    `color_excedente` tiñe ese segmento de sobra: quien llama puede pasar el color que corresponda a
    si pasarse del Proyectado es favorable o no para esa métrica puntual (ej. superar el Punto de
    Equilibrio es bueno; superar una Deuda CP no planificada, no) -- por defecto un ámbar neutro
    ('se pasó de la referencia', sin prejuzgar si es bueno o malo) para cuando no se sabe.

    Reutilizado por la Fila 2 de la Comparativa Plan vs. Real (Proyectado vs. Real) y por el gráfico
    de Punto de Equilibrio de Operaciones (Volumen de Equilibrio vs. Volumen Real Vendido)."""
    if valor_fondo is None or valor_frente is None:
        return st.info('Sin dato para graficar.')
    plan, real = float(valor_fondo), float(valor_frente)
    color_excedente = color_excedente or COLOR_METRICA['riesgo']
    color_ref = 'rgba(255,255,255,0.5)' if es_modo_oscuro() else 'rgba(26,23,20,0.5)'
    fig = go.Figure()
    if plan > 0:
        # Normalizado a % del Proyectado: la pista siempre mide 100 = Plan, así el "se pasó de largo"
        # es directamente visual (el segmento de excedente empieza justo donde termina la pista) y
        # comparable entre KPIs de escalas muy distintas (USD, unidades, %) en la misma fila de columnas.
        pct_real = real / plan * 100
        dentro = min(pct_real, 100)
        excedente = max(0.0, pct_real - 100)
        fig.add_trace(go.Bar(x=[100], y=[''], orientation='h', name=nombre_fondo, base=0, width=0.55,
                              marker_color='rgba(140,151,166,0.30)', hoverinfo='skip'))
        fig.add_trace(go.Bar(x=[dentro], y=[''], orientation='h', name=nombre_frente, base=0, width=0.55,
                              marker_color=BRAND_ACCENT,
                              hovertemplate=f'{nombre_frente}: {_fmt_valor_cg(real, tipo)}<extra></extra>'))
        if excedente > 0:
            fig.add_trace(go.Bar(x=[excedente], y=[''], orientation='h', name='Excedente sobre el plan',
                                  base=100, width=0.55, marker_color=color_excedente,
                                  hovertemplate=f'Excedente: +{pct_real - 100:,.1f} p.p. sobre el plan<extra></extra>'))
        # BUG REPORTADO Y CONFIRMADO (Playwright, caso real "Punto de Equilibrio" con Ronda 1 de
        # CADIZ, donde Real = 302.8% del plan): la pista de referencia (nombre_fondo, gris muy claro)
        # queda TOTALMENTE tapada en cuanto dentro llega a 100 -- porque barmode='overlay' dibuja la
        # barra de "Real" exactamente encima, mismo ancho y misma fila. El resultado: solo se ven los
        # colores de "Real" y "Excedente", la referencia desaparece del todo salvo por su nombre en la
        # leyenda -- que es justo el reporte del equipo ("el punto de equilibrio no se ve"). La línea
        # punteada de acá abajo YA marcaba el 100% pero sin ninguna etiqueta -- ahora lleva el nombre
        # de la referencia (nombre_fondo) escrito directamente sobre el gráfico, así el dato clave
        # (dónde está el equilibrio) queda visible pase lo que pase con las barras de abajo.
        fig.add_vline(x=100, line_dash='dot', line_width=1.5, line_color=color_ref,
                      annotation_text=nombre_fondo, annotation_position='top',
                      annotation_font_size=11, annotation_font_color=color_ref)
        fig.update_layout(barmode='overlay', title=titulo, xaxis_title=None,
                           xaxis=dict(ticksuffix='%', range=[0, max(100, pct_real) * 1.15]),
                           legend=dict(orientation='h', yanchor='top', y=-0.25, xanchor='center', x=0.5))
        mostrar(fig, ocultar_eje_valores='y')
        cumplimiento = f' ({pct_real:,.1f}% del plan)'
    else:
        # Proyectado <= 0: expresarlo como % del plan no tiene sentido (división por ~0) -- se cae a
        # una barra simple en valor absoluto, sin pista de referencia, y se avisa en el caption.
        fig.add_trace(go.Bar(x=[real], y=[''], orientation='h', name=nombre_frente, marker_color=BRAND_ACCENT, width=0.55))
        fig.update_layout(title=titulo, xaxis_title=None, showlegend=False)
        mostrar(fig, ocultar_eje_valores='y')
        cumplimiento = ' — Proyectado ≤ 0, no expresable como % de avance'
    st.caption(f'{nombre_fondo}: {_fmt_valor_cg(plan, tipo)} · {nombre_frente}: {_fmt_valor_cg(real, tipo)}{cumplimiento}')

# --- COMPARATIVA PLAN VS. REAL: Proyectado (CADIZ_Gestion_v2.xlsx, vía export_proyeccion.py) vs.
# Real (RDOS de CESIM, ya parseados más arriba por cesim_parser) ---
def _fmt_valor_cg(v, tipo):
    if v is None:
        return '—'
    if tipo == 'usd':
        return format_num(v)
    if tipo == 'unidades':
        return f'{format_num(v)} u.'
    if tipo == 'usd_accion':
        return f'USD {v:,.2f}'
    if tipo == 'ratio':
        return f'{v * 100:,.1f}%'
    return str(v)
def _fmt_delta_cg(v):
    if v['estado'] != 'ok' or v['gap_abs'] is None:
        return None
    if v['tipo'] == 'usd':
        # Ronda con status=REAL en ambos lados (histórico ya migrado) da un gap de centavos por
        # redondeo de punto flotante entre el motor Python y el motor Excel -- no es un gap real y
        # mostrarlo como "-0" confundiría; se redondea al dólar y se omite si queda en 0.
        gap_redondeado = round(v['gap_abs'])
        return format_num(gap_redondeado) if gap_redondeado != 0 else None
    if v['tipo'] == 'unidades':
        gap_redondeado = round(v['gap_abs'])
        return f'{gap_redondeado:+,.0f} u.' if gap_redondeado != 0 else None
    if v['tipo'] == 'usd_accion':
        return f"{v['gap_abs']:+,.2f}"
    if v['tipo'] == 'ratio':
        return f"{v['gap_abs'] * 100:+.1f} p.p."
    return None
_DELTA_COLOR_CG = {'real_mayor': 'normal', 'real_menor': 'inverse', None: 'off'}
# Mismo mapeo de favorabilidad que _DELTA_COLOR_CG, pero como color de relleno para el segmento de
# excedente de chart_bullet(): si más Real es mejor (real_mayor), pasarse del plan es favorable
# (verde). Para 'real_menor' (ej. deuda no planificada) se probó primero con BRAND_ACCENT (rojo) para
# marcarlo como desfavorable, pero es EL MISMO rojo que ya usa el relleno "Real" del propio bullet --
# el segmento de excedente quedaba invisible, fundido con la barra (ver test visual). Ámbar neutro
# funciona para ambos casos sin esa colisión: sigue leyéndose como "atención, se pasó de la
# referencia" sea o no favorable (la flecha de color del delta, un renglón más arriba, ya dice si eso
# es bueno o malo).
_COLOR_EXCEDENTE_CG = {'real_mayor': COLOR_POSITIVE, 'real_menor': COLOR_METRICA['riesgo'], None: COLOR_METRICA['riesgo']}
def panel_comparativa_plan_real(df_todas_rondas, ronda_snapshot, crosswalk=None, key_suffix='', mostrar_directo=False):
    """Botón 'Comparativa Plan vs. Real': Proyectado (nuestro modelo) vs. Real (RDOS de CESIM) para los
    KPIs del crosswalk dado. Un KPI sin proyección para esta ronda (el modelo no lo cubre, o es una
    ronda de Práctica que el modelo no proyecta) o sin dato real todavía (CESIM no publicó esta
    ronda) no se omite en silencio: cae al gráfico de evolución de esa variable.

    mostrar_directo=True se salta el toggle y renderiza directo -- para cuando esta es la ÚNICA
    razón de estar en la página (p.ej. CESIM todavía no publicó ningún RDOS de esta ronda: no hay
    nada más que mostrar en el resto de las secciones, así que no tiene sentido esconder esto detrás
    de un clic extra)."""
    crosswalk = crosswalk or CROSSWALK_FINANZAS
    if not mostrar_directo:
        activo = st.toggle('📊 Comparativa Plan vs. Real', key=f'cg_toggle_{key_suffix}')
        if not activo:
            return
    df_proy = get_proyeccion()
    if df_proy is None:
        st.info('Todavía no se subió `CADIZ_Gestion_v2.xlsx` a la raíz del repo (o no se pudo leer '
                'la hoja `DATA_EXPORT`) — subilo con ese mismo nombre para ver la Comparativa Plan vs. Real.')
        return
    ronda_num = ronda_a_num(ronda_snapshot)
    claves_no_publicadas = {k for k, spec in crosswalk.items() if spec.get('real_no_publicado')}
    gaps_todos = calcular_gaps(df_todas_rondas, df_proy, ronda_nombre=ronda_snapshot, ronda_num=ronda_num, crosswalk=crosswalk)
    gaps = {k: v for k, v in gaps_todos.items() if k not in claves_no_publicadas}
    sin_publicar = {k: v for k, v in gaps_todos.items() if k in claves_no_publicadas}
    con_gap = {k: v for k, v in gaps.items() if v['estado'] in ('ok', 'sin_real')}
    sin_gap = {k: v for k, v in gaps.items() if v['estado'] in ('sin_datos', 'sin_proyeccion')}
    with st.container(border=True):
        st.markdown(f'**Comparativa Plan vs. Real — {ronda_snapshot}**')
        if not con_gap:
            st.caption('CADIZ no tiene una proyección cargada para esta ronda en el modelo de gestión — '
                       'ver la evolución de cada indicador más abajo.')
        else:
            cols = st.columns(min(4, len(con_gap)))
            for i, (clave, v) in enumerate(con_gap.items()):
                with cols[i % len(cols)]:
                    if v['estado'] == 'sin_real':
                        st.metric(v['label'], _fmt_valor_cg(v['proyectado'], v['tipo']))
                        st.caption('Proyectado (CADIZ) — real de CESIM pendiente')
                    else:
                        st.metric(v['label'], _fmt_valor_cg(v['real'], v['tipo']),
                                   delta=_fmt_delta_cg(v), delta_color=_DELTA_COLOR_CG[v['gap_favorable']])
                        st.caption(f"Real — proyectado {_fmt_valor_cg(v['proyectado'], v['tipo'])}")
            # Fila 2: bullet charts (Proyectado vs. Real superpuestos) -- solo para los KPIs que
            # tienen AMBOS valores (estado='ok'); 'sin_real' ya se ve en la tarjeta de arriba, no hay
            # nada que superponer todavía.
            # tipo='texto' (ej. Calificación crediticia) no tiene sentido como barra -- ya se ve
            # completo en la tarjeta de Fila 1 (valor + "Real — proyectado ...").
            con_ambos = {k: v for k, v in con_gap.items() if v['estado'] == 'ok' and v['tipo'] != 'texto'}
            if con_ambos:
                st.markdown('###### Proyectado vs. Real')
                cols_b = st.columns(min(4, len(con_ambos)))
                for i, (clave, v) in enumerate(con_ambos.items()):
                    with cols_b[i % len(cols_b)]:
                        # Mismo criterio de favorabilidad que ya colorea la flecha del delta en la
                        # tarjeta de arriba (_DELTA_COLOR_CG) -- así el excedente de la barra de
                        # progreso no contradice al delta que el usuario ya vio un renglón más arriba.
                        chart_bullet(v['label'], v['proyectado'], v['real'], v['tipo'],
                                     color_excedente=_COLOR_EXCEDENTE_CG.get(v['gap_favorable']))
        if sin_gap or sin_publicar:
            st.caption('Sin comparación posible para estos indicadores (no forman parte de la '
                       'proyección de CADIZ, es una ronda de práctica, o CESIM no publica ese dato en '
                       'el RDOS) — se muestra su evolución:')
    if sin_gap or sin_publicar:
        total = len(sin_gap) + len(sin_publicar)
        cols_ev = st.columns(min(2, total))
        i = 0
        for clave, v in sin_gap.items():
            spec = crosswalk[clave]['real']
            sub = df_todas_rondas[(df_todas_rondas['Estado'] == spec['estado']) & (df_todas_rondas['Metrica'] == spec['metrica'])]
            if spec.get('seccion'):
                sub = sub[sub['Seccion'] == spec['seccion']]
            with cols_ev[i % len(cols_ev)]:
                chart_evolucion(sub, v['label'])
            i += 1
        for clave, v in sin_publicar.items():
            spec = crosswalk[clave]['proyeccion']
            with cols_ev[i % len(cols_ev)]:
                chart_evolucion_proyeccion(df_proy, spec['metric'], spec['region'], v['label'])
                st.caption('CESIM no publica este dato en el RDOS — evolución de la proyección propia de CADIZ.')
            i += 1

# --- Fila 3 de la Comparativa Plan vs. Real: gráficos de GAP/varianza específicos por sección
# (Adenda 12). Cada uno se llama desde la pestaña "Comparativa Plan vs. Real" de su propia sección
# (no desde panel_comparativa_plan_real, que es genérico y no conoce estas métricas de grano fino
# por mercado/tecnología/área) -- y solo tiene sentido con team=CADIZ (son cruces contra SU propia
# proyección en CADIZ_Gestion_v2.xlsx). ---
def fila3_resultados_ingresos(df_all, ronda_snapshot, ronda_num, df_proy):
    st.markdown('###### Análisis de Desvíos de Ingresos — Precio / Volumen / Mix')
    mercado_sel = st.selectbox('Mercado', _MERCADOS_GAP, key='sel_cg_resultados_mercado')
    datos = precio_volumen_mercado(df_all, df_proy, ronda_snapshot, ronda_num, mercado_sel, team=MY_COMPANY)
    if not datos:
        st.info(f'CADIZ no tiene datos de precio/volumen (Plan o Real) en {mercado_sel} para {ronda_snapshot}.')
        return
    if all(d['precio_plan'] is None for d in datos.values()):
        # Sin ESTO, el waterfall tomaría Plan=0 como línea base y le atribuiría el 100% de los
        # Ingresos Reales al "Desvío por Precio" -- un artefacto de la falta de dato, no un desvío
        # real. El modelo de CADIZ solo proyecta desde Ronda 2 (Ronda 0/1 no tienen Plan cargado).
        st.info(f'CADIZ no tiene una proyección de Precio/Volumen cargada para {mercado_sel} en {ronda_snapshot} '
                '— el modelo de gestión proyecta recién desde Ronda 2, no hay Plan con el que comparar.')
        return
    var = variacion_precio_volumen_mix(datos)
    if not var['reconciliacion_ok']:
        st.warning('El desglose Precio/Volumen/Mix no reconcilia exactamente con la variación de Ingresos — revisar.')
    etapas = [('Ingresos Proyectados', var['ingresos_plan']), ('Desvío por Precio', var['var_precio']),
              ('Desvío por Volumen', var['var_volumen']), ('Desvío por Mix', var['var_mix']),
              ('Ingresos Reales', var['ingresos_real'])]
    fig = go.Figure(go.Waterfall(
        orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'total'],
        x=[e[0] for e in etapas], y=[e[1] for e in etapas],
        text=[format_num(v) for _, v in etapas], textposition='outside',
        # Color = favorable/desfavorable para CADIZ (verde/ámbar), no "sube/baja" -- antes el desvío
        # desfavorable usaba MUTED_PALETTE[2], un verde grisáceo casi del mismo matiz que el favorable
        # (COLOR_POSITIVE): a simple vista ambos leían "verde" y no se distinguía cuál desvío ayudó y
        # cuál perjudicó. Ahora es el mismo par verde/ámbar que el resto de los gráficos de desvío.
        increasing={'marker': {'color': COLOR_POSITIVE}}, decreasing={'marker': {'color': COLOR_METRICA['riesgo']}},
        totals={'marker': {'color': BRAND_ACCENT}}))
    fig.update_layout(title=f'Ingresos — Proyectado vs. Real, {mercado_sel} ({_MONEDA_MERCADO_GAP[mercado_sel]})')
    mostrar(fig, ocultar_eje_valores='y')
    st.caption(f'Verde = desvío que sumó Ingresos; ámbar = desvío que restó. En moneda nativa de {mercado_sel} '
               f'({_MONEDA_MERCADO_GAP[mercado_sel]}) — no se convierte a USD para no asumir un tipo de cambio '
               'que el simulador no publica.')

def fila3_mercado_cuota_objetivo(df_all, ronda_snapshot, ronda_num, df_proy):
    st.markdown('###### Cuota de mercado — Proyectado vs. Real, por tecnología')
    mercado_sel = st.selectbox('Mercado', _MERCADOS_GAP, key='sel_cg_mercado_cuota')
    datos = cuota_mercado_objetivo_vs_real(df_all, df_proy, ronda_snapshot, ronda_num, mercado_sel, team=MY_COMPANY)
    if not datos:
        st.info(f'Sin datos de cuota objetivo/real en {mercado_sel} para {ronda_snapshot}.')
        return
    filas = []
    for tech, d in datos.items():
        # "Proyectado" en todos lados (antes decía "Objetivo (Plan)" acá, distinto del resto de la
        # Comparativa) -- mismo término que chart_bullet, la Fila 1 de KPIs y las demás Filas 3.
        if d['objetivo'] is not None:
            filas.append({'Tecnología': tech, 'Tipo': 'Proyectado', 'Cuota': d['objetivo'] * 100})
        if d['real'] is not None:
            filas.append({'Tecnología': tech, 'Tipo': 'Real', 'Cuota': d['real'] * 100})
    if not filas:
        return st.info('Sin datos suficientes.')
    dfc = pd.DataFrame(filas)
    fig = px.bar(dfc, x='Tecnología', y='Cuota', color='Tipo', barmode='group',
                 color_discrete_map={'Proyectado': MUTED_PALETTE[0], 'Real': BRAND_ACCENT},
                 text=dfc['Cuota'].apply(lambda v: f'{v:.1f}%'), title=f'Cuota de mercado — {mercado_sel}, {ronda_snapshot}')
    fig.update_traces(textposition='outside', cliponaxis=False)
    fig.update_layout(yaxis_title='% del mercado total')
    mostrar(fig)
    st.caption('Cuota = ventas de CADIZ en esa tecnología / tamaño TOTAL del mercado (las 4 tecnologías) — '
               'misma convención en Plan y Real (distinta de la que el RDOS publica directo por tecnología, '
               'ver nota metodológica en gap_analysis.cuota_mercado_objetivo_vs_real). '
               'Ojo con leerla junto al gráfico de "Demanda estimada" de más arriba: el Proyectado de ESTA '
               'cuota se calculó contra el tamaño de mercado que el modelo había asumido al planificar; el '
               'Real se calcula contra el tamaño que terminó publicando CESIM. Si la demanda real vino más '
               'chica que la proyectada, la cuota puede salir MÁS ALTA que el objetivo aunque el volumen '
               'propio en unidades haya sido menor al planeado — no es una contradicción entre los dos '
               'gráficos, es la misma torta más chica repartida distinto.')

def _costo_fabricacion_ponderado(datos_area):
    """A partir de costo_unitario_area(): costo unitario de fabricación PONDERADO por producción REAL
    (propia + contratada), Plan vs. Real, y el GAP que aporta cada tecnología al total — usa los
    MISMOS pesos (producción real) para ponderar Plan y Real, así el desglose por tecnología
    reconcilia EXACTO con la diferencia total (no es una aproximación)."""
    filas = []
    prod_total = 0.0
    for tech, d in datos_area.items():
        prod_p, prod_t = d['prod_propia_real'], d['prod_terc_real']
        prod_tech = prod_p + prod_t
        if prod_tech <= 0:
            continue
        plan_tech = ((d['cu_propia_plan'] or 0) * prod_p + (d['cu_terc_plan'] or 0) * prod_t) / prod_tech
        real_tech = ((d['cu_propia_real'] or 0) * prod_p + (d['cu_terc_real'] or 0) * prod_t) / prod_tech
        filas.append({'tech': tech, 'prod': prod_tech, 'plan': plan_tech, 'real': real_tech})
        prod_total += prod_tech
    if prod_total <= 0:
        return None
    plan_pond = sum(f['prod'] * f['plan'] for f in filas) / prod_total
    real_pond = sum(f['prod'] * f['real'] for f in filas) / prod_total
    gaps = [{'tech': f['tech'], 'gap': (f['real'] - f['plan']) * f['prod'] / prod_total} for f in filas]
    return {'plan_pond': plan_pond, 'real_pond': real_pond, 'gaps': gaps}

def fila3_operaciones_gap_fabricacion(df_all, ronda_snapshot, ronda_num, df_proy):
    st.markdown('###### Desvío en Costo Unitario de Fabricación (Proyectado vs. Real)')
    st.caption('Alcance: solo costo de FABRICACIÓN (propia + contratada), ponderado por producción real. '
               'Transporte/aranceles y promoción se reportan por mercado de destino (no por área de origen) '
               'y no están incluidos acá — por eso este desvío no reconcilia el 100% de la Contribución '
               'Marginal unitaria completa.')
    area_sel = st.selectbox('Área de producción', _AREAS_GAP, key='sel_cg_operaciones_area')
    datos = costo_unitario_area(df_all, df_proy, ronda_snapshot, ronda_num, area_sel, team=MY_COMPANY)
    if not datos:
        return st.info(f'Sin datos de costo unitario de fabricación en {area_sel} para {ronda_snapshot}.')
    if all(d['cu_propia_plan'] is None and d['cu_terc_plan'] is None for d in datos.values()):
        # Mismo motivo que en el waterfall de Ingresos: sin esto, Proyectado=0 le atribuiría el 100%
        # del costo real a un "Desvío" que en realidad es solo ausencia de proyección (Ronda 0/1,
        # antes de que el modelo de CADIZ empezara a proyectar en Ronda 2).
        return st.info(f'CADIZ no tiene una proyección de costo unitario cargada para {area_sel} en {ronda_snapshot} '
                        '— el modelo de gestión proyecta recién desde Ronda 2, no hay Plan con el que comparar.')
    pond = _costo_fabricacion_ponderado(datos)
    if not pond:
        return st.info(f'Sin datos de producción real en {area_sel} para {ronda_snapshot}.')
    # "Desvío {tecnología}" (antes "GAP {tecnología}", en inglés y sin explicar qué significa): cuánto
    # empujó ESA tecnología al costo unitario PONDERADO total, de Proyectado a Real -- no es "cuánto le
    # costó de más esa tecnología en el vacío", es su aporte a la diferencia total, ponderado por su
    # propia producción real. La suma de todos los "Desvío X" + Costo Proyectado da EXACTO el Costo
    # Real (reconciliación por construcción, ver _costo_fabricacion_ponderado) -- por eso tiene sentido
    # como cascada/waterfall y no como barras sueltas.
    etapas = [('Costo Proyectado', pond['plan_pond'])]
    for g in pond['gaps']:
        if abs(g['gap']) > 1e-9:
            etapas.append((f"Desvío {g['tech']}", g['gap']))
    etapas.append(('Costo Real', pond['real_pond']))
    fig = go.Figure(go.Waterfall(
        orientation='v', measure=['absolute'] + ['relative'] * (len(etapas) - 2) + ['total'],
        x=[e[0] for e in etapas], y=[e[1] for e in etapas],
        text=[format_num(v) for _, v in etapas], textposition='outside',
        # Verde = desvío que ayudó a bajar el costo (favorable); ámbar = lo empujó hacia arriba
        # (desfavorable) -- mismo par de colores y mismo criterio (favorable/desfavorable, no
        # sube/baja) que el waterfall de Ingresos de más arriba. Antes usaba MUTED_PALETTE[2] (un
        # verde grisáceo) para el costo que SUBE y COLOR_POSITIVE (verde pleno) para el que BAJA --
        # dos verdes casi del mismo matiz para significados opuestos, imposible de leer de un vistazo.
        increasing={'marker': {'color': COLOR_METRICA['riesgo']}}, decreasing={'marker': {'color': COLOR_POSITIVE}},
        totals={'marker': {'color': BRAND_ACCENT}}))
    fig.update_layout(title=f'Costo unitario de fabricación — {area_sel}, {ronda_snapshot}')
    mostrar(fig, ocultar_eje_valores='y')
    st.caption('Cada barra "Desvío {tecnología}" es cuánto empujó esa tecnología el costo unitario ponderado '
               'total, de Proyectado a Real (ponderado por su propia producción real) — no el costo de esa '
               'tecnología en sí. Verde = empujó el costo hacia abajo (favorable); ámbar = lo empujó hacia '
               'arriba. Costo Proyectado + todos los desvíos = Costo Real, exacto.')

def fila3_finanzas_flujo_caja(df_all, ronda_snapshot, ronda_num, df_proy):
    st.markdown('###### Composición del Flujo de Caja — Plan vs. Real (Global)')
    res = flujo_caja_plan_real_global(df_all, df_proy, ronda_snapshot, ronda_num, team=MY_COMPANY)
    plan, real = res['plan'], res['real']
    etiquetas = {'cfo': 'Act. Operativas (CFO)', 'cfi': 'Act. de Inversión (CFI)', 'cff': 'Act. Financieras (CFF)'}
    filas = []
    for k, label in etiquetas.items():
        if plan.get(k) is not None:
            filas.append({'Componente': label, 'Tipo': 'Proyectado', 'Valor': plan[k]})
        if real.get(k) is not None:
            filas.append({'Componente': label, 'Tipo': 'Real', 'Valor': real[k]})
    if not filas:
        return st.info(f'Sin datos de Flujo de Caja (Plan o Real) para {ronda_snapshot}.')
    dff = pd.DataFrame(filas)
    fig = px.bar(dff, x='Componente', y='Valor', color='Tipo', barmode='group',
                 color_discrete_map={'Proyectado': MUTED_PALETTE[0], 'Real': BRAND_ACCENT},
                 text=dff['Valor'].apply(format_num), title=f'Composición del Flujo de Caja — Global, {ronda_snapshot}')
    fig.update_traces(textposition='outside', cliponaxis=False)
    mostrar(fig, ocultar_eje_valores='y')
    if all(plan.get(k) is None for k in etiquetas):
        st.caption('CADIZ no proyecta Flujo de Caja para esta ronda en el modelo de gestión (recién desde Ronda 2).')
    if all(real.get(k) is None for k in etiquetas):
        st.caption('CESIM todavía no publicó el RDOS real de esta ronda — se muestra solo lo proyectado.')

def serie_metrica(estado, metrica, empresa=None, hasta_orden=None, seccion=None):
    """Serie histórica de una métrica para un equipo, ordenada por ronda.
    OJO con 'seccion': hay métricas cuyo nombre se repite dentro del mismo estado
    (ej. 'Total' aparece en Accionistas, Acreedores, Gobierno, Personal y Proveedores
    dentro de Creación de Valor). Sin filtrar por sección se mezclan cinco series distintas."""
    d = df_all[(df_all['Estado'] == estado) & (df_all['Metrica'] == metrica)].copy()
    if seccion: d = d[d['Seccion'] == seccion]
    if empresa: d = d[d['Empresa'] == empresa]
    if d.empty: return []
    d['Valor'] = num(d['Valor'])
    if hasta_orden is not None:
        d = d[d['Ronda_Orden'] <= hasta_orden]
    return d.sort_values('Ronda_Orden')['Valor'].tolist()

def kpi_con_tendencia(col, label, valor_txt, serie, delta=None, color=None, invertir=False):
    """Tarjeta de KPI + sparkline debajo, para ver nivel y tendencia sin cambiar de sección."""
    with col:
        st.metric(label, valor_txt, delta=delta)
        fig = sparkline(serie, color=color, invertir=invertir)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
def kpi_banda_oscura(items):
    """Banda oscura para los 2-3 KPIs de valor MÁS importantes de la ronda (los que le interesan
    a un accionista) -- los separa visualmente del resto de tarjetas claras en vez de competir al
    mismo nivel, estilo el bloque "Monto Pendiente / A vencer / Ya pagado" de la referencia. Es
    HTML de una sola pieza (no columnas + st.metric) porque no hay forma segura de "abrir" un div
    oscuro con un st.markdown y "cerrarlo" varios st.* después -- cada items[i] es un dict con
    'label', 'valor' (ya formateado) y opcionalmente 'delta' (texto) + 'favorable' (True/False/None
    para pintar el delta verde/rojo; None lo deja neutro)."""
    piezas = []
    for it in items:
        delta_html = ''
        if it.get('delta'):
            # OJO: "favorable" suele venir de comparar floats de pandas/numpy (ej. delta > 0), que da
            # numpy.bool_ -- "is False" falla por identidad contra ese tipo aunque el valor sea
            # correcto (numpy.bool_(False) is False → False). Sin comparación de identidad.
            fav = it.get('favorable')
            clase = '' if fav is None else ('up' if fav else 'down')
            delta_html = f'<div class="kpi-band-delta {clase}">{it["delta"]}</div>'
        piezas.append(f'<div class="kpi-band-item"><div class="kpi-band-label">{it["label"]}</div>'
                       f'<div class="kpi-band-value">{it["valor"]}</div>{delta_html}</div>')
    # En modo oscuro nativo de Streamlit la banda necesita distinguirse por color, no por
    # oscuridad -- ver el comentario junto a ".kpi-band-oscura.tema-oscuro" en style.css.
    clase_tema = ' tema-oscuro' if es_modo_oscuro() else ''
    st.markdown(f'<div class="kpi-band-oscura{clase_tema}">{"".join(piezas)}</div>', unsafe_allow_html=True)

# ---------------- Panel de alertas ----------------
def evaluar_alertas():
    """Corre un set de reglas sobre la ronda en foco y devuelve solo lo que se está prendiendo.
    La idea es no tener que recorrer las 5 secciones para enterarse de que algo se rompió."""
    alertas = []
    bal = df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]
    ratios = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)]

    # --- Liquidez: el sobregiro automático de Cesim es un hecho del reporte, no un umbral nuestro
    deuda_cp = valor_de(bal, 'Deudas a corto plazo (no planificadas)', empresa_analisis)
    if deuda_cp and deuda_cp > 0:
        alertas.append(('critico', 'Sobregiro automático',
                        f'{format_num(deuda_cp)} USD de deuda de corto plazo NO planificada: la caja no alcanzó '
                        'para cubrir obligaciones. Suele venir con tasa de interés penal.'))

    orden_hoy = df[df['Ronda'] == ronda_snapshot]['Ronda_Orden'].iloc[0] if not df[df['Ronda'] == ronda_snapshot].empty else None

    # NOTA: hubo acá una alerta "I+D fuera de lo común" (Categoría 3, supuesto propio de CADIZ) que
    # vigilaba gasto de I+D récord + por encima del promedio de rivales, como indicio temprano de
    # tecnología nueva en camino. Se sacó a pedido del equipo (ensuciaba el panel y no aportaba
    # suficiente valor accionable) -- la detección CONFIRMADA de tecnología nueva (Categoría 2, un
    # hecho, no una estimación) sigue más abajo en "Entrada a tecnología nueva de la competencia".

    # --- Tendencias: dos rondas seguidas en la misma dirección. No hay número inventado acá,
    #     es la propia serie del reporte la que define si viene cayendo o subiendo.
    def dos_rondas_seguidas(estado, metrica, etiqueta, detalle, subiendo=False, seccion=None):
        serie = serie_metrica(estado, metrica, empresa_analisis, hasta_orden=orden_hoy, seccion=seccion)
        serie = [v for v in serie if v is not None and not pd.isna(v)]
        if len(serie) < 3: return
        d1, d2 = serie[-1] - serie[-2], serie[-2] - serie[-3]
        if (d1 > 0 and d2 > 0) if subiendo else (d1 < 0 and d2 < 0):
            alertas.append(('aviso', etiqueta, detalle.format(a=serie[-3], b=serie[-1])))

    dos_rondas_seguidas('Ratios e indicadores financieros clave', 'Retorno total acumulado del accionista (p.a.), %',
                        'Retorno del accionista en baja', 'Cayó dos rondas seguidas: de {a:,.1f}% a {b:,.1f}%.')
    dos_rondas_seguidas('Hoja de Balance, miles USD, Global', 'Inventario',
                        'Inventario acumulándose', 'Creció dos rondas seguidas — capital inmovilizado.', subiendo=True)

    # --- Cambios vs. la ronda anterior: se compara el dato de una ronda contra el de la otra,
    #     sin definir qué valor es "bueno" o "malo".
    ordenes = sorted(df['Ronda_Orden'].dropna().unique())
    orden_prev = None
    if orden_hoy in ordenes:
        i = ordenes.index(orden_hoy)
        orden_prev = ordenes[i - 1] if i > 0 else None

    if orden_prev is not None:
        ronda_prev = df[df['Ronda_Orden'] == orden_prev]['Ronda'].iloc[0]
        ratios_prev = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda_Orden'] == orden_prev)]

        # Posición en el ranking de retorno del accionista
        def puesto(tabla):
            vals = {e: valor_de(tabla, 'Retorno total acumulado del accionista (p.a.), %', e) for e in COMPANIES}
            rk = sorted([e for e in vals if vals.get(e) is not None], key=vals.get, reverse=True)
            return rk.index(empresa_analisis) + 1 if empresa_analisis in rk else None
        p_hoy, p_ant = puesto(ratios), puesto(ratios_prev)
        if p_hoy is not None and p_ant is not None and p_hoy != p_ant:
            nivel = 'aviso' if p_hoy > p_ant else 'ok'
            verbo = 'Bajó' if p_hoy > p_ant else 'Subió'
            alertas.append((nivel, f'{verbo} del {p_ant}° al {p_hoy}° puesto',
                            f'Ranking de retorno del accionista, contra {ronda_prev}.'))

        # Calificación crediticia: se reporta el cambio, sin juzgar qué letra es aceptable
        calif_hoy = valor_texto(ratios, 'Calificación crediticia', empresa_analisis)
        calif_ant = valor_texto(ratios_prev, 'Calificación crediticia', empresa_analisis)
        if calif_hoy and calif_ant and str(calif_hoy).strip() != str(calif_ant).strip():
            alertas.append(('aviso', 'Cambió la calificación crediticia',
                            f'De {str(calif_ant).strip()} a {str(calif_hoy).strip()} respecto de {ronda_prev}.'))

        # --- Entrada CONFIRMADA de LA COMPETENCIA a una tecnología nueva: a diferencia del aviso de
        #     I+D de arriba (estimativo, y ciego a la vía de licencia), esto es un HECHO -- Categoría
        #     2, dato real de CESIM, sin ninguna estimación de nuestra parte. El manual describe DOS
        #     caminos para sumar tecnología (I+D propio o comprar una licencia, disponible de
        #     inmediato) y esta alerta los cubre a los dos por igual: no le importa CÓMO la consiguió
        #     el rival, solo que efectivamente ya la tiene y la está vendiendo -- verificado con la
        #     cuota de mercado real que CESIM publica por (país, tecnología) para los 7 equipos
        #     (`Informe de mercado, {país} → Seccion='{país} cuotas de mercado, %' → Metrica=
        #     tecnología`, el mismo campo que ya usa `cuota_mercado_objetivo_vs_real` en
        #     gap_analysis.py). Se dispara cuando un rival pasa de 0% en la ronda anterior a >0% en
        #     esta, en una tecnología/país donde antes no vendía nada -- vigila a todos los rivales
        #     siempre, igual que las otras alertas de competencia.
        #
        #     Aparece recién cuando ya hubo ventas reales (una ronda más tarde que la inversión en
        #     I+D si fue por esa vía, o la misma ronda si fue por licencia) -- llega después que el
        #     aviso de I+D, pero sin ninguna ambigüedad sobre qué tecnología es.
        #
        #     Se consolida en UN solo aviso (mismo patrón que "Movimientos de capacidad de la
        #     competencia" más abajo) en vez de una tarjeta por cada combinación: cuando una
        #     tecnología recién se habilita para toda la industria, pueden entrar 3-4 equipos juntos
        #     en la misma ronda, y una tarjeta idéntica repetida 4 veces satura el panel sin agregar
        #     información nueva en cada una.
        entradas_tech = []
        for pais in _MERCADOS_GAP:
            cuota_hoy = df[(df['Estado'] == f'Informe de mercado, {pais}') &
                           (df['Seccion'] == f'{pais} cuotas de mercado, %') &
                           (df['Ronda_Orden'] == orden_hoy) & (df['Empresa'] != MY_COMPANY)].copy()
            cuota_prev = df[(df['Estado'] == f'Informe de mercado, {pais}') &
                             (df['Seccion'] == f'{pais} cuotas de mercado, %') &
                             (df['Ronda_Orden'] == orden_prev) & (df['Empresa'] != MY_COMPANY)].copy()
            if cuota_hoy.empty: continue
            cuota_hoy['Valor'] = num(cuota_hoy['Valor'])
            cuota_prev['Valor'] = num(cuota_prev['Valor'])
            for tech in _TECNOLOGIAS_GAP:
                hoy_t = cuota_hoy[cuota_hoy['Metrica'] == tech].dropna(subset=['Valor']).set_index('Empresa')['Valor']
                prev_t = cuota_prev[cuota_prev['Metrica'] == tech].dropna(subset=['Valor']).set_index('Empresa')['Valor']
                for rival in [e for e in COMPANIES if e != MY_COMPANY]:
                    v_hoy = hoy_t.get(rival)
                    if v_hoy is None or v_hoy <= 0: continue
                    v_prev = prev_t.get(rival, 0.0)
                    if v_prev == 0:
                        entradas_tech.append(f'{rival} en {tech} ({pais}, 0% → {v_hoy:.1f}%)')
        if entradas_tech:
            detalle = (' · '.join(entradas_tech) + '. Antes no vendían nada ahí en esa tecnología — '
                       'confirmado con dato real, sin importar si la consiguieron con I+D propio o '
                       'comprando una licencia.')
            alertas.append(('aviso', 'Entrada a tecnología nueva de la competencia', detalle))

    # --- Movimientos de capacidad de LA COMPETENCIA: Cesim publica las fábricas que va a haber
    #     después de la próxima ronda, así que se sabe de antemano quién está por agrandarse o
    #     achicarse. La idea de esta alerta es específicamente vigilar a los rivales -- CADIZ ya
    #     sabe sus propias decisiones -- y hacerlo siempre, sin depender de a quién tengamos
    #     seleccionado en "Equipo en foco" (por eso se compara contra MY_COMPANY, no contra
    #     empresa_analisis: cambiar el equipo en foco para mirar otra sección no debe apagar esta
    #     vigilancia de la competencia).
    # OJO con la forma del reporte: Cesim pone el PAÍS en 'Metrica' (EE.UU. / China) y el
    # HORIZONTE en 'Subgrupo' (Ronda actual / Próxima ronda / Después de la próxima ronda).
    # Filtrando al revés no matchea nada y el conteo actual daba 0.
    #
    # Historial de este chequeo: la v1 mezclaba los 7 equipos en un solo mensaje ambiguo y solo
    # miraba subas (nunca bajas, como la reducción real de CEOS en EE.UU. 7->5 en Ronda 1) -- se
    # corrigió de más filtrando a empresa_analisis, lo cual apagaba el aviso de competencia cuando
    # el foco está en CADIZ, que es exactamente el caso de uso principal. Esta versión vuelve a
    # cubrir a todos los rivales (todo el que no sea MY_COMPANY), agrega reducciones, y desglosa
    # por área (Metrica) en vez de sumar EE.UU.+China en un solo número, que puede esconder un
    # movimiento real en un área si la otra se mueve al revés.
    #
    # Se mantiene el aviso de Ronda de práctica: verificado con datos reales que una decisión
    # cargada ahí (ensayo, ej. CADIZ China 2->3 en Práctica 2) puede no trasladarse nunca a la
    # competencia oficial (Ronda 1 mostró a CADIZ sin cambios) -- no es un compromiso real.
    #
    # FIX (reportado: "en Ronda 1 dice que CEOS expande China en las próximas 2 rondas, y en
    # Ronda 2 vuelve a decir lo mismo"): es el MISMO evento real, visto dos veces porque antes solo
    # se comparaba 'Ronda actual' contra 'Después de la próxima ronda' (fijo a 2 rondas vista) y el
    # título decía siempre "(próximas 2 rondas)" sin importar cuánto faltaba en realidad. Verificado
    # con los datos: en R1, CEOS China = 2 (actual) / 2 (próxima) / 3 (después) -> el cambio todavía
    # está a 2 rondas. En R2, CEOS China = 2 (actual) / 3 (próxima) / 3 (después) -> el MISMO cambio
    # ya está a 1 ronda -- el horizonte se acorta, pero el mensaje no lo reflejaba y parecía una
    # alerta repetida sin sentido. Ahora se mira primero 'Próxima ronda' (1 ronda vista); si ahí no
    # hay cambio, recién se usa 'Después de la próxima ronda' (2 rondas vista) -- así el aviso
    # cuenta regresiva (2 rondas -> 1 ronda) en vez de repetirse idéntico, y deja de aparecer solo
    # cuando el cambio ya se concretó en 'Ronda actual'.
    fab = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Número de fábricas') &
             (df['Ronda'] == ronda_snapshot) & (df['Empresa'] != MY_COMPANY)].copy()
    if not fab.empty:
        fab['Valor'] = num(fab['Valor'])
        act = fab[fab['Subgrupo'] == 'Ronda actual'].groupby(['Empresa', 'Metrica'])['Valor'].sum()
        prox = fab[fab['Subgrupo'] == 'Próxima ronda'].groupby(['Empresa', 'Metrica'])['Valor'].sum()
        desp = fab[fab['Subgrupo'] == 'Después de la próxima ronda'].groupby(['Empresa', 'Metrica'])['Valor'].sum()
        movimientos = []
        for clave in act.index:
            empresa, area = clave
            a = act.get(clave, 0)
            p = prox.get(clave, a)
            d = desp.get(clave, p)
            # Prioridad: el cambio más cercano en el tiempo es el que importa mostrar ahora.
            if p != a:
                destino, horizonte = p, 'la próxima ronda'
            elif d != a:
                destino, horizonte = d, 'dentro de 2 rondas'
            else:
                continue
            verbo = 'expande' if destino > a else 'reduce'
            movimientos.append(f'{empresa} {verbo} {area} ({a:.0f} → {destino:.0f}, {horizonte})')
        if movimientos:
            detalle = ' · '.join(movimientos)
            alertas.append(('aviso', 'Movimientos de capacidad de la competencia', detalle))
    return alertas

def panel_alertas():
    alertas = evaluar_alertas()
    if not alertas:
        st.markdown('<div class="stat-segment-card"><div class="stat-segment-bar"><div class="seg ok" '
                    'style="width:100%"></div></div><div class="stat-segment-legend"><span class="ok">'
                    '<span class="pt"></span>Sin alertas activas</span></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="alerta-fila ok">✅ <b>Sin alertas</b> '
                    f'<span class="detalle">— nada fuera de rango en {ronda_snapshot} para {empresa_analisis}.</span></div>',
                    unsafe_allow_html=True)
        return
    # Barra de composición por severidad -- el total es la cantidad de alertas ACTIVAS ahora
    # (no un universo fijo de "reglas evaluadas": una sola regla puede dispararse varias veces,
    # ver el comentario en assets/style.css junto a .stat-segment-card).
    n_critico = sum(1 for a in alertas if a[0] == 'critico')
    n_aviso = sum(1 for a in alertas if a[0] == 'aviso')
    n_ok = sum(1 for a in alertas if a[0] == 'ok')
    total_sev = n_critico + n_aviso + n_ok
    segs = ''.join(f'<div class="seg {niv}" style="width:{cnt/total_sev*100:.1f}%"></div>'
                   for niv, cnt in [('critico', n_critico), ('aviso', n_aviso), ('ok', n_ok)] if cnt)
    partes_legend = []
    if n_critico: partes_legend.append(f'<span class="critico"><span class="pt"></span>{n_critico} crítica{"s" if n_critico != 1 else ""}</span>')
    if n_aviso: partes_legend.append(f'<span class="aviso"><span class="pt"></span>{n_aviso} aviso{"s" if n_aviso != 1 else ""}</span>')
    if n_ok: partes_legend.append(f'<span class="ok"><span class="pt"></span>{n_ok} mejora{"s" if n_ok != 1 else ""}</span>')
    st.markdown(f'<div class="stat-segment-card"><div class="stat-segment-label">'
                f'Estado de alertas — {total_sev} activa{"s" if total_sev != 1 else ""} en {ronda_snapshot}</div>'
                f'<div class="stat-segment-bar">{segs}</div>'
                f'<div class="stat-segment-legend">{"".join(partes_legend)}</div></div>', unsafe_allow_html=True)
    # Orden: primero lo que hay que resolver, después lo informativo, al final las mejoras.
    orden = {'critico': 0, 'aviso': 1, 'ok': 2}
    iconos = {'critico': '🔴', 'aviso': '🟠', 'ok': '🟢'}
    clases = {'critico': 'alerta-fila', 'aviso': 'alerta-fila aviso', 'ok': 'alerta-fila ok'}
    for nivel, titulo, detalle in sorted(alertas, key=lambda a: orden.get(a[0], 1)):
        icono = iconos.get(nivel, '🟠')
        clase = clases.get(nivel, 'alerta-fila aviso')
        st.markdown(f'<div class="{clase}">{icono} <b>{titulo}</b> <span class="detalle">— {detalle}</span></div>',
                    unsafe_allow_html=True)

# ---------------- Sidebar ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')
# Las rondas de Práctica (el ensayo previo al arranque de la competencia oficial) se sacaron de la
# navegación a pedido del equipo -- ya arrancó la competencia Oficial (Ronda 0 y Ronda 1 jugadas) y
# esos ensayos "no suman" al análisis de gestión. Quedan como dato histórico en el repo
# (data/raw/practicas/*.xls) por si hace falta revisarlos, pero la app ya no los ofrece para elegir.
filtro_tipo = 'Oficial'
rondas_timeline = [f'Ronda {i}' for i in range(1, 13)]
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_timeline, value=rondas_timeline[0], key='slider_rondas')
# Indicador de estado (estilo "● Conectado" de la referencia) -- acá confirma de un vistazo qué
# ronda está en foco, en vez de ser puramente decorativo.
st.sidebar.markdown(f'<div class="sidebar-status"><span class="dot"></span>{ronda_snapshot}</div>',
                     unsafe_allow_html=True)
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0, key='select_equipo')
st.sidebar.divider()
# BUG REPORTADO Y CONFIRMADO -- es una limitación de la plataforma, no de este código: Streamlit
# expone el tema elegido (Settings > claro/oscuro/uso del sistema) vía st.context.theme.type, pero
# esa lectura se toma UNA VEZ por corrida del script, y alternar el tema en el menú de Settings no
# siempre dispara una corrida nueva por sí solo. Resultado: si tocás el toggle de tema, los colores
# que dependen de es_modo_oscuro() (banda de KPIs, sidebar, gráficos) pueden quedar con el tema
# VIEJO hasta que algo más fuerce un rerun -- cambiar de Ronda, de Equipo o de Sección, como ya
# venía notando el equipo. Este botón es el atajo más chico y confiable para lo mismo, sin tener
# que tocar otro control de la app.
if st.sidebar.button('🔄 Actualizar tema', help='Usalo si cambiaste entre modo claro/oscuro en Settings y los colores de la app no se actualizaron solos.'):
    st.rerun()
SECCIONES = ['Resultados', 'Mercado', 'Operaciones', 'Finanzas', 'RRHH y Sostenibilidad']
seccion = st.sidebar.radio('Sección', SECCIONES, key='select_seccion_router')
df_all = get_data(filtro_tipo)
if df_all.empty or ronda_snapshot not in df_all['Ronda'].unique():
    # CASO ESPECIAL: CESIM todavía no publicó ningún RDOS de esta ronda (nada que mostrar en
    # Resultados/Mercado/Operaciones/RRHH), pero CADIZ ya cargó su propia proyección en el modelo de
    # gestión para esa ronda -- en vez de un callejón sin salida, se muestra directamente el Control
    # de Gestión (lo único que SÍ hay para ofrecer) en la sección Finanzas. Fuera de Finanzas, o si
    # no hay proyección tampoco, se mantiene el aviso original sin cambios.
    ronda_num_bypass = ronda_a_num(ronda_snapshot)
    df_proy_bypass = get_proyeccion() if ronda_num_bypass is not None else None
    hay_proyeccion_cadiz = (df_proy_bypass is not None and not df_proy_bypass[
        (df_proy_bypass['round'] == ronda_num_bypass) & (df_proy_bypass['team'] == MY_COMPANY)].empty)
    _CROSSWALK_POR_SECCION_BYPASS = {'Finanzas': CROSSWALK_FINANZAS, 'Mercado': CROSSWALK_MERCADO,
                                      'Operaciones': CROSSWALK_OPERACIONES, 'Resultados': CROSSWALK_RESULTADOS}
    if hay_proyeccion_cadiz and seccion in _CROSSWALK_POR_SECCION_BYPASS and empresa_analisis == MY_COMPANY:
        st.info(f"📁 CESIM todavía no publicó los RDOS de **{ronda_snapshot}** — el resto del tablero "
                "no tiene datos para mostrar todavía, pero CADIZ ya cargó su proyección para esta "
                "ronda en el modelo de gestión:")
        panel_comparativa_plan_real(df_all.copy(), ronda_snapshot, crosswalk=_CROSSWALK_POR_SECCION_BYPASS[seccion],
                               key_suffix=f'{seccion.lower()}_sin_real', mostrar_directo=True)
    else:
        st.info(f"📁 Faltan datos: No se encontraron archivos para **{ronda_snapshot}** en el entorno **{filtro_tipo}**.")
    st.stop()
df = df_all.copy()
ronda_ultima = ronda_snapshot
try:
    st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    # Antes fallaba en silencio (pass): si el archivo no está en el despliegue, la app se veía
    # sin ningún estilo custom (sidebar claro, sin banda oscura, sin barra segmentada) y no había
    # ninguna pista de por qué. Ahora al menos avisa.
    st.warning('No se encontró assets/style.css — el estilo visual (sidebar oscuro, banda de KPIs, '
               'barras segmentadas) no se aplicó en este despliegue. Verificá que la carpeta '
               '"assets" se haya subido junto con app.py.')
# =================================================================
# SECCIÓN 1 — RESULTADOS
# =================================================================
def seccion_resultado():
    tab_resumen, tab_cg = st.tabs(['Resumen', 'Comparativa Plan vs. Real'])
    with tab_resumen:
        _seccion_resultado_resumen()
    with tab_cg:
        if empresa_analisis == MY_COMPANY:
            panel_comparativa_plan_real(df_all.copy(), ronda_snapshot, crosswalk=CROSSWALK_RESULTADOS, key_suffix='resultados', mostrar_directo=True)
            st.divider()
            fila3_resultados_ingresos(df_all.copy(), ronda_snapshot, ronda_a_num(ronda_snapshot), get_proyeccion())
        else:
            st.caption('Cambiá "Equipo en foco" a CADIZ en la barra lateral para ver la Comparativa Plan vs. Real (es sobre la proyección propia de CADIZ).')
def _seccion_resultado_resumen():
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)]
    ratios_ronda_r1 = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)]

    # "Accionistas, Total" en la tabla de Creación de Valor = Beneficio de la ronda: es el valor
    # generado PARA EL ACCIONISTA en esa ronda puntual (no confundir con "Valor total creado", que
    # suma también lo pagado a Proveedores/Personal/Gobierno — no es plata del accionista).
    acc_ronda = df[(df['Modulo'] == 'Creación de valor') & (df['Seccion'] == 'Accionistas') &
                   (df['Metrica'] == 'Total') & (df['Ronda'] == ronda_snapshot)]
    cv_vals = {emp: valor_de(acc_ronda, 'Total', emp) for emp in COMPANIES}

    # Acumulado: Cesim ya reporta este campo pre-acumulado desde el inicio del juego — no hay que
    # sumarlo nosotros ronda a ronda. Es el criterio real de "creación de valor para el accionista".
    retorno_acum_vals = {emp: valor_de(ratios_ronda_r1, 'Retorno total acumulado del accionista (p.a.), %', emp) for emp in COMPANIES}

    # Retorno de ESTA ronda puntual: variación simple del precio de la acción vs. la ronda anterior.
    # (El campo "acumulado" es *per annum*, no es aditivo entre rondas — restarlo directo da un
    # número que no representa lo que pasó en la ronda. Esto sí es directamente comparable ronda a ronda.)
    precio_hist = df[(df['Estado'] == 'Ratios e indicadores financieros clave') &
                      (df['Metrica'] == 'Precio de la acción al final de la ronda, USD')].copy()
    precio_hist['Valor'] = num(precio_hist['Valor'])
    ordenes_disp = sorted(df['Ronda_Orden'].dropna().unique())
    orden_actual = df[df['Ronda'] == ronda_snapshot]['Ronda_Orden'].iloc[0] if not df[df['Ronda'] == ronda_snapshot].empty else None
    idx_orden = ordenes_disp.index(orden_actual) if orden_actual in ordenes_disp else None
    orden_anterior = ordenes_disp[idx_orden - 1] if idx_orden and idx_orden > 0 else None
    retorno_ronda_vals = {}
    if orden_anterior is not None:
        for emp in COMPANIES:
            p_act = valor_de(precio_hist[precio_hist['Ronda_Orden'] == orden_actual], 'Precio de la acción al final de la ronda, USD', emp)
            p_ant = valor_de(precio_hist[precio_hist['Ronda_Orden'] == orden_anterior], 'Precio de la acción al final de la ronda, USD', emp)
            retorno_ronda_vals[emp] = ((p_act - p_ant) / p_ant * 100) if (p_act is not None and p_ant not in (None, 0)) else None

    cap_vals = {emp: valor_de(val_ronda, 'Capitalización de mercado, miles USD', emp) for emp in COMPANIES}
    with st.container(border=True):
        st.markdown(f'**Alertas — {empresa_analisis}, {ronda_snapshot}**')
        panel_alertas()
    st.write('')
    st.subheader('KPIs de Valor')
    prom_ret_acum = np.nanmean([v for v in retorno_acum_vals.values() if v is not None]) if any(v is not None for v in retorno_acum_vals.values()) else None
    val_ret_acum = retorno_acum_vals.get(empresa_analisis)
    delta_ret_acum = ((val_ret_acum - prom_ret_acum) / abs(prom_ret_acum) * 100) if prom_ret_acum and val_ret_acum is not None else None

    ranking_acum = sorted([e for e in retorno_acum_vals if retorno_acum_vals.get(e) is not None], key=retorno_acum_vals.get, reverse=True)
    pos = ranking_acum.index(empresa_analisis) + 1 if empresa_analisis in ranking_acum else '-'
    ret_hist = df_all[(df_all['Estado'] == 'Ratios e indicadores financieros clave') &
                       (df_all['Metrica'] == 'Retorno total acumulado del accionista (p.a.), %')].copy()
    ret_hist['Valor'] = num(ret_hist['Valor'])
    puestos_hist = ret_hist.dropna(subset=['Valor']).copy()
    puestos_hist['Puesto'] = puestos_hist.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
    serie_puesto = puestos_hist[puestos_hist['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')['Puesto'].tolist()

    prom_cv = np.nanmean([v for v in cv_vals.values() if v is not None]) if any(v is not None for v in cv_vals.values()) else None
    val_cv = cv_vals.get(empresa_analisis)
    delta_cv = ((val_cv - prom_cv)/prom_cv*100) if prom_cv and val_cv is not None else None

    prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None
    val_cap = cap_vals.get(empresa_analisis)
    delta_cap = ((val_cap - prom_cap)/prom_cap*100) if prom_cap and val_cap else None

    # Los 3 números que más le importan a un accionista van en la banda oscura, separados del
    # resto (ver kpi_banda_oscura) -- "Retorno acum. del accionista", mismo término base que usa
    # el crosswalk de Resultados; "Capitalización de mercado" (antes "Market Cap", en inglés) usa
    # el mismo nombre que el propio campo de CESIM.
    kpi_banda_oscura([
        {'label': 'Retorno acum. del accionista', 'valor': f'{val_ret_acum:,.1f}%' if val_ret_acum is not None else '—',
         'delta': f'{delta_ret_acum:+.1f}% vs Prom' if delta_ret_acum is not None else None, 'favorable': (delta_ret_acum > 0) if delta_ret_acum is not None else None},
        {'label': 'Beneficio del accionista', 'valor': format_num(val_cv),
         'delta': f'{delta_cv:+.1f}% vs Prom' if delta_cv is not None else None, 'favorable': (delta_cv > 0) if delta_cv is not None else None},
        {'label': 'Capitalización de mercado (USD)', 'valor': format_num(val_cap),
         'delta': f'{delta_cap:+.1f}% vs Prom' if delta_cap else None, 'favorable': (delta_cap > 0) if delta_cap else None},
    ])

    # Posición en el ranking y Retorno de la ronda son más de contexto que de "número que decide
    # la creación de valor" -- se quedan como tarjetas claras con sparkline, más chicas.
    c2, c5 = st.columns(2)
    # invertir: en el ranking, "para arriba" en el gráfico tiene que ser mejorar de puesto
    kpi_con_tendencia(c2, 'Posición en el ranking', f'{pos}° de {len(COMPANIES)}', serie_puesto, invertir=True)

    prom_ret_ronda = np.nanmean([v for v in retorno_ronda_vals.values() if v is not None]) if any(v is not None for v in retorno_ronda_vals.values()) else None
    val_ret_ronda = retorno_ronda_vals.get(empresa_analisis)
    delta_ret_ronda = ((val_ret_ronda - prom_ret_ronda) / abs(prom_ret_ronda) * 100) if prom_ret_ronda and val_ret_ronda is not None else None
    # '—' y no 'Sin ronda previa': ese texto largo se cortaba con "..." en la tarjeta (el valor de
    # st.metric no wrappea como el label) -- el caption de abajo ya aclara por qué no hay dato acá.
    kpi_con_tendencia(c5, 'Retorno de la acción',
                       f'{val_ret_ronda:+,.1f}%' if val_ret_ronda is not None else '—',
                       serie_metrica('Ratios e indicadores financieros clave', 'Precio de la acción al final de la ronda, USD', empresa_analisis),
                       delta=f'{delta_ret_ronda:+.1f}% vs Prom' if delta_ret_ronda is not None else None)
    st.caption('El retorno acumulado es per-annum y no es aditivo entre rondas — para ver cómo fue *esta* ronda usá '
               '"Retorno de la acción", que es variación simple de precio. En la primera ronda del ecosistema no hay '
               'ronda previa con la cual compararla.')
    st.divider()
    vista_ranking = st.radio('Vista del ranking (columna derecha)', ['Acumulado (Retorno del Accionista, %)', f'Solo {ronda_snapshot} (USD)'], horizontal=True, key='vista_ranking_cv')
    col_a, col_b = st.columns(2)
    with col_a:
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def g(metrica): return valor_de(pl, metrica) or 0.0
        ingresos = g('Ingresos por ventas')
        if ingresos > 0:
            costos_prod = g('Costos de fabricación interna') + g('Costos de la característica') + g('Costos de fabricación contratada')
            costos_op = g('Costos de transporte y aranceles') + g('I+D') + g('Promoción') + g('Administración')
            depr, ints, imp, ben = g('Depreciación de Activos Fijos'), g('Gastos financieros netos'), g('Impuesto sobre el beneficio'), g('Beneficio de la ronda')
            fig = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Ingresos', '- Prod', '- Op/Admin', '- Depr', '- Int', '- Imp', '= Neto'],
                y=[ingresos, -costos_prod, -costos_op, -depr, -ints, -imp, ben],
                text=[format_num(v) for v in [ingresos, -costos_prod, -costos_op, -depr, -ints, -imp, ben]], textposition='outside',
                decreasing={'marker': {'color': MUTED_PALETTE[2]}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': COLOR_POSITIVE if ben > 0 else BRAND_ACCENT}}
            ))
            fig.update_layout(title=f'Puente de Beneficio Neto — {empresa_analisis}')
            mostrar(fig, ocultar_eje_valores='y')
    with col_b:
        es_acumulado = vista_ranking.startswith('Acumulado')
        datos_ranking = retorno_acum_vals if es_acumulado else cv_vals
        titulo_ranking = 'Ranking: Retorno Acumulado del Accionista, %' if es_acumulado else f'Ranking: Beneficio del Accionista — {ronda_snapshot}'
        ranking = pd.DataFrame(list(datos_ranking.items()), columns=['Empresa', 'Valor']).sort_values('Valor', ascending=True).dropna()
        ranking['Etiqueta'] = ranking['Valor'].apply(lambda v: f'{v:,.1f}%') if es_acumulado else ranking['Valor'].apply(format_num)
        fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa', color_discrete_map=COLOR_MAP, text='Etiqueta')
        fig.update_traces(textposition='outside', cliponaxis=False, showlegend=False)
        fig.update_layout(title=titulo_ranking, xaxis=dict(range=[0, ranking['Valor'].max() * 1.25]))
        mostrar(fig, ocultar_eje_valores='x')
    st.divider()
    st.subheader('Cuota de mercado')
    # Antes: 5 gráficos de barra casi idénticos (global, por valor, EE.UU., China, Europa) -- mismo
    # tipo de gráfico repetido 5 veces es exactamente la queja de "muchos gráficos de barra". Acá se
    # reemplazan por DOS formas distintas, cada una elegida por el trabajo que hace mejor:
    #   1) Dumbbell (dos puntos + línea): compara cuota por UNIDADES vs. cuota por VALOR por equipo en
    #      un solo gráfico -- la distancia entre los dos puntos de cada equipo ES el dato interesante
    #      (vender una porción de unidades distinta a la de ingresos implica un mix de precio propio).
    #   2) Heatmap: cuota por país (EE.UU./China/Europa) x equipo en una sola grilla -- reemplaza 3
    #      barras por 1 sola lectura de matriz, con la tabla de datos completa abajo por accesibilidad.
    sub_global = df[(df['Estado'] == 'Informe de mercado, global') &
                     (df['Seccion'] == 'Cuotas de mercado globales, %') & (df['Metrica'] == 'Total') &
                     (df['Ronda'] == ronda_snapshot)].copy()
    sub_global['Valor'] = num(sub_global['Valor'])
    cuota_unidades = sub_global.set_index('Empresa')['Valor'].to_dict()
    # Cuota por valor ($): CESIM no publica esta cifra directamente (los precios están en moneda local
    # por mercado -- USD/RMB/EUR -- y sumarlos sin convertir daría un número sin sentido). Se calcula
    # sobre "Ingresos por ventas, Global" (Cuenta de resultados), que CESIM SÍ publica ya convertido a
    # USD para los 7 equipos: cuota por valor = ingresos de la empresa / Σ ingresos de los 7 equipos.
    ingresos_glob = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') &
                        (df['Metrica'] == 'Ingresos por ventas') & (df['Ronda'] == ronda_snapshot)].copy()
    ingresos_glob['Valor'] = num(ingresos_glob['Valor'])
    total_ing = ingresos_glob['Valor'].sum()
    cuota_valor = (ingresos_glob.set_index('Empresa')['Valor'] / total_ing * 100).to_dict() if total_ing else {}
    filas_dumbbell = [{'Empresa': e, 'Unidades': cuota_unidades.get(e), 'Valor': cuota_valor.get(e)} for e in COMPANIES]
    dfd = pd.DataFrame(filas_dumbbell).dropna(subset=['Unidades', 'Valor'])
    if not dfd.empty:
        dfd = dfd.sort_values('Valor')
        fig_d = go.Figure()
        for _, r in dfd.iterrows():
            es_cadiz = r['Empresa'] == MY_COMPANY
            fig_d.add_trace(go.Scatter(x=[r['Unidades'], r['Valor']], y=[r['Empresa'], r['Empresa']], mode='lines',
                                        line=dict(color=BRAND_ACCENT if es_cadiz else 'rgba(140,151,166,0.45)',
                                                  width=2.5 if es_cadiz else 1.5),
                                        showlegend=False, hoverinfo='skip'))
        fig_d.add_trace(go.Scatter(x=dfd['Unidades'], y=dfd['Empresa'], mode='markers', name='Cuota por unidades, %',
                                    marker=dict(size=11, color=MUTED_PALETTE[0]),
                                    hovertemplate='%{y} — Unidades: %{x:.1f}%<extra></extra>'))
        fig_d.add_trace(go.Scatter(x=dfd['Valor'], y=dfd['Empresa'], mode='markers', name='Cuota por valor ($), %',
                                    marker=dict(size=11, color=BRAND_ACCENT, symbol='diamond'),
                                    hovertemplate='%{y} — Valor: %{x:.1f}%<extra></extra>'))
        fig_d.update_layout(title=f'Cuota de mercado global — unidades vs. valor, {ronda_snapshot}', xaxis_title='%',
                             legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
        mostrar(fig_d)
    else:
        st.info('Sin datos suficientes de cuota global (unidades y valor) para esta ronda.')
    st.caption('Cada línea conecta la cuota de UN equipo en dos monedas de medida: unidades vendidas y valor en '
               'USD. Cuando el punto de Valor queda a la derecha del de Unidades, ese equipo vende más caro que '
               'el promedio (o con mejor mix); si queda a la izquierda, más barato.')
    paises = ['EE.UU.', 'China', 'Europa']
    filas_hm = []
    for pais in paises:
        sub_pais = df[(df['Estado'] == f'Informe de mercado, {pais}') &
                      (df['Seccion'] == f'{pais} cuotas de mercado, %') & (df['Metrica'] == 'Total') &
                      (df['Ronda'] == ronda_snapshot)].copy()
        sub_pais['Valor'] = num(sub_pais['Valor'])
        for _, row in sub_pais.dropna(subset=['Valor']).iterrows():
            filas_hm.append({'Empresa': row['Empresa'], 'País': pais, 'Cuota': row['Valor']})
    if filas_hm:
        dfh = pd.DataFrame(filas_hm)
        piv = dfh.pivot(index='Empresa', columns='País', values='Cuota').reindex(columns=paises)
        piv = piv.reindex(piv.mean(axis=1).sort_values(ascending=False).index)  # ranking, no alfabético
        fig_hm = go.Figure(go.Heatmap(
            z=piv.values, x=list(piv.columns), y=list(piv.index),
            colorscale=[[0, 'rgba(179,38,30,0.06)'], [1, BRAND_ACCENT]],  # secuencial, un solo matiz (marca)
            text=[[f'{v:.1f}%' if pd.notna(v) else '' for v in fila] for fila in piv.values],
            texttemplate='%{text}', textfont=dict(size=12),
            hovertemplate='%{y} — %{x}: %{z:.1f}%<extra></extra>', showscale=False,
            xgap=3, ygap=3))  # gap entre celdas -- separador de superficie, no una grilla de líneas
        fig_hm.update_layout(title=f'Cuota de mercado por país, % — {ronda_snapshot}')
        mostrar(fig_hm)
        with st.expander('Ver como tabla'):
            st.dataframe(piv.style.format('{:.1f}%', na_rep='—'), use_container_width=True)
    else:
        st.info('Sin datos de cuota de mercado por país para esta ronda.')
    st.divider()
    cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')].copy()
    # chart_evolucion() ya antepone "Evolución — " al titulo -- pasarle "Evolución de la ..." de nuevo
    # duplicaba la palabra ("Evolución — Evolución de..."). Solo el sustantivo acá.
    chart_evolucion(cap_sub, 'Capitalización de Mercado (USD)')
# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    tab_pos, tab_pan, tab_evo, tab_cg = st.tabs(['Posicionamiento', 'Panorama Competitivo', 'Evolución', 'Comparativa Plan vs. Real'])
    tecnologias = ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno']

    with tab_cg:
        if empresa_analisis == MY_COMPANY:
            panel_comparativa_plan_real(df_all.copy(), ronda_snapshot, crosswalk=CROSSWALK_MERCADO, key_suffix='mercado', mostrar_directo=True)
            st.divider()
            fila3_mercado_cuota_objetivo(df_all.copy(), ronda_snapshot, ronda_a_num(ronda_snapshot), get_proyeccion())
        else:
            st.caption('Cambiá "Equipo en foco" a CADIZ en la barra lateral para ver la Comparativa Plan vs. Real (es sobre la proyección propia de CADIZ).')

    with tab_pos:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'], key='sel_mercado_pais')
        tech_sel = c2.selectbox('Tecnología', tecnologias, key='sel_mercado_tech')
        estado_pais = f'Informe de mercado, {pais_sel}'
        sub = df[(df['Estado'] == estado_pais) & (df['Seccion'] == tech_sel) & (df['Ronda'] == ronda_snapshot)]

        ventas_data = [{'Empresa': emp, 'Volumen': valor_fuzzy(sub[sub['Empresa'] == emp], 'Ventas')} for emp in COMPANIES]
        vol_df = pd.DataFrame(ventas_data).dropna()
        def scatter_posicionamiento(keyword_metrica, titulo_x):
            eje_x_df = sub[sub['Metrica'].str.contains(rf'^{keyword_metrica}', case=False, na=False)][['Empresa', 'Valor']].rename(columns={'Valor': titulo_x})
            if vol_df.empty or eje_x_df.empty: return None
            pos = eje_x_df.merge(vol_df, on='Empresa').dropna()
            pos[titulo_x] = num(pos[titulo_x])
            if pos.empty: return None
            fig = px.scatter(pos, x=titulo_x, y='Volumen', color='Empresa', color_discrete_map=COLOR_MAP, size='Volumen', text='Empresa', title=f'{titulo_x} vs Volumen')
            fig.update_traces(textposition='top center', showlegend=False)
            linea_media(fig, pos['Volumen'].mean(), eje='y', etiqueta='Vol Prom')
            linea_media(fig, pos[titulo_x].mean(), eje='x', etiqueta=f'{titulo_x} Prom')
            mostrar(fig)
            return True
        col_a, col_b = st.columns(2)
        with col_a: scatter_posicionamiento('Precio', 'Precio Promedio')
        with col_b: scatter_posicionamiento('Cantidad de características', 'Características')
        st.divider()
        st.subheader('Eficiencia Comercial')
        mkt_sub = df[(df['Estado'].str.contains(f'Cuenta de resultados.*{pais_sel}', case=False, na=False)) & (df['Seccion'] == tech_sel) & (df['Metrica'].str.contains('Promoción', case=False, na=False)) & (df['Ronda'] == ronda_snapshot)]
        if mkt_sub.empty:
            mkt_sub = df[(df['Estado'].str.contains(f'Cuenta de resultados.*{pais_sel}', case=False, na=False)) & (df['Metrica'].str.contains('Promoción', case=False, na=False)) & (df['Ronda'] == ronda_snapshot)]
        mkt_df = mkt_sub[['Empresa', 'Valor']].rename(columns={'Valor': 'Marketing (USD)'}).dropna()
        mkt_df['Marketing (USD)'] = num(mkt_df['Marketing (USD)'])
        if not vol_df.empty and not mkt_df.empty:
            efi = vol_df.merge(mkt_df, on='Empresa').dropna()
            if not efi.empty:
                fig_efi = px.scatter(efi, x='Marketing (USD)', y='Volumen', color='Empresa', color_discrete_map=COLOR_MAP, size='Volumen', text='Empresa', title='Marketing vs. Retorno en Ventas')
                fig_efi.update_traces(textposition='top center', showlegend=False)
                linea_media(fig_efi, efi['Volumen'].mean(), eje='y')
                linea_media(fig_efi, efi['Marketing (USD)'].mean(), eje='x')
                mostrar(fig_efi)
            else: st.info("Sin datos consolidados de Marketing.")
        else: st.info("Sin datos de Marketing para analizar eficiencia.")

        st.divider()
        st.subheader('Share of Voice (SOV) vs. Share of Market (SOM)')
        st.caption(f'{tech_sel}, {pais_sel}, {ronda_snapshot}. SOV = Promoción del equipo / Promoción total de la '
                   'tecnología (los 7 equipos). SOM = cuota de mercado real que publica CESIM para esa tecnología '
                   '(Ventas del equipo / Ventas totales DE ESA TECNOLOGÍA, no del mercado completo) — mismo grano '
                   'que el SOV, para que la comparación sea de manzanas con manzanas.')
        promo_sov = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {pais_sel}') & (df['Seccion'] == tech_sel) &
                       (df['Metrica'] == 'Promoción') & (df['Ronda'] == ronda_snapshot)].copy()
        promo_sov['Valor'] = num(promo_sov['Valor']).abs()
        som_sov = df[(df['Estado'] == f'Informe de mercado, {pais_sel}') & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') &
                     (df['Metrica'] == tech_sel) & (df['Ronda'] == ronda_snapshot)].copy()
        som_sov['Valor'] = num(som_sov['Valor'])
        promo_total_sov = promo_sov['Valor'].sum()
        if promo_total_sov > 0 and not som_sov.empty:
            sov_df = promo_sov[['Empresa', 'Valor']].rename(columns={'Valor': 'Promo'})
            sov_df['SOV'] = sov_df['Promo'] / promo_total_sov * 100
            som_df = som_sov[['Empresa', 'Valor']].rename(columns={'Valor': 'SOM'})
            comp_sov = sov_df.merge(som_df, on='Empresa', how='outer')
            comp_sov_long = comp_sov.melt(id_vars='Empresa', value_vars=['SOV', 'SOM'], var_name='Indicador', value_name='Pct').dropna(subset=['Pct'])
            fig_sov = px.bar(comp_sov_long, x='Empresa', y='Pct', color='Indicador', barmode='group',
                              color_discrete_map={'SOV': MUTED_PALETTE[0], 'SOM': BRAND_ACCENT},
                              text=comp_sov_long['Pct'].apply(lambda v: f'{v:,.1f}%'),
                              title=f'SOV vs. SOM — {tech_sel}, {pais_sel}, {ronda_snapshot}')
            fig_sov.update_traces(textposition='outside', cliponaxis=False)
            fig_sov.update_layout(yaxis_title='%')
            mostrar(fig_sov)
        else:
            st.info('Sin datos suficientes de Promoción o Cuota de mercado para esta combinación.')

    with tab_pan:
        c1p, c2p = st.columns(2)
        pais_pan = c1p.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'], key='sel_pan_pais')
        tech_pan = c2p.selectbox('Tecnología', tecnologias, key='sel_pan_tech')
        estado_pan = f'Informe de mercado, {pais_pan}'

        st.markdown('**Enfoque de estrategia de marketing — los 7 equipos**')
        est = df[(df['Estado'] == estado_pan) & (df['Seccion'] == tech_pan) &
                 (df['Metrica'] == 'Enfoque de la estrategia de marketing') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
        if not est.empty:
            estrategias = ['Precio bajo', 'Equilibrado', 'Marca', 'Características', 'Precio alto']
            # Mapa de color FIJO por estrategia (antes usaba el color automático de Plotly, que
            # reasigna colores según el orden de aparición en cada gráfico — por eso "Marca"
            # salía de un color acá y de otro allá).
            estrategia_colores = dict(zip(estrategias, [BRAND_ACCENT, MUTED_PALETTE[0], MUTED_PALETTE[1], MUTED_PALETTE[2], MUTED_PALETTE[3]]))
            est = est.copy().sort_values('Empresa')
            # Antes era un gráfico de barras todas de la misma altura: el eje Y no codificaba nada
            # y el texto iba rotado adentro de la barra. Peor todavía, px.bar parte el dataframe en
            # un trace por estrategia y el update_traces le pasaba la columna ENTERA a cada trace,
            # así que el texto de la barra no correspondía a su color. Con chips no hay ambigüedad
            # posible: el color y el texto salen de la misma fila.
            with st.container(border=True):
                st.markdown(f'**Estrategia elegida — {tech_pan}, {pais_pan}, {ronda_snapshot}**')
                chips = []
                for _, fila in est.iterrows():
                    color = estrategia_colores.get(fila['Valor'], MUTED_PALETTE[0])
                    clase = 'chip-estrategia destacado' if fila['Empresa'] == MY_COMPANY else 'chip-estrategia'
                    chips.append(f'<span class="{clase}" style="background-color:{color}">'
                                 f'{fila["Empresa"]} · {fila["Valor"]}</span>')
                st.markdown(' '.join(chips), unsafe_allow_html=True)
        else:
            st.info('Sin datos de estrategia para esta combinación.')

        st.divider()
        st.markdown('**Mix tecnológico**')
        col_mix1, col_mix2 = st.columns(2)
        mix_rows = []
        for tech in tecnologias:
            v = df[(df['Estado'] == estado_pan) & (df['Seccion'] == tech) & (df['Metrica'] == 'Ventas, miles unidades') & (df['Ronda'] == ronda_snapshot)]['Valor']
            mix_rows.append({'Tecnología': tech, 'Ventas': num(v).sum()})
        mix_df = pd.DataFrame(mix_rows)
        mix_df = mix_df[mix_df['Ventas'] > 0]
        with col_mix1:
            if not mix_df.empty:
                fig_mix = px.pie(mix_df, names='Tecnología', values='Ventas', hole=0.5,
                                  color_discrete_sequence=[BRAND_ACCENT] + MUTED_PALETTE,
                                  title=f'Toda la industria — {pais_pan}, {ronda_snapshot}')
                mostrar(fig_mix)
            else:
                st.info('Sin ventas registradas en esta combinación.')
        with col_mix2:
            mix_emp_rows = []
            for tech in tecnologias:
                sub_tech = df[(df['Estado'] == estado_pan) & (df['Seccion'] == tech) & (df['Metrica'] == 'Ventas, miles unidades') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
                sub_tech['Valor'] = num(sub_tech['Valor'])
                for _, r in sub_tech.iterrows():
                    mix_emp_rows.append({'Empresa': r['Empresa'], 'Tecnología': tech, 'Ventas': r['Valor']})
            mix_emp_df = pd.DataFrame(mix_emp_rows).dropna(subset=['Ventas'])
            mix_emp_df = mix_emp_df[mix_emp_df['Ventas'] > 0]
            if not mix_emp_df.empty:
                totales = mix_emp_df.groupby('Empresa')['Ventas'].transform('sum')
                mix_emp_df['Pct'] = mix_emp_df['Ventas'] / totales * 100
                fig_mix_emp = px.bar(mix_emp_df, x='Empresa', y='Pct', color='Tecnología', barmode='stack',
                                      color_discrete_sequence=[BRAND_ACCENT] + MUTED_PALETTE,
                                      title=f'Por equipo — {pais_pan}, {ronda_snapshot}')
                fig_mix_emp.update_layout(yaxis_title='% de ventas')
                mostrar(fig_mix_emp)
            else:
                st.info('Sin ventas por equipo en esta combinación.')

    with tab_evo:
        pais_evo = st.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'], key='sel_evo_pais')
        estado_evo = f'Informe de mercado, {pais_evo}'

        st.markdown('**Demanda total vs. ventas totales de la industria, por tecnología**')
        st.caption('Toda la torta del mercado (7 equipos sumados): la brecha entre demanda y ventas es oportunidad que nadie capturó. '
                   'Un panel por tecnología para ver dónde está esa brecha, en vez de un solo total que mezcla las cuatro — '
                   'se omite la tecnología que todavía no tiene ningún dato en este mercado.')
        paneles_tech = []
        for tech in tecnologias:
            dem = df[(df['Estado'] == estado_evo) & (df['Seccion'] == tech) & (df['Metrica'] == 'Demanda, miles unidades')].copy()
            ven = df[(df['Estado'] == estado_evo) & (df['Seccion'] == tech) & (df['Metrica'] == 'Ventas, miles unidades')].copy()
            dem['Valor'] = num(dem['Valor']); ven['Valor'] = num(ven['Valor'])
            dem_piv = dem.groupby(['Ronda', 'Ronda_Orden'], as_index=False)['Valor'].sum().assign(Tipo='Demanda')
            ven_piv = ven.groupby(['Ronda', 'Ronda_Orden'], as_index=False)['Valor'].sum().assign(Tipo='Ventas')
            piv = pd.concat([dem_piv, ven_piv], ignore_index=True)
            if piv.empty or piv['Valor'].fillna(0).abs().sum() == 0:
                continue  # tecnología sin ningún dato (>0) en este mercado -- no se muestra el panel
            paneles_tech.append((tech, piv.sort_values('Ronda_Orden')))
        if paneles_tech:
            cols_dv = st.columns(2)
            for i, (tech, piv) in enumerate(paneles_tech):
                fig_dv = go.Figure()
                for tipo, color in [('Demanda', MUTED_PALETTE[0]), ('Ventas', BRAND_ACCENT)]:
                    d_t = piv[piv['Tipo'] == tipo]
                    fig_dv.add_trace(go.Bar(x=d_t['Ronda'], y=d_t['Valor'], name=tipo, marker_color=color))
                fig_dv.update_layout(barmode='group', title=f'{tech} — {pais_evo}')
                with cols_dv[i % 2]:
                    mostrar(fig_dv)
        else:
            st.info('Sin datos suficientes.')

        st.divider()
        st.markdown(f'**Evolución de la cuota de mercado — {pais_evo}**')
        st.caption('Los 7 equipos, CADIZ resaltado.')
        share_hist = df[(df['Estado'] == estado_evo) & (df['Seccion'] == f'{pais_evo} cuotas de mercado, %') &
                         (df['Metrica'].str.strip() == 'Total')].copy()
        chart_evolucion(share_hist, f'Cuota de mercado, % — {pais_evo}')
        # NOTA: hasta acá había un gráfico "Trayectoria de {empresa}: precio y características en el
        # tiempo" (Precio, USD vs. Cantidad de características, cada uno en su propio eje Y superpuesto
        # en el mismo plano -- yaxis / yaxis2 con overlaying='y'). Era el único gráfico de doble eje Y
        # de verdad que quedaba en la app (el resto ya se había migrado a paneles apilados, ver
        # chart_dos_metricas_apiladas) -- señalado como pendiente en la Adenda 18 y sacado a pedido
        # explícito del equipo.
# =================================================================
# SECCIÓN 3 — OPERACIONES
# =================================================================
def seccion_operaciones():
    bloque1, bloque2, tab_cg = st.tabs(['Capacidad y Costos', 'Inventario y Logística', 'Comparativa Plan vs. Real'])
    with tab_cg:
        if empresa_analisis == MY_COMPANY:
            panel_comparativa_plan_real(df_all.copy(), ronda_snapshot, crosswalk=CROSSWALK_OPERACIONES, key_suffix='operaciones', mostrar_directo=True)
            st.divider()
            fila3_operaciones_gap_fabricacion(df_all.copy(), ronda_snapshot, ronda_a_num(ronda_snapshot), get_proyeccion())
        else:
            st.caption('Cambiá "Equipo en foco" a CADIZ en la barra lateral para ver la Comparativa Plan vs. Real (es sobre la proyección propia de CADIZ).')
    with bloque1:
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        # Cesim reporta la capacidad usada POR TECNOLOGÍA dentro de cada país (ej. Combustión 45% +
        # Híbrido 40% en EE.UU. = 85% de la planta) — hay que sumarlas para tener el % real de la planta,
        # si no, cada tecnología aparecía como una gauge separada.
        cap = cap.dropna(subset=['Valor']).groupby('Subgrupo', as_index=False)['Valor'].sum()
        if not cap.empty:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                titulo = row['Subgrupo'] if pd.notna(row['Subgrupo']) else 'Capacidad'
                uso = float(row['Valor'])
                libre = max(100 - uso, 0)
                # Barra segmentada, mismo lenguaje visual que "Estado de Alertas" (panel_alertas) --
                # pero acá SÍ hay un universo fijo real (100% = capacidad instalada de la planta),
                # a diferencia de las alertas, donde no existe un total fijo de "reglas evaluadas".
                # Sin semáforo: no hay un rango "sano" publicado por Cesim, así que poner umbrales
                # propios sería inventar un criterio que el reporte no da.
                with col:
                    st.markdown(
                        f'<div class="stat-segment-card">'
                        f'<div class="stat-segment-label">Capacidad empleada — {titulo}</div>'
                        f'<div class="stat-segment-value">{uso:,.1f}%</div>'
                        f'<div class="stat-segment-bar">'
                        f'<div class="seg uso" style="width:{min(uso, 100):.1f}%"></div>'
                        f'<div class="seg libre" style="width:{libre:.1f}%"></div></div>'
                        f'<div class="stat-segment-legend">'
                        f'<span class="uso"><span class="pt"></span>Usado</span>'
                        f'<span class="libre"><span class="pt"></span>Libre</span></div></div>',
                        unsafe_allow_html=True)
        st.divider()
        st.markdown('**Producción: propia vs. contratada, y fábricas**')
        prod = df[(df['Estado'] == 'Detalles de fabricación') &
                  (df['Seccion'].isin(['Producción interna, miles unidades', 'Producción contratada, miles unidades'])) &
                  (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) &
                  (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        prod['Valor'] = num(prod['Valor'])
        prod = prod.dropna(subset=['Valor']).groupby(['Subgrupo', 'Seccion'], as_index=False)['Valor'].sum()
        prod['Tipo'] = prod['Seccion'].map({'Producción interna, miles unidades': 'Interna', 'Producción contratada, miles unidades': 'Contratada'})

        col_pp, col_ff = st.columns(2)
        with col_pp:
            if not prod.empty:
                fig_prod = px.bar(prod, x='Subgrupo', y='Valor', color='Tipo', barmode='group',
                                   color_discrete_map={'Interna': BRAND_ACCENT, 'Contratada': MUTED_PALETTE[0]},
                                   text=prod['Valor'].apply(lambda v: f'{v:,.0f}'),
                                   title=f'Producción propia vs. contratada — {ronda_snapshot}')
                fig_prod.update_traces(textposition='outside', cliponaxis=False)
                mostrar(fig_prod, ocultar_eje_valores='y')
            else:
                st.info('Sin datos de producción para esta combinación.')
        with col_ff:
            fab_all = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Número de fábricas') &
                         (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'] == 'Ronda actual')].copy()
            fab_all['Valor'] = num(fab_all['Valor'])
            fab_piv = fab_all.groupby(['Empresa', 'Metrica'], as_index=False)['Valor'].sum()
            if not fab_piv.empty:
                fig_fab = px.bar(fab_piv, x='Empresa', y='Valor', color='Metrica', barmode='stack',
                                  color_discrete_map={'EE.UU.': BRAND_ACCENT, 'China': MUTED_PALETTE[0]},
                                  text=fab_piv['Valor'].apply(lambda v: f'{v:,.0f}'),
                                  title=f'Fábricas por equipo — {ronda_snapshot}')
                fig_fab.update_traces(textposition='inside')
                mostrar(fig_fab, ocultar_eje_valores='y')
            else:
                st.info('Sin datos de fábricas para esta ronda.')

        # La alerta de expansión de capacidad se movió al panel de alertas de Resultados,
        # para no tener avisos importantes desparramados por el tablero.

        st.divider()
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def g(metrica): return valor_de(pl, metrica) or 0.0
        ingresos = g('Ingresos por ventas')
        if ingresos > 0:
            etapas = [('Ingresos', ingresos), ('- Fab. Interna', ingresos - g('Costos de fabricación interna'))]
            etapas.append(('- Caract.', etapas[-1][1] - g('Costos de la característica')))
            etapas.append(('- Fab. Contratada', etapas[-1][1] - g('Costos de fabricación contratada')))
            etapas.append(('- Logística', etapas[-1][1] - g('Costos de transporte y aranceles')))
            etapas.append(('- Op/Admin', etapas[-1][1] - g('I+D') - g('Promoción') - g('Administración')))
            ebitda = etapas[-1][1]
            etapas.append(('= EBITDA', ebitda))
            colores = [COLOR_POSITIVE] + [MUTED_PALETTE[2]]*(len(etapas)-2) + [COLOR_POSITIVE if ebitda > 0 else BRAND_ACCENT]
            # textinfo='value+...' usa el formateo automático de Plotly, que muestra decimales sin
            # redondear ("45.91583M") -- inconsistente con format_num() (1 decimal) que se usa en el
            # resto del tablero, incluida la waterfall de "Puente de Beneficio Neto" con estos mismos
            # datos unas filas más abajo. Se arma el texto a mano con format_num().
            fig = go.Figure(go.Funnel(y=[e[0] for e in etapas], x=[e[1] for e in etapas],
                                       text=[format_num(e[1]) for e in etapas], textinfo='text+percent initial',
                                       marker={'color': colores}))
            fig.update_layout(title='Estructura Macro de Costos (Funnel)')
            mostrar(fig, ocultar_eje_valores='x')

        st.divider()
        st.markdown('**Costos de proveedores — composición**')
        st.caption('No incluye Fabricación contratada — eso ya se ve arriba, en Producción propia vs. contratada.')
        prov = df[(df['Modulo'] == 'Creación de valor') & (df['Seccion'] == 'Proveedores') &
                  (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) &
                  (~df['Metrica'].isin(['Total', 'Valor total creado', 'Costos de fabricación contratada']))].copy()
        prov['Valor'] = num(prov['Valor'])
        prov = prov.dropna(subset=['Valor'])
        if not prov.empty:
            fig_prov = px.bar(prov, x='Metrica', y='Valor', color='Metrica', color_discrete_sequence=MUTED_PALETTE,
                               text=prov['Valor'].apply(format_num), title=f'Composición de costos de proveedores — {ronda_snapshot}')
            fig_prov.update_traces(textposition='outside', cliponaxis=False, showlegend=False)
            mostrar(fig_prov, ocultar_eje_valores='y')
        else:
            st.info('Sin datos de proveedores para esta combinación.')
        st.divider()
        c3, c4 = st.columns(2)
        pais_ue = c3.selectbox('País — Margen Unitario', ['EE.UU.', 'China', 'Europa'], key='sel_op_pais')
        tech_ue = c4.selectbox('Tecnología — Margen Unitario', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'], key='sel_op_tech')
        margen = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, '^Ventas', empresa=empresa_analisis)
        def gm(metrica): return valor_de(margen, metrica) or 0.0
        if unidades and unidades > 0:
            p_venta = gm('Ingresos por ventas') / unidades
            c_prod = -gm('Fabricación propia y por contrato') / unidades
            c_flete = -gm('Transporte y aranceles') / unidades
            c_caract = -gm('Costos de la característica') / unidades
            m_bruto = gm('Beneficio bruto') / unidades
            fig_ue = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'total'],
                x=['Precio', '- Prod.', '- Logística', '- Caract.', '= Margen Unitario'],
                y=[p_venta, c_prod, c_flete, c_caract, m_bruto],
                text=[format_num(v) for v in [p_venta, c_prod, c_flete, c_caract, m_bruto]], textposition='outside',
                decreasing={'marker': {'color': MUTED_PALETTE[2]}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': COLOR_POSITIVE if m_bruto > 0 else BRAND_ACCENT}}
            ))
            fig_ue.update_layout(title=f'Margen Unitario — {tech_ue}, {pais_ue}')
            mostrar(fig_ue, ocultar_eje_valores='y')
            costo_total_unit = -(c_prod + c_flete + c_caract)
            markup_pct = (m_bruto / costo_total_unit * 100) if costo_total_unit else None
            col_cm, col_mk = st.columns(2)
            col_cm.metric('Contribución Marginal Unitaria', f'USD {m_bruto:,.0f}')
            col_mk.metric('Mark-up aplicado', f'{markup_pct:,.1f}%' if markup_pct is not None else '—')
            st.caption('Mark-up = Contribución Marginal Unitaria / Costo unitario total (fabricación + logística + características).')

        st.divider()
        st.markdown(f'**Punto de equilibrio — {empresa_analisis}, {ronda_snapshot}**')
        cm_total_miles = 0.0
        vol_total_miles = 0.0
        for mercado_be in ['EE.UU.', 'China', 'Europa']:
            margen_be = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {mercado_be}') &
                           (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) &
                           (df['Metrica'] == 'Margen de contribución')].copy()
            cm_total_miles += num(margen_be['Valor']).sum()
            ventas_be = df[(df['Estado'] == f'Informe de mercado, {mercado_be}') & (df['Empresa'] == empresa_analisis) &
                          (df['Ronda'] == ronda_snapshot) & (df['Metrica'] == 'Ventas, miles unidades')].copy()
            vol_total_miles += num(ventas_be['Valor']).sum()
        pl_be = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def gbe(metrica): return valor_de(pl_be, metrica) or 0.0
        costos_fijos_miles = gbe('Depreciación de Activos Fijos') + gbe('I+D') + gbe('Administración')
        if vol_total_miles > 0 and cm_total_miles:
            cm_unitaria = cm_total_miles / vol_total_miles  # miles USD / miles u. = USD/u. -- la escala se cancela
            volumen_real = vol_total_miles * 1000.0
            volumen_equilibrio = (costos_fijos_miles * 1000.0) / cm_unitaria if cm_unitaria else None
            if volumen_equilibrio is not None and volumen_equilibrio > 0:
                chart_bullet(f'Punto de Equilibrio — {empresa_analisis}, {ronda_snapshot}', volumen_equilibrio, volumen_real,
                             'unidades', nombre_fondo='Volumen de Equilibrio', nombre_frente='Volumen Real Vendido',
                             color_excedente=COLOR_POSITIVE)  # vender por encima del equilibrio es favorable
                st.caption('Costos Fijos = Depreciación + I+D + Administración (real, Global). Contribución Marginal '
                           'Unitaria Ponderada = Margen de contribución total / unidades totales vendidas, sumado en '
                           'los 3 mercados donde el equipo vende.')
            else:
                st.info('No se pudo calcular el punto de equilibrio para esta combinación.')
        else:
            st.info('Sin datos suficientes de ventas/margen para calcular el punto de equilibrio.')
    with bloque2:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('País Inventario', ['EE.UU.', 'China', 'Europa'], key='sel_inv_pais')
        tech_sel = c2.selectbox('Tecnología — Inventario', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'], key='sel_inv_tech')
        log = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) & (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Subgrupo'] == pais_sel) & (df['Ronda'] == ronda_snapshot)].copy()
        log['Valor'] = num(log['Valor'])
        d = log.set_index('Metrica')['Valor']
        if not d.empty:
            inv_ini = d.get('Inventario inicial', 0) or 0
            prod = (d.get('Producción interna', 0) or 0) + (d.get('Producción contratada', 0) or 0)
            imp = sum(v for k, v in d.items() if k.startswith('Importado desde') and pd.notna(v))
            ventas = abs(d.get(f'Ventas en {pais_sel}', 0) or 0)
            exp = sum(abs(v) for k, v in d.items() if k.startswith('Exportado a') and pd.notna(v))
            inv_fin = d.get('Inventario final', 0) or 0
            fig_inv = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Inv Inicial', '+ Prod', '+ Import', '- Ventas', '- Export', '= Inv Final'],
                y=[inv_ini, prod, imp, -ventas, -exp, inv_fin],
                text=[format_num(v) for v in [inv_ini, prod, imp, -ventas, -exp, inv_fin]], textposition='outside',
                decreasing={'marker': {'color': MUTED_PALETTE[2]}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': MUTED_PALETTE[0]}}
            ))
            fig_inv.update_layout(title='Puente de Inventario Físico')
            mostrar(fig_inv, ocultar_eje_valores='y')

        st.divider()
        st.markdown('**Gap de pronóstico: demanda insatisfecha vs. inventario que sobró**')
        st.caption('Evolución de las dos formas de errar la estimación de demanda: faltante (no llegaste a vender lo que te pedían) y sobrante (produjiste de más y quedó en depósito).')
        log_hist = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) &
                      (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Subgrupo'] == pais_sel) &
                      (df['Metrica'].isin(['Demanda insatisfecha', 'Inventario final']))].copy()
        log_hist['Valor'] = num(log_hist['Valor'])
        log_hist = log_hist.dropna(subset=['Valor']).sort_values('Ronda_Orden')
        if not log_hist.empty:
            fig_gap = go.Figure()
            for metrica, color, nombre in [('Demanda insatisfecha', BRAND_ACCENT, 'Faltante (demanda insatisfecha)'),
                                            ('Inventario final', MUTED_PALETTE[0], 'Sobrante (inventario final)')]:
                d_m = log_hist[log_hist['Metrica'] == metrica]
                fig_gap.add_trace(go.Bar(x=d_m['Ronda'], y=d_m['Valor'], name=nombre, marker_color=color))
            fig_gap.update_layout(barmode='group', title=f'Faltante vs. sobrante — {empresa_analisis}, {tech_sel}, {pais_sel}',
                                   legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
            mostrar(fig_gap)
        else:
            st.info('Sin datos suficientes para esta combinación.')

        st.divider()
        log_tech = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) & (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Ronda'] == ronda_snapshot)]
        def val_log(planta, metrica):
            r = log_tech[(log_tech['Subgrupo'] == planta) & (log_tech['Metrica'] == metrica)]['Valor']
            return abs(pd.to_numeric(r.iloc[0], errors='coerce')) if len(r) else 0.0
        destinos = ['EE.UU.', 'China', 'Europa']
        matriz = pd.DataFrame(0.0, index=['EE.UU.', 'China', 'Subcontratado'], columns=destinos)
        for planta in ['EE.UU.', 'China']:
            interna, contratada = val_log(planta, 'Producción interna'), val_log(planta, 'Producción contratada')
            tot = interna + contratada
            flows = {dst: val_log(planta, f'Ventas en {planta}' if dst == planta else f'Exportado a {dst}') for dst in destinos}
            if tot > 0:
                for dst in destinos:
                    matriz.loc[planta, dst] += flows[dst] * (interna/tot)
                    matriz.loc['Subcontratado', dst] += flows[dst] * (contratada/tot)
        if matriz.sum().sum() > 0:
            fig3 = px.imshow(matriz.values, x=destinos, y=matriz.index, text_auto='.0f', aspect='auto', color_continuous_scale=[[0, BRAND_LIGHT], [1, BRAND_ACCENT]])
            fig3.update_coloraxes(showscale=False)
            fig3.update_xaxes(title_text='Destino (Mercado)')
            fig3.update_yaxes(title_text='Origen (Planta)')
            fig3.update_traces(xgap=3, ygap=3) 
            fig3.update_layout(title='Matriz Logística (Heatmap Origen -> Destino)')
            mostrar(fig3)
        else:
            st.info(f"Sin flujos logísticos de {tech_sel} para mostrar en esta ronda.")
# =================================================================
# SECCIÓN 4 — FINANZAS (Corto y Largo Plazo)
# =================================================================
def seccion_finanzas():
    pl_ronda = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]
    ratios_ronda = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)]
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)]
    def wacc(emp):
        de = valor_de(val_ronda, 'Deuda a patrimonio', emp)
        re_ = valor_de(val_ronda, 'Rendimiento esperado del patrimonio, %', emp)
        rd = valor_de(val_ronda, 'Costo de la deuda después de impuestos, %', emp)
        if None in (de, re_, rd): return None
        return (1/(1+de))*re_ + (de/(1+de))*rd
    # Estos 7 KPIs describen la foto financiera de la ronda, no son de corto ni de largo plazo:
    # quedan fijos arriba y las pestañas subdividen solamente el análisis.
    bal_ronda = df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]
    ebitda_vals = {e: valor_de(pl_ronda, 'Beneficio operativo antes de depreciación (EBITDA)', e) for e in COMPANIES}
    margen_vals = {e: valor_de(ratios_ronda, 'Margen bruto', e) for e in COMPANIES}
    ros_vals = {e: valor_de(ratios_ronda, 'Rentabilidad de las ventas (ROS)', e) for e in COMPANIES}
    caja_vals = {e: valor_de(bal_ronda, 'Efectivo y equivalentes de efectivo', e) for e in COMPANIES}
    deuda_cp_vals = {e: valor_de(bal_ronda, 'Deudas a corto plazo (no planificadas)', e) for e in COMPANIES}
    deuda_lp_vals = {e: valor_de(bal_ronda, 'Deudas a largo plazo', e) for e in COMPANIES}
    val_deuda_cp = deuda_cp_vals.get(empresa_analisis)
    calif_val = valor_texto(ratios_ronda, 'Calificación crediticia', empresa_analisis)

    def delta_raw(vals, empresa=empresa_analisis):
        # Mismo cálculo que el resto de la app: % de distancia contra el promedio de los 7 equipos.
        prom = np.nanmean([v for v in vals.values() if v is not None]) if any(v is not None for v in vals.values()) else None
        val = vals.get(empresa)
        if prom in (None, 0) or val is None:
            return None
        return (val - prom) / abs(prom) * 100

    def delta_str(vals, empresa=empresa_analisis):
        d = delta_raw(vals, empresa)
        return f'{d:+.1f}% vs Prom' if d is not None else None

    # Los 3 números que más resumen la foto financiera de la ronda (rentabilidad, liquidez y
    # riesgo de corto plazo) van en la banda oscura, mismo patrón que Resultados/Resumen. El resto
    # (márgenes y calificación) da contexto pero no es lo primero que se mira -- queda abajo en
    # tarjetas claras.
    d_ebitda = delta_raw(ebitda_vals)
    d_caja = delta_raw(caja_vals)
    d_deuda = delta_raw(deuda_cp_vals)
    kpi_banda_oscura([
        {'label': 'EBITDA (USD)', 'valor': format_num(ebitda_vals.get(empresa_analisis)) if pd.notna(ebitda_vals.get(empresa_analisis)) else '—',
         'delta': f'{d_ebitda:+.1f}% vs Prom' if d_ebitda is not None else None, 'favorable': (d_ebitda > 0) if d_ebitda is not None else None},
        {'label': 'Caja final (USD)', 'valor': format_num(caja_vals.get(empresa_analisis)) if pd.notna(caja_vals.get(empresa_analisis)) else '—',
         'delta': f'{d_caja:+.1f}% vs Prom' if d_caja is not None else None, 'favorable': (d_caja > 0) if d_caja is not None else None},
        {'label': 'Deuda CP no planificada (USD)', 'valor': format_num(val_deuda_cp) if val_deuda_cp is not None else '—',
         # Acá menos es mejor -- favorable se invierte respecto de EBITDA/Caja.
         'delta': f'{d_deuda:+.1f}% vs Prom' if d_deuda is not None else None, 'favorable': (d_deuda < 0) if d_deuda is not None else None},
    ])

    f2, f3, f6, f7 = st.columns(4)
    with f2: st.metric('Margen bruto', f"{margen_vals.get(empresa_analisis):,.1f}%" if pd.notna(margen_vals.get(empresa_analisis)) else '—', delta=delta_str(margen_vals))
    with f3: st.metric('ROS', f"{ros_vals.get(empresa_analisis):,.1f}%" if pd.notna(ros_vals.get(empresa_analisis)) else '—', delta=delta_str(ros_vals))
    with f6: st.metric('Deuda LP (USD)', format_num(deuda_lp_vals.get(empresa_analisis)), delta=delta_str(deuda_lp_vals), delta_color='inverse')
    with f7: st.metric('Calificación crediticia', calif_val if calif_val else '—')
    st.write('')

    st.write('')

    tab_cp, tab_lp, tab_cg = st.tabs(['Corto Plazo: Liquidez y Operación', 'Largo Plazo: Estructura, Retorno y Competencia',
                                       'Comparativa Plan vs. Real'])

    # Control de Gestión: es inherentemente sobre CADIZ (es nuestra propia proyección, no la de
    # "Equipo en foco") -- si se está mirando otro equipo, se avisa en vez de mostrar el gap de
    # CADIZ sin aclarar de quién es. Convertido de toggle suelto a pestaña (Adenda 11) por
    # consistencia con Resultados/Mercado/Operaciones, que ahora tienen la misma pestaña.
    with tab_cg:
        if empresa_analisis == MY_COMPANY:
            panel_comparativa_plan_real(df, ronda_snapshot, key_suffix='finanzas', mostrar_directo=True)
            st.divider()
            fila3_finanzas_flujo_caja(df_all.copy(), ronda_snapshot, ronda_a_num(ronda_snapshot), get_proyeccion())
        else:
            st.caption('Cambiá "Equipo en foco" a CADIZ en la barra lateral para ver la Comparativa Plan vs. Real.')

    with tab_cp:
        # El detalle del sobregiro ya lo levanta el panel de alertas en Resultados: acá va
        # solamente cómo evoluciona y cómo se compara contra la industria.
        st.subheader('Deuda y liquidez')
        col_dl_a, col_dl_b = st.columns(2)
        with col_dl_a:
            deuda_cp_sub = df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Metrica'] == 'Deudas a corto plazo (no planificadas)')]
            chart_evolucion(deuda_cp_sub, 'Deuda CP no planificada (USD)')
        with col_dl_b:
            ranking_deuda = pd.DataFrame(list(deuda_cp_vals.items()), columns=['Empresa', 'Valor']).dropna().sort_values('Valor', ascending=False)
            if not ranking_deuda.empty and ranking_deuda['Valor'].sum() > 0:
                ranking_deuda['Etiqueta'] = ranking_deuda['Valor'].apply(format_num)
                fig_dcp = px.bar(ranking_deuda, x='Empresa', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                                  title=f'Deuda CP no planificada — {ronda_snapshot}', text='Etiqueta')
                fig_dcp.update_traces(textposition='outside', cliponaxis=False, showlegend=False)
                mostrar(fig_dcp, ocultar_eje_valores='y')
            else:
                st.info('Ningún equipo tomó deuda de corto plazo no planificada en esta ronda.')


    with tab_lp:
        # Subsección 2: Largo Plazo (Estructura, Retorno y Rangos)

        st.markdown('**Estructura del Balance: Activo vs. Pasivo + Patrimonio Neto**')
        bal_ronda = df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]

        def gb(metrica):
            return valor_de(bal_ronda, metrica, empresa_analisis) or 0.0

        activo_items = {'Efectivo y equivalentes': gb('Efectivo y equivalentes de efectivo'),
                         'Cuentas por cobrar': gb('Cuentas por Cobrar'), 'Inventario': gb('Inventario'),
                         'Activo fijo': gb('Activo fijo')}
        pasivo_pn_items = {'Cuentas por pagar': gb('Cuentas por pagar'),
                            'Deudas CP no planificadas': gb('Deudas a corto plazo (no planificadas)'),
                            'Deudas LP': gb('Deudas a largo plazo'),
                            'Capital social + adicional': gb('Capital social') + gb('Capital adicional desembolsado'),
                            'Ganancias acumuladas + de la ronda': gb('Ganancias acumuladas') + gb('Beneficio de la ronda')}
        if sum(activo_items.values()) > 0:
            fig_bal = go.Figure()
            # Paletas separadas por lado: antes el verde era "Activo fijo" a la izquierda y
            # "Deudas LP" a la derecha, y el tan era "Inventario" y "Ganancias acumuladas".
            # Con la misma paleta de los dos lados parecía que un color significaba lo mismo.
            colores_activo = ['#3E7CB1', '#5C9BC9', '#8FBEDC', '#C3DCEC']          # azules  = qué tengo
            colores_pasivo = ['#C9922E', '#B3261E', '#8C6D3F', '#6E8C6E', '#A8A29A']  # cálidos = quién lo financia
            for (nombre, val), color in zip(activo_items.items(), colores_activo):
                fig_bal.add_trace(go.Bar(x=['Activo'], y=[val], name=nombre, marker_color=color,
                                          text=format_num(val), textposition='inside', showlegend=False))
            for (nombre, val), color in zip(pasivo_pn_items.items(), colores_pasivo):
                fig_bal.add_trace(go.Bar(x=['Pasivo + PN'], y=[val], name=nombre, marker_color=color,
                                          text=format_num(val), textposition='inside', showlegend=False))
            fig_bal.update_layout(
                barmode='stack', title=f'Estructura del Balance — {empresa_analisis}, {ronda_snapshot}',
                # Dos leyendas separadas, cada una pegada a la barra que le corresponde —
                # antes una sola leyenda combinada hacía difícil saber qué color era de qué lado.
                showlegend=False)
            mostrar(fig_bal, ocultar_eje_valores='y')
            # La leyenda de Plotly, aun puesta afuera, mezclaba los conceptos de los dos lados en
            # una sola tira. Se dibuja a mano en dos columnas, cada una bajo su barra, para que
            # se vea de una qué compone el Activo y qué compone el Pasivo + PN.
            def bloque_leyenda(titulo, items, colores):
                filas = ''.join(
                    f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:0.82rem">'
                    f'<span style="width:11px;height:11px;border-radius:3px;background:{c};flex:none"></span>'
                    f'<span style="flex:1">{n}</span>'
                    f'<span style="opacity:0.65">{format_num(v)}</span></div>'
                    for (n, v), c in zip(items.items(), colores))
                return (f'<div style="font-weight:600;font-size:0.8rem;opacity:0.7;text-transform:uppercase;'
                        f'letter-spacing:0.02em;margin-bottom:4px">{titulo}</div>{filas}')
            col_leg_a, col_leg_p = st.columns(2)
            with col_leg_a:
                st.markdown(bloque_leyenda('Activo', activo_items, colores_activo), unsafe_allow_html=True)
            with col_leg_p:
                st.markdown(bloque_leyenda('Pasivo + PN', pasivo_pn_items, colores_pasivo), unsafe_allow_html=True)
            st.caption('Los dos lados deben dar la misma altura (el Balance siempre cierra) — Activo total = Pasivo + Patrimonio Neto.')
        else:
            st.info('Sin datos de balance para esta combinación.')

        st.divider()
        st.markdown('**Costo de la deuda por mercado**')
        # La calificación crediticia se muestra una sola vez, en los KPIs fijos de la sección.
        tasas_metricas = {'EE.UU. (corto)': 'EE.UU., corto', 'EE.UU. (largo)': 'EE.UU., largo',
                           'China (corto)': 'China, corto', 'Europa (corto)': 'Europa, corto'}
        tasas_rows = []
        for etiqueta, metrica in tasas_metricas.items():
            val_emp = valor_de(ratios_ronda, metrica, empresa_analisis)
            prom = np.nanmean([valor_de(ratios_ronda, metrica, e) for e in COMPANIES if valor_de(ratios_ronda, metrica, e) is not None])
            if val_emp is not None:
                tasas_rows.append({'Mercado': etiqueta, empresa_analisis: val_emp, 'Promedio industria': prom})
        if tasas_rows:
            tasas_df = pd.DataFrame(tasas_rows).melt(id_vars='Mercado', var_name='Serie', value_name='Tasa, %')
            fig_tasas = px.bar(tasas_df, x='Mercado', y='Tasa, %', color='Serie', barmode='group',
                                color_discrete_map={empresa_analisis: BRAND_ACCENT, 'Promedio industria': MUTED_PALETTE[0]},
                                title=f'Tasa de interés por mercado y plazo — {empresa_analisis} vs. industria, {ronda_snapshot}')
            fig_tasas.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
            mostrar(fig_tasas)
            st.caption('Tasas más altas en general reflejan menor calificación crediticia (la tarjeta de arriba).')

        datos_lp = {
            'ROCE': {e: valor_fuzzy(ratios_ronda, 'Rentabilidad del capital empleado', empresa=e) for e in COMPANIES},
            'ROE': {e: valor_de(ratios_ronda, 'Rendimiento de los Fondos Propios (ROE)', e) for e in COMPANIES},
            'Apalancamiento': {e: valor_de(ratios_ronda, 'Endeudamiento neto/patrimonio (apalancamiento)', e) for e in COMPANIES},
            'WACC': {e: wacc(e) for e in COMPANIES},
        }
        ejes_validos = {k: v for k, v in datos_lp.items() if len([x for x in v.values() if pd.notna(x)]) >= 2}
        if ejes_validos:
            color_ref = 'rgba(255,255,255,0.5)' if es_modo_oscuro() else 'rgba(26,23,20,0.5)'
            fig_rango = go.Figure()
            for i, (nombre, vals) in enumerate(ejes_validos.items()):
                valores = sorted(v for v in vals.values() if pd.notna(v))
                vmin, vmax, vmed = valores[0], valores[-1], np.median(valores)
                vcadiz = vals.get(empresa_analisis)
                rango = (vmax - vmin) or 1
                pos = lambda x: (x - vmin) / rango * 100
                suf = "%" if nombre in ['ROCE', 'ROE', 'WACC'] else "x"
            
                fig_rango.add_trace(go.Scatter(x=[0, 100], y=[i, i], mode='lines', line=dict(color=MUTED_PALETTE[3], width=6), showlegend=False))
                fig_rango.add_trace(go.Scatter(x=[pos(vmed)], y=[i], mode='markers', marker=dict(symbol='line-ns', size=16, color=MUTED_PALETTE[1], line_width=2), showlegend=False))
            
                if vcadiz is not None:
                    val_str = f"{vcadiz:,.1f}{suf}"
                    fig_rango.add_trace(go.Scatter(
                        x=[pos(vcadiz)], y=[i], 
                        mode='markers+text', 
                        text=[val_str], 
                        textposition="top center", 
                        textfont=dict(color=BRAND_ACCENT, size=12, family="JetBrains Mono"),
                        marker=dict(size=14, color=BRAND_ACCENT), 
                        showlegend=False
                    ))
            
                fig_rango.add_annotation(x=0, y=i, text=f'{vmin:,.1f}{suf}', showarrow=False, xshift=-30, font=dict(size=11, color=color_ref))
                fig_rango.add_annotation(x=100, y=i, text=f'{vmax:,.1f}{suf}', showarrow=False, xshift=30, font=dict(size=11, color=color_ref))
            
            fig_rango.update_layout(yaxis=dict(tickmode='array', tickvals=list(range(len(ejes_validos))), ticktext=list(ejes_validos.keys())), xaxis=dict(range=[-15, 115]), title='Rango de Industria (Mín / Mediana / CÁDIZ / Máx)')
            mostrar(fig_rango, ocultar_eje_valores='x')
        st.divider()
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            rr = pd.DataFrame({'Empresa': COMPANIES, 'Apalancamiento': [datos_lp['Apalancamiento'].get(e) for e in COMPANIES], 'ROE': [datos_lp['ROE'].get(e) for e in COMPANIES]}).dropna()
            if len(rr) > 1:
                fig = px.scatter(rr, x='Apalancamiento', y='ROE', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa', title='Matriz Riesgo / Retorno')
                fig.update_traces(textposition='top center', showlegend=False)
                linea_media(fig, rr['Apalancamiento'].mean(), eje='x')
                linea_media(fig, rr['ROE'].mean(), eje='y')
                mostrar(fig)
        with col_f2:
            ben = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Metrica'] == 'Beneficio de la ronda')].copy()
            deuda = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Metrica'] == 'Endeudamiento neto/patrimonio (apalancamiento)')].copy()
            ben['Valor'] = num(ben['Valor'])
            deuda['Valor'] = num(deuda['Valor'])
            ben = ben[ben['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')
            deuda = deuda[deuda['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')
            if not ben.empty and not deuda.empty:
                # Antes doble eje Y, con la escala de Apalancamiento llegando a negativo -- eso puede
                # sugerir una correlación entre las dos series que no está probada. Dos paneles, cada
                # métrica con su propia escala (ver chart_dos_metricas_apiladas).
                chart_dos_metricas_apiladas('Beneficio Neto vs. Nivel de Deuda',
                                             ben['Ronda'], ben['Valor'], 'Beneficio (USD)', COLOR_POSITIVE, 'bar',
                                             deuda['Ronda'], deuda['Valor'], 'Apalancamiento (x)', MUTED_PALETTE[1], 'line')
    # =================================================================
    # SECCIÓN 5 — RRHH Y SOSTENIBILIDAD
    # =================================================================
def seccion_rrhh_sostenibilidad():
    bloque_rrhh, bloque_sost = st.tabs(['Personal y Talento', 'Sostenibilidad'])

    with bloque_rrhh:
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader('Salario y rotación')
            salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
            rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
            if not salario.empty and not rotacion.empty:
                # Antes doble eje Y (Salario en USD y Rotación en % superpuestos en el mismo plano) --
                # dos paneles apilados, cada métrica con su propia escala.
                chart_dos_metricas_apiladas('Evolución: Salario vs Rotación',
                                             salario['Ronda'], salario['Valor'], 'Salario (USD)', COLOR_METRICA['dinero'], 'line',
                                             rotacion['Ronda'], rotacion['Valor'], 'Rotación (%)', COLOR_METRICA['riesgo'], 'line')
        with col_b:
            st.subheader('Rotación y contrataciones')
            contrat = rrhh[rrhh['Metrica'] == 'Contrataciones + / despidos -'].sort_values('Ronda_Orden')
            if not salario.empty and not contrat.empty and not rotacion.empty:
                chart_dos_metricas_apiladas('Rotación vs. Contrataciones netas',
                                             contrat['Ronda'], contrat['Valor'], 'Contrataciones netas (personas)', COLOR_METRICA['personas'], 'bar',
                                             rotacion['Ronda'], rotacion['Valor'], 'Rotación (%)', COLOR_METRICA['riesgo'], 'line')
                st.caption('Cuántas contrataciones netas hizo falta hacer, en la misma ronda en que se dio la rotación.')

        st.divider()
        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader('Inversión en I+D')
            idn = rrhh[rrhh['Metrica'] == 'Número de personal de I+D, esta ronda'].sort_values('Ronda_Orden')
            idc = rrhh[rrhh['Metrica'] == 'Otros costos variables de I + D'].sort_values('Ronda_Orden')
            if not idn.empty and not idc.empty:
                chart_dos_metricas_apiladas('Inversión en I+D: costo vs. dotación',
                                             idc['Ronda'], idc['Valor'], 'Costo variable I+D (USD)', COLOR_METRICA['dinero'], 'bar',
                                             idn['Ronda'], idn['Valor'], 'Personal I+D (headcount)', COLOR_METRICA['personas'], 'line')
            else:
                st.info('Sin datos de I+D para este equipo.')
        with col_d:
            st.subheader('Capacitación e impacto')
            capac = rrhh[rrhh['Metrica'] == 'Presupuesto mensual para capacitación, USD'].sort_values('Ronda_Orden')
            efic = rrhh[rrhh['Metrica'] == 'Multiplicador de la eficiencia de RRHH'].sort_values('Ronda_Orden')
            if not capac.empty and not efic.empty:
                chart_dos_metricas_apiladas('Capacitación vs. eficiencia de RRHH',
                                             capac['Ronda'], capac['Valor'], 'Presupuesto capacitación (USD)', COLOR_METRICA['dinero'], 'bar',
                                             efic['Ronda'], efic['Valor'], 'Multiplicador eficiencia RRHH', COLOR_METRICA['eficiencia'], 'line')
                st.caption('Ojo con leer una relación directa: el efecto de la capacitación no es instantáneo, así que el '
                           'presupuesto de una ronda y el multiplicador de esa MISMA ronda no se explican entre sí. '
                           'Lo que hay que mirar es la pendiente del multiplicador en las rondas siguientes a un aumento de presupuesto.')
            else:
                st.info('Sin datos de capacitación para este equipo.')

    with bloque_sost:
        st.subheader('Impacto ambiental')
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg_rrhh')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'], key='ind_esg_rrhh')
        dicc = {'Emisiones de CO2': 'Total, toneladas métricas', 'Consumo de energía': 'Total, MWh', 'Consumo de agua': 'Total, miles de m3'}
        sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_esg}') & (df['Metrica'] == dicc[ind])]
        chart_comparacion_equipos(sub_amb, f'{ind} — {pais_esg}')

        st.divider()
        st.subheader('Reputación ESG y cuota de mercado')
        esg = df[(df['Estado'] == 'Informe ESG') & (df['Subgrupo'] == 'Puntuación final') & (df['Metrica'] == 'Reputación ESG') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].copy()
        esg['Valor'] = num(esg['Valor'])
        cols = st.columns(3)
        for i, pais in enumerate(['EE.UU.', 'China', 'Europa']):
            with cols[i]:
                mkt = df[(df['Estado'] == f'Informe de mercado, {pais}') & (df['Seccion'] == f'{pais} cuotas de mercado, %') & (df['Metrica'].str.strip() == 'Total') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].rename(columns={'Valor': 'Share'})
                mkt['Share'] = num(mkt['Share'])
                d = esg.merge(mkt, on='Empresa').dropna()
                if len(d) > 1:
                    fig2 = px.scatter(d, x='Valor', y='Share', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa', title=f'ESG vs Share - {pais}')
                    fig2.update_traces(textposition='top center', showlegend=False)
                    mostrar(fig2)
# ---------------- Router ----------------
st.title(seccion)
if seccion == SECCIONES[0]: seccion_resultado()
elif seccion == SECCIONES[1]: seccion_mercado()
elif seccion == SECCIONES[2]: seccion_operaciones()
elif seccion == SECCIONES[3]: seccion_finanzas()
elif seccion == SECCIONES[4]: seccion_rrhh_sostenibilidad()
