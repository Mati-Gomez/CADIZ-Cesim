"""
app.py — Tablero de Control Directivo, Grupo CADIZ (Cesim Global Automotive)

Como cargar una ronda nueva:
    1. Descargar el .xls de resultados de la ronda desde Cesim.
    2. Subirlo a la carpeta data/raw/ de este repo.
    3. Listo. La app lee todos los .xls de data/raw/ en cada carga y arma
       el historico sola — no hace falta correr ningun script aparte.
"""
import glob
import os
import re

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from cesim_parser import build_historico

MY_COMPANY = 'CADIZ'
COMPANIES = ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CUORE', 'FOCUS', 'TOKIO']
BRAND_ACCENT = '#D9FF50'
BRAND_DARK = '#1A1A2E'
MUTED_PALETTE = ['#8C8FA3', '#B7B9C6', '#6E7180', '#A3A6B5', '#5C5F6E', '#9497A6']

COLOR_MAP = {MY_COMPANY: BRAND_ACCENT}
for i, c in enumerate([c for c in COMPANIES if c != MY_COMPANY]):
    COLOR_MAP[c] = MUTED_PALETTE[i % len(MUTED_PALETTE)]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

st.set_page_config(page_title='CADIZ | Tablero Cesim', layout='wide')


# ---------------- Carga de datos ----------------
def get_pais(estado: str) -> str:
    if re.search(r'\bGlobal\b', estado) or 'casa matriz' in estado:
        return 'Global'
    if 'EE.UU.' in estado:
        return 'EE.UU.'
    if 'China' in estado:
        return 'China'
    if 'Europa' in estado:
        return 'Europa'
    return 'General'


@st.cache_data(show_spinner='Procesando rondas...')
def cargar_historico(files_signature: tuple) -> pd.DataFrame:
    data = build_historico(list(files_signature))
    data['Pais'] = data['Estado'].apply(get_pais)
    return data


def get_data() -> pd.DataFrame:
    xls_files = sorted(glob.glob(f'{DATA_DIR}/*.xls') + glob.glob(f'{DATA_DIR}/*.XLS'))
    if not xls_files:
        st.warning(f'No se encontraron archivos .xls en {DATA_DIR}/. Subí al menos una ronda.')
        st.caption(f'(Buscando en: {DATA_DIR})')
        st.stop()
    return cargar_historico(tuple(xls_files))


df = get_data()
rondas_disponibles = (
    df[['Ronda', 'Ronda_Orden']].drop_duplicates().sort_values('Ronda_Orden')['Ronda'].tolist()
)
ronda_ultima = rondas_disponibles[-1]

MODULOS = ['Resumen', 'Estados financieros', 'Ratios', 'Informes de mercado',
           'Informe de RRHH', 'Sostenibilidad', 'Informes de producción',
           'Informes de costos', 'Clasificación', 'Valuación', 'Creación de valor']

# ---------------- Sidebar ----------------
st.sidebar.markdown('### CADIZ — Cesim Global Automotive')
st.sidebar.caption(f"{len(rondas_disponibles)} ronda(s): {', '.join(rondas_disponibles)}")
modulo = st.sidebar.radio('Módulo', MODULOS)


# ---------------- Helpers de gráficos ----------------
def chart_comparacion_equipos(sub: pd.DataFrame, metrica: str):
    """Barra: valor de la última ronda por equipo, CADIZ resaltado."""
    ultima = sub[sub['Ronda'] == ronda_ultima].copy()
    ultima['Valor'] = pd.to_numeric(ultima['Valor'], errors='coerce')
    ultima = ultima.dropna(subset=['Valor']).sort_values('Valor', ascending=False)
    if ultima.empty:
        st.info('No hay datos numéricos para esta métrica en la última ronda.')
        return
    fig = px.bar(ultima, x='Empresa', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                 title=f'{metrica} — {ronda_ultima} (todos los equipos)', text_auto='.2s')
    fig.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)


def chart_evolucion(sub: pd.DataFrame, metrica: str):
    """Línea: evolución de la métrica por ronda, para los 7 equipos, CADIZ resaltada."""
    ev = sub.copy()
    ev['Valor'] = pd.to_numeric(ev['Valor'], errors='coerce')
    ev = ev.dropna(subset=['Valor'])
    if ev.empty:
        st.info('No hay datos numéricos para el gráfico de evolución.')
        return
    fig = go.Figure()
    for comp in COMPANIES:
        d = ev[ev['Empresa'] == comp].sort_values('Ronda_Orden')
        if d.empty:
            continue
        es_cadiz = comp == MY_COMPANY
        fig.add_trace(go.Scatter(
            x=d['Ronda'], y=d['Valor'], mode='lines+markers', name=comp,
            line=dict(color=COLOR_MAP[comp], width=4 if es_cadiz else 1.5),
            marker=dict(size=8 if es_cadiz else 5),
            opacity=1.0 if es_cadiz else 0.6,
        ))
    fig.update_layout(title=f'Evolución — {metrica}', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)


