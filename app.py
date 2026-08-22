"""
app.py — Tablero de Control Directivo, Grupo CADIZ (Cesim Global Automotive)

Como cargar una ronda nueva:
    1. Descargar el .xls de resultados de la ronda desde Cesim.
    2. Subirlo a la carpeta data/raw/ de este repo (drag & drop en github.com
       o `git add data/raw/tu_archivo.xls && git commit && git push`).
    3. Listo. Esta app lee TODOS los .xls de data/raw/ en cada carga y arma
       el historico sola — no hace falta correr ningun script aparte.
"""
import glob
import os
import streamlit as st
import pandas as pd
import plotly.express as px

from cesim_parser import build_historico

MY_COMPANY = 'CADIZ'
BRAND_ACCENT = '#D9FF50'
BRAND_DARK = '#1A1A2E'
# Ruta ABSOLUTA relativa a la ubicación de este archivo, no al directorio
# desde donde se ejecuta streamlit — evita el error "no se encontraron .xls"
# cuando se corre `streamlit run app.py` desde otra carpeta.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

st.set_page_config(page_title='CADIZ | Tablero Cesim', layout='wide')


@st.cache_data(show_spinner='Procesando rondas...')
def cargar_historico(files_signature: tuple) -> pd.DataFrame:
    # files_signature (lista de rutas) solo se usa para invalidar la cache
    # cuando cambia el set de archivos en data/raw/
    paths = list(files_signature)
    return build_historico(paths)


def get_data() -> pd.DataFrame:
    # case-insensitive por si el archivo quedo como .XLS
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

# ---------------- Sidebar ----------------
st.sidebar.markdown(f"### CADIZ — Cesim Global Automotive")
st.sidebar.caption(f"{len(rondas_disponibles)} ronda(s) cargada(s): {', '.join(rondas_disponibles)}")

modulos = ['Resumen', 'Estados financieros', 'Ratios', 'Informes de mercado',
           'Informe de RRHH', 'Sostenibilidad', 'Informes de producción',
           'Informes de costos', 'Clasificación', 'Valuación', 'Creación de valor']
modulo = st.sidebar.radio('Módulo', modulos)

ronda_ultima = rondas_disponibles[-1]

# ---------------- Contenido ----------------
st.title(modulo)

if modulo == 'Resumen':
    ultima = df[df['Ronda'] == ronda_ultima]
    creacion_valor = ultima[(ultima['Modulo'] == 'Creación de valor') & (ultima['Empresa'] == MY_COMPANY)]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('Ronda actual', ronda_ultima)
    with col2:
        ebitda_row = ultima[(ultima['Estado'].str.contains('resultados, miles USD, Global', na=False)) &
                             (ultima['Metrica'].str.contains('EBITDA', na=False)) &
                             (ultima['Empresa'] == MY_COMPANY)]
        val = ebitda_row['Valor'].iloc[0] if len(ebitda_row) else None
        st.metric('EBITDA (Global)', f'{val:,.0f}' if val is not None else '—')
    with col3:
        val = creacion_valor['Valor'].iloc[0] if len(creacion_valor) else None
        st.metric('Creación de valor', f'{val:,.0f}' if val is not None else '—')

    st.caption('KPIs de arranque — se amplía con el resto de los módulos.')

elif modulo == 'Creación de valor':
    sub = df[df['Modulo'] == 'Creación de valor']
    fig = px.line(sub, x='Ronda_Orden', y='Valor', color='Empresa', line_group='Empresa',
                   markers=True, hover_data=['Ronda'],
                   title='Evolución de creación de valor por empresa')
    fig.update_traces(line=dict(width=4), selector=dict(name=MY_COMPANY))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info(f'Módulo "{modulo}" — pendiente de construir sobre este mismo esqueleto de datos.')
    sub = df[df['Modulo'] == modulo]
    st.dataframe(sub, use_container_width=True)