def render_modulo(modulo_nombre: str):
    """Renderer genérico: país (si aplica) → estado/reporte → métrica → gráficos."""
    sub = df[df['Modulo'] == modulo_nombre]
    if sub.empty:
        st.info('Sin datos para este módulo todavía.')
        return

    paises = sorted(sub['Pais'].unique())
    col_a, col_b = st.columns(2)
    if len(paises) > 1:
        pais_sel = col_a.selectbox('País / Región', paises)
        sub = sub[sub['Pais'] == pais_sel]
    else:
        col_a.caption(f"Alcance: {paises[0] if paises else 'General'}")

    estados = sorted(sub['Estado'].unique())
    if len(estados) > 1:
        estado_sel = col_b.selectbox('Reporte', estados)
        sub = sub[sub['Estado'] == estado_sel]

    metricas = sorted(sub['Metrica'].unique())
    metrica_sel = st.selectbox('Métrica', metricas)
    sub_metrica = sub[sub['Metrica'] == metrica_sel]

    c1, c2 = st.columns(2)
    with c1:
        chart_comparacion_equipos(sub_metrica, metrica_sel)
    with c2:
        chart_evolucion(sub_metrica, metrica_sel)

    with st.expander('Ver datos crudos de esta selección'):
        st.dataframe(sub_metrica.sort_values(['Ronda_Orden', 'Empresa']), use_container_width=True)


# ---------------- Páginas especiales ----------------
def render_resumen():
    ultima = df[df['Ronda'] == ronda_ultima]

    ebitda_row = ultima[(ultima['Modulo'] == 'Estados financieros') & (ultima['Pais'] == 'Global') &
                         (ultima['Metrica'].str.contains('EBITDA', na=False, case=False)) &
                         (ultima['Empresa'] == MY_COMPANY)]
    ebitda = ebitda_row['Valor'].iloc[0] if len(ebitda_row) else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Ronda actual', ronda_ultima)
    col2.metric('EBITDA (Global)', f'{ebitda:,.0f}' if ebitda is not None else '—')

    cv_metric = 'Valor total creado'
    cv = ultima[(ultima['Modulo'] == 'Creación de valor') & (ultima['Metrica'] == cv_metric) &
                (ultima['Empresa'] == MY_COMPANY)]
    col3.metric('Creación de valor', f"{cv['Valor'].iloc[0]:,.0f}" if len(cv) else '—')

    cv_todas = ultima[(ultima['Modulo'] == 'Creación de valor') & (ultima['Metrica'] == cv_metric)].copy()
    if len(cv_todas):
        cv_todas['Valor'] = pd.to_numeric(cv_todas['Valor'], errors='coerce')
        ranking = cv_todas.groupby('Empresa')['Valor'].sum().sort_values(ascending=False)
        posicion = list(ranking.index).index(MY_COMPANY) + 1 if MY_COMPANY in ranking.index else None
        col4.metric('Posición (creación de valor)', f'{posicion}° de {len(ranking)}' if posicion else '—')

    st.divider()
    st.subheader('Creación de valor — evolución de los 7 equipos')
    cv_evol = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == cv_metric)]
    chart_evolucion(cv_evol, 'Valor total creado')


def render_clasificacion():
    st.caption('Ranking entre los 7 equipos según creación de valor (criterio ganador de Cesim).')
    cv_metric = 'Valor total creado'
    ronda_sel = st.selectbox('Ronda', rondas_disponibles, index=len(rondas_disponibles) - 1)
    cv = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == cv_metric) & (df['Ronda'] == ronda_sel)].copy()
    cv['Valor'] = pd.to_numeric(cv['Valor'], errors='coerce')
    ranking = cv.groupby('Empresa')['Valor'].sum().sort_values(ascending=False).reset_index()
    ranking.insert(0, 'Puesto', range(1, len(ranking) + 1))

    fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa',
                 color_discrete_map=COLOR_MAP, text_auto='.2s',
                 title=f'Ranking de creación de valor — {ronda_sel}')
    fig.update_layout(showlegend=False, yaxis=dict(categoryorder='total ascending'), plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(ranking, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader('Evolución del puesto de CADIZ por ronda')
    cv_all = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == cv_metric)].copy()
    cv_all['Valor'] = pd.to_numeric(cv_all['Valor'], errors='coerce')
    puestos = (cv_all.groupby(['Ronda', 'Ronda_Orden', 'Empresa'])['Valor'].sum().reset_index()
               .sort_values(['Ronda_Orden', 'Valor'], ascending=[True, False]))
    puestos['Puesto'] = puestos.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
    cadiz_puesto = puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden')
    fig2 = px.line(cadiz_puesto, x='Ronda', y='Puesto', markers=True)
    fig2.update_yaxes(autorange='reversed', dtick=1)  # puesto 1 arriba
    fig2.update_traces(line=dict(color=BRAND_ACCENT, width=4))
    st.plotly_chart(fig2, use_container_width=True)


# ---------------- Router ----------------
st.title(modulo)

if modulo == 'Resumen':
    render_resumen()
elif modulo == 'Clasificación':
    render_clasificacion()
else:
    render_modulo(modulo)
