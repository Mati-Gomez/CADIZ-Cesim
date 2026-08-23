"""
app.py — Tablero de Control Directivo, Grupo CADIZ (Cesim Global Automotive)

Como cargar una ronda nueva:
    1. Descargar el .xls de resultados de la ronda desde Cesim.
    2. Subirlo a la carpeta data/raw/ de este repo.
    3. Listo. La app lee todos los .xls de data/raw/ en cada carga y arma
       el historico sola — no hace falta correr ningun script aparte.

Arquitectura: 5 secciones directivas. Tabs solo donde selectores distintos
(país/tecnología) afectan a un subconjunto de gráficos — el resto es un
único scroll consolidado (KPIs arriba, gráficos clave al medio, detalle
operativo abajo).

Reglas de estética (acordadas):
- Líneas de promedio/mediana SOLO en métricas aisladas de CADIZ (evolución
  histórica). Los gráficos que muestran a los 7 equipos a la vez van limpios.
- Cero gridlines de fondo.
- CADIZ en verde flúor de marca; competencia y promedios en grises apagados.
- Si una barra/punto ya trae la etiqueta de dato incrustada, se oculta el
  eje de valores para no duplicar información.
"""
import glob
import os
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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


def num(series):
    return pd.to_numeric(series, errors='coerce')


df_all = get_data()

# ---------------- Sidebar: filtros globales ----------------
st.sidebar.markdown('### CADIZ — Cesim Global Automotive')

filtro_tipo = st.sidebar.radio('Rondas a incluir', ['Todas', 'Solo oficiales', 'Solo prácticas'], horizontal=False)
if filtro_tipo == 'Solo oficiales':
    df = df_all[df_all['Tipo_Ronda'] == 'Oficial'].copy()
elif filtro_tipo == 'Solo prácticas':
    df = df_all[df_all['Tipo_Ronda'] == 'Práctica'].copy()
else:
    df = df_all.copy()

if df.empty:
    st.warning('No hay rondas para ese filtro. Probá con "Todas".')
    st.stop()

rondas_disponibles = df[['Ronda', 'Ronda_Orden']].drop_duplicates().sort_values('Ronda_Orden')['Ronda'].tolist()
ronda_ultima = rondas_disponibles[-1]

st.sidebar.caption(f"{len(rondas_disponibles)} ronda(s): {', '.join(rondas_disponibles)}")
ronda_snapshot = st.sidebar.selectbox('Ronda (vistas de una ronda)', rondas_disponibles, index=len(rondas_disponibles) - 1)
empresa_analisis = st.sidebar.selectbox('Equipo (vistas individuales)', COMPANIES, index=0)

st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=False)

SECCIONES = [
    '1. El Resultado',
    '2. El Frente de Batalla (Mercado)',
    '3. La Sala de Máquinas (Operaciones)',
    '4. La Salud del Negocio (Finanzas)',
    '5. El Largo Plazo (RRHH y Sostenibilidad)',
]
seccion = st.sidebar.radio('Sección', SECCIONES)

# ---------------- Tema (Plotly + CSS) ----------------
PLOTLY_TEMPLATE = 'plotly_dark' if modo_oscuro else 'plotly_white'
COLOR_TEXT = '#EDEDF2' if modo_oscuro else BRAND_DARK
COLOR_REF_LINE = 'rgba(255,255,255,0.35)' if modo_oscuro else 'rgba(26,26,46,0.35)'
COLOR_GAUGE_BG1 = '#2B2B40' if modo_oscuro else '#EAEAF2'
COLOR_GAUGE_BG2 = '#3D3D57' if modo_oscuro else '#D8D8E8'
COLOR_TOTAL_BAR = '#4A4A66' if modo_oscuro else BRAND_DARK

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

[data-testid="stMetric"] {{
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 10px;
    padding: 14px 16px 10px 16px;
}}
[data-testid="stMetricLabel"] {{ font-weight: 500; opacity: 0.85; }}

section[data-testid="stSidebar"] h3 {{
    border-bottom: 3px solid {BRAND_ACCENT};
    padding-bottom: 8px;
    display: inline-block;
}}

.stTabs [data-baseweb="tab-highlight"] {{ background-color: {BRAND_ACCENT} !important; }}
.stTabs [aria-selected="true"] {{ color: {BRAND_ACCENT if modo_oscuro else BRAND_DARK} !important; font-weight: 600; }}

h1, h2, h3 {{ letter-spacing: -0.01em; }}
</style>
""", unsafe_allow_html=True)


def mostrar(fig, ocultar_eje_valores=None, **kwargs):
    """Aplica el tema activo, saca gridlines, y opcionalmente oculta el eje
    de valores cuando el gráfico ya trae etiquetas de dato incrustadas."""
    fig.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=COLOR_TEXT, family='Inter, sans-serif'))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    if ocultar_eje_valores == 'y':
        fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x':
        fig.update_xaxes(showticklabels=False, title=None)
    st.plotly_chart(fig, use_container_width=True, **kwargs)


def linea_media(fig, valor, eje='y', etiqueta='Promedio industria'):
    """Línea de referencia punteada — usar SOLO en gráficos de una métrica aislada de CADIZ."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return
    kwargs = dict(line_dash='dash', line_color=COLOR_REF_LINE, line_width=1.5,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color=COLOR_REF_LINE)
    if eje == 'y':
        fig.add_hline(y=valor, **kwargs)
    else:
        fig.add_vline(x=valor, **kwargs)


def tarjeta_delta(label, valor, promedio, fmt=',.0f', sufijo=''):
    if valor is None:
        st.metric(label, '—')
        return
    delta = None
    if promedio not in (None, 0) and not (isinstance(promedio, float) and np.isnan(promedio)):
        delta = (valor - promedio) / promedio * 100
    st.metric(label, f'{valor:{fmt}}{sufijo}',
              delta=f'{delta:+.1f}% vs. industria' if delta is not None else None)


# ---------------- Helpers de gráficos reutilizables ----------------
def chart_comparacion_equipos(sub: pd.DataFrame, titulo: str, ronda=None):
    """Barra de los 7 equipos en una ronda. Sin línea de promedio (regla: toda la industria a la vez = limpio)."""
    ronda = ronda or ronda_ultima
    d = sub[sub['Ronda'] == ronda].copy()
    d['Valor'] = num(d['Valor'])
    d = d.dropna(subset=['Valor']).sort_values('Valor', ascending=False)
    if d.empty:
        st.info('No hay datos numéricos para esta selección.')
        return
    fig = px.bar(d, x='Empresa', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                 title=f'{titulo} — {ronda}', text_auto='.2s')
    fig.update_traces(showlegend=False, textposition='outside', cliponaxis=False)
    mostrar(fig, ocultar_eje_valores='y')


def chart_evolucion(sub: pd.DataFrame, titulo: str):
    """Evolución histórica multi-ronda — acá SÍ va la línea de promedio industria (excepción de la regla)."""
    ev = sub.copy()
    ev['Valor'] = num(ev['Valor'])
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
    promedio_x_ronda = ev.groupby('Ronda_Orden').agg(Ronda=('Ronda', 'first'), Valor=('Valor', 'mean')).sort_index()
    if len(promedio_x_ronda) > 0:
        fig.add_trace(go.Scatter(x=promedio_x_ronda['Ronda'], y=promedio_x_ronda['Valor'], mode='lines',
                                  name='Promedio industria', line=dict(color=COLOR_REF_LINE, width=1.5, dash='dash')))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)


def valor_de(sub_df, estado=None, pais=None, seccion_f=None, subgrupo=None, metrica=None, empresa=None, ronda=None):
    d = sub_df
    if estado is not None:
        d = d[d['Estado'] == estado]
    if pais is not None:
        d = d[d['Pais'] == pais]
    if seccion_f is not None:
        d = d[d['Seccion'] == seccion_f]
    if subgrupo is not None:
        d = d[d['Subgrupo'] == subgrupo]
    if metrica is not None:
        d = d[d['Metrica'] == metrica]
    if empresa is not None:
        d = d[d['Empresa'] == empresa]
    if ronda is not None:
        d = d[d['Ronda'] == ronda]
    if d.empty:
        return None
    v = pd.to_numeric(d['Valor'].iloc[0], errors='coerce')
    return None if pd.isna(v) else v


def valores_industria(sub_df, metrica, estado=None, ronda=None):
    return {emp: valor_de(sub_df, estado=estado, metrica=metrica, empresa=emp, ronda=ronda) for emp in COMPANIES}


# =================================================================
# SECCIÓN 1 — EL RESULTADO (una sola pantalla)
# =================================================================
def seccion_resultado():
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)].copy()
    val_ronda['Valor'] = num(val_ronda['Valor'])
    cv_metric = 'Valor total creado'
    cv_ronda = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == cv_metric) & (df['Ronda'] == ronda_snapshot)].copy()
    cv_ronda['Valor'] = num(cv_ronda['Valor'])
    cv_vals = cv_ronda.groupby('Empresa')['Valor'].sum().to_dict()
    prom_cv = np.nanmean(list(cv_vals.values())) if cv_vals else None
    cap_vals = valores_industria(val_ronda, 'Capitalización de mercado, miles USD')
    prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None

    st.subheader('KPIs')
    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta_delta('Creación de valor', cv_vals.get(empresa_analisis), prom_cv)
    with c2:
        ranking_orden = sorted(cv_vals, key=cv_vals.get, reverse=True) if cv_vals else []
        posicion = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else None
        st.metric('Posición (creación de valor)', f'{posicion}° de {len(ranking_orden)}' if posicion else '—')
    with c3:
        tarjeta_delta('Capitalización de mercado', cap_vals.get(empresa_analisis), prom_cap)

    st.divider()
    st.subheader('Puente de valor y ranking')
    col_a, col_b = st.columns(2)

    with col_a:
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') &
                (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]

        def g(metrica):
            r = pl[pl['Metrica'] == metrica]['Valor']
            return pd.to_numeric(r.iloc[0], errors='coerce') if len(r) else 0.0

        ingresos = g('Ingresos por ventas')
        costos_produccion = g('Costos de fabricación interna') + g('Costos de la característica') + g('Costos de fabricación contratada')
        costos_com_admin = g('Costos de transporte y aranceles') + g('I+D') + g('Promoción') + g('Administración')
        depreciacion = g('Depreciación de Activos Fijos')
        intereses = g('Gastos financieros netos')
        impuestos = g('Impuesto sobre el beneficio')
        beneficio = g('Beneficio de la ronda')

        if ingresos == 0:
            st.info('No hay datos de cuenta de resultados para esta combinación de equipo/ronda.')
        else:
            fig = go.Figure(go.Waterfall(
                orientation='v',
                measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Ingresos', 'Costos de\nproducción', 'Costos\ncomerc. y admin.', 'Depreciación', 'Intereses', 'Impuestos', 'Beneficio neto'],
                y=[ingresos, -costos_produccion, -costos_com_admin, -depreciacion, -intereses, -impuestos, beneficio],
                text=[f'{v:,.0f}' for v in [ingresos, -costos_produccion, -costos_com_admin, -depreciacion, -intereses, -impuestos, beneficio]],
                textposition='outside',
                decreasing={'marker': {'color': '#B7B9C6'}},
                increasing={'marker': {'color': BRAND_ACCENT}},
                totals={'marker': {'color': COLOR_TOTAL_BAR}},
                connector={'line': {'color': COLOR_REF_LINE}},
            ))
            fig.update_layout(title=f'Puente de valor — {empresa_analisis}, {ronda_snapshot}')
            mostrar(fig, ocultar_eje_valores='y')

    with col_b:
        ranking = cv_ronda.groupby('Empresa')['Valor'].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa',
                     color_discrete_map=COLOR_MAP, text=ranking['Valor'].apply(lambda v: f'{v:,.0f}'),
                     title=f'Ranking de creación de valor — {ronda_snapshot}')
        fig.update_traces(textposition='outside', showlegend=False, cliponaxis=False)
        fig.update_layout(yaxis=dict(categoryorder='total ascending'),
                           xaxis=dict(range=[0, ranking['Valor'].max() * 1.2]))
        mostrar(fig, ocultar_eje_valores='x')

    st.divider()
    st.subheader('Evolución histórica')
    col_c, col_d = st.columns(2)
    with col_c:
        cv_all = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == cv_metric)].copy()
        cv_all['Valor'] = num(cv_all['Valor'])
        puestos = (cv_all.groupby(['Ronda', 'Ronda_Orden', 'Empresa'])['Valor'].sum().reset_index()
                   .sort_values(['Ronda_Orden', 'Valor'], ascending=[True, False]))
        puestos['Puesto'] = puestos.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
        cadiz_puesto = puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden')
        fig2 = px.line(cadiz_puesto, x='Ronda', y='Puesto', markers=True, title=f'Puesto de {empresa_analisis} por ronda')
        fig2.update_yaxes(autorange='reversed', dtick=1)
        fig2.update_traces(line=dict(color=BRAND_ACCENT, width=4))
        mostrar(fig2)
    with col_d:
        cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')]
        chart_evolucion(cap_sub, 'Capitalización de mercado (Global)')


# =================================================================
# SECCIÓN 2 — MERCADO (una sola pantalla)
# =================================================================
def seccion_mercado():
    tecnologias = ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno']
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('País', ['EE.UU.', 'China', 'Europa'], key='pais_mercado')
    tech_sel = c2.selectbox('Tecnología', tecnologias, key='tech_mercado')
    st.caption('Dispersión de los 7 equipos — dónde se ubica cada uno frente al resto de la industria.')

    estado_pais = f'Informe de mercado, {pais_sel}'
    sub = df[(df['Estado'] == estado_pais) & (df['Seccion'] == tech_sel) & (df['Ronda'] == ronda_snapshot)]
    share = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') &
               (df['Metrica'] == tech_sel) & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].rename(columns={'Valor': 'Share'})
    share['Share'] = num(share['Share'])

    def scatter_posicionamiento(eje_x_metrica, eje_x_label):
        eje_x = sub[sub['Metrica'] == eje_x_metrica][['Empresa', 'Valor']].rename(columns={'Valor': eje_x_label})
        pos = eje_x.merge(share, on='Empresa', how='inner')
        pos[eje_x_label] = num(pos[eje_x_label])
        pos = pos.dropna(subset=[eje_x_label, 'Share'])
        pos = pos[pos['Share'] > 0]
        if pos.empty:
            st.info(f'Ningún equipo tiene cuota de mercado en {tech_sel} — {pais_sel} — {ronda_snapshot}.')
            return
        fig = px.scatter(pos, x=eje_x_label, y='Share', color='Empresa', color_discrete_map=COLOR_MAP,
                          size=pos['Share'].abs(), text='Empresa',
                          title=f'{eje_x_label} vs. Cuota de mercado — {tech_sel}, {pais_sel}, {ronda_snapshot}')
        fig.update_traces(textposition='top center', showlegend=False)
        fig.update_layout(yaxis_title='Cuota de mercado, %')
        mostrar(fig)

    col_a, col_b = st.columns(2)
    with col_a:
        scatter_posicionamiento('Precio de venta, USD', 'Precio (USD)')
    with col_b:
        scatter_posicionamiento('Cantidad de características ofrecidas', 'Características ofrecidas')

    st.divider()
    st.subheader('Evolución de la cuota de mercado')
    st.caption(f'Inercia competitiva en {pais_sel} a lo largo de las rondas (cuota total del país, todas las tecnologías).')
    share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') &
                     (df['Metrica'] == 'Total')].copy()
    share_hist['Valor'] = num(share_hist['Valor'])
    share_hist = share_hist.dropna(subset=['Valor']).sort_values('Ronda_Orden')
    if share_hist.empty:
        st.info(f'Sin datos de cuota de mercado histórica para {pais_sel}.')
    else:
        fig = px.area(share_hist, x='Ronda', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                       groupnorm='percent', title=f'Cuota de mercado, % — {pais_sel}',
                       category_orders={'Ronda': share_hist.sort_values('Ronda_Orden')['Ronda'].unique().tolist()})
        fig.update_layout(yaxis_title='Cuota de mercado, %')
        mostrar(fig)


# =================================================================
# SECCIÓN 3 — OPERACIONES Y COSTOS (2 bloques)
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y costos', 'Inventario y logística'])
    tecnologias = ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno']

    with bloque1:
        st.subheader('Capacidad instalada')
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') &
                  (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) &
                  (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        cap = cap.dropna(subset=['Valor'])
        if cap.empty:
            st.info('Sin datos de capacidad instalada para esta combinación.')
        else:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                with col:
                    fig = go.Figure(go.Indicator(
                        mode='gauge+number', value=row['Valor'],
                        title={'text': f"{row['Subgrupo']} ({row['Metrica']})"},
                        gauge={'axis': {'range': [0, 100]},
                               'bar': {'color': BRAND_ACCENT},
                               'steps': [{'range': [0, 70], 'color': COLOR_GAUGE_BG1},
                                         {'range': [70, 100], 'color': COLOR_GAUGE_BG2}]}))
                    fig.update_layout(height=260, margin=dict(t=60, b=10))
                    mostrar(fig)

        st.divider()
        st.subheader('Estructura de costos')
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') &
                (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]

        def g(metrica):
            r = pl[pl['Metrica'] == metrica]['Valor']
            return pd.to_numeric(r.iloc[0], errors='coerce') if len(r) else 0.0

        ingresos = g('Ingresos por ventas')
        etapas = [('Ingresos', ingresos), ('- Fabricación interna', ingresos - g('Costos de fabricación interna'))]
        etapas.append(('- Característica', etapas[-1][1] - g('Costos de la característica')))
        etapas.append(('- Fabricación contratada', etapas[-1][1] - g('Costos de fabricación contratada')))
        etapas.append(('- Transporte y aranceles', etapas[-1][1] - g('Costos de transporte y aranceles')))
        etapas.append(('- I+D, Promoción, Admin.', etapas[-1][1] - g('I+D') - g('Promoción') - g('Administración')))
        etapas.append(('= EBITDA', etapas[-1][1]))

        if ingresos == 0:
            st.info('No hay datos de cuenta de resultados para esta combinación.')
        else:
            labels = [e[0] for e in etapas]
            valores = [e[1] for e in etapas]
            fig = go.Figure(go.Funnel(
                y=labels, x=valores, textposition='inside', textinfo='value+percent initial',
                marker={'color': [COLOR_TOTAL_BAR] + [MUTED_PALETTE[i % len(MUTED_PALETTE)] for i in range(len(labels) - 2)] + [BRAND_ACCENT]}))
            fig.update_layout(title=f'Estructura de costos (funnel) — {empresa_analisis}, {ronda_snapshot}', height=460)
            mostrar(fig, ocultar_eje_valores='x')

        st.divider()
        st.subheader('Rentabilidad por unidad (unit economics)')
        c3, c4 = st.columns(2)
        pais_ue = c3.selectbox('País', ['EE.UU.', 'China', 'Europa'], key='pais_unit_econ')
        tech_ue = c4.selectbox('Tecnología', tecnologias, key='tech_unit_econ')
        estado_margen = f'Desglose de margen por tec, miles USD, {pais_ue}'
        margen = df[(df['Estado'] == estado_margen) & (df['Seccion'] == tech_ue) &
                    (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_de(df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Ronda'] == ronda_snapshot)],
                             seccion_f=tech_ue, metrica='Ventas, miles unidades', empresa=empresa_analisis)

        def gm(metrica):
            r = margen[margen['Metrica'] == metrica]['Valor']
            return pd.to_numeric(r.iloc[0], errors='coerce') if len(r) else 0.0

        if not unidades or unidades <= 0:
            st.info(f'{empresa_analisis} no vendió {tech_ue} en {pais_ue} en {ronda_snapshot}.')
        else:
            segmentos = [
                ('Precio de venta', gm('Ingresos por ventas') / unidades),
                ('Fabricación propia/contrato', -gm('Fabricación propia y por contrato') / unidades),
                ('Productos importados', -gm('Costo de los productos importados') / unidades),
                ('Transporte y aranceles', -gm('Transporte y aranceles') / unidades),
                ('Característica', -gm('Costos de la característica') / unidades),
            ]
            segmentos = [s for s in segmentos if abs(s[1]) > 0.01]
            colores_seg = [BRAND_ACCENT] + [MUTED_PALETTE[i % len(MUTED_PALETTE)] for i in range(len(segmentos) - 1)]
            fig = go.Figure()
            for (nombre, val_seg), color in zip(segmentos, colores_seg):
                fig.add_trace(go.Bar(x=['Por unidad, USD'], y=[val_seg], name=nombre,
                                      marker_color=color, text=f'{val_seg:,.0f}', textposition='inside'))
            margen_bruto_unit = gm('Beneficio bruto') / unidades
            fig.update_layout(barmode='relative', title=f'Margen real por vehículo — {empresa_analisis}, {tech_ue}, {pais_ue}, {ronda_snapshot}')
            mostrar(fig)
            st.caption(f'Margen bruto por unidad: **{margen_bruto_unit:,.0f} USD**')

    with bloque2:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('País', ['EE.UU.', 'China', 'Europa'], key='pais_inventario')
        tech_sel = c2.selectbox('Tecnología', tecnologias, key='tech_inventario')

        st.subheader('Puente de inventario')
        log = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) &
                 (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Subgrupo'] == pais_sel) &
                 (df['Ronda'] == ronda_snapshot)].copy()
        log['Valor'] = num(log['Valor'])
        d = log.set_index('Metrica')['Valor']

        if d.empty:
            st.info('Sin datos de logística para esta combinación.')
        else:
            inv_inicial = d.get('Inventario inicial', 0) or 0
            produccion = (d.get('Producción interna', 0) or 0) + (d.get('Producción contratada', 0) or 0)
            importado = sum(v for k, v in d.items() if k.startswith('Importado desde') and v)
            ventas = abs(d.get(f'Ventas en {pais_sel}', 0) or 0)
            exportado = sum(abs(v) for k, v in d.items() if k.startswith('Exportado a') and v)
            inv_final = d.get('Inventario final', 0) or 0
            demanda_insat = d.get('Demanda insatisfecha', 0) or 0

            entradas = [e for e in [('+ Producción', produccion), ('+ Importado', importado)] if e[1]]
            salidas = [e for e in [('- Ventas', -ventas), ('- Exportado', -exportado)] if e[1]]
            etapas = [('Inventario inicial', inv_inicial)] + entradas + salidas + [('= Inventario final', inv_final)]
            fig = go.Figure(go.Waterfall(
                orientation='v',
                measure=['absolute'] + ['relative'] * (len(etapas) - 2) + ['total'],
                x=[e[0] for e in etapas], y=[e[1] for e in etapas],
                text=[f'{e[1]:,.0f}' for e in etapas], textposition='outside',
                decreasing={'marker': {'color': '#B7B9C6'}},
                increasing={'marker': {'color': BRAND_ACCENT}},
                totals={'marker': {'color': COLOR_TOTAL_BAR}},
                connector={'line': {'color': COLOR_REF_LINE}},
            ))
            fig.update_layout(title=f'Puente de inventario — {empresa_analisis}, {tech_sel}, {pais_sel}, {ronda_snapshot}')
            mostrar(fig, ocultar_eje_valores='y')

            if demanda_insat:
                ratios_r = df[(df['Estado'] == 'Ratios e indicadores financieros clave') &
                              (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)].copy()
                ratios_r['Valor'] = num(ratios_r['Valor'])
                margen_pct = valor_de(ratios_r, metrica='Margen bruto')
                precio_venta = valor_de(df[(df['Estado'] == f'Informe de mercado, {pais_sel}') & (df['Ronda'] == ronda_snapshot)],
                                         seccion_f=tech_sel, metrica='Precio de venta, USD', empresa=empresa_analisis)
                if margen_pct is not None and precio_venta is not None:
                    margen_unitario = precio_venta * (margen_pct / 100)
                    perdida = demanda_insat * margen_unitario
                    st.warning(f'**Margen bruto perdido por falta de stock (estimado):** {perdida:,.0f} miles USD '
                               f'({demanda_insat:,.0f} unidades × {margen_unitario:,.0f} USD de margen unitario estimado)')
                else:
                    st.info(f'Demanda insatisfecha: {demanda_insat:,.0f} unidades (no se pudo estimar el margen perdido: falta precio o margen bruto).')

        st.divider()
        st.subheader('Matriz térmica de logística')
        st.caption('Origen → Destino, en unidades. "Subcontratado" prorratea la mezcla interna/contratada de cada '
                   'planta proporcionalmente a sus destinos reales — Cesim no distingue qué unidad específica '
                   'despachada era interna o contratada, así que es una estimación, no un dato exacto.')

        log_tech = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) &
                      (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Ronda'] == ronda_snapshot)].copy()
        log_tech['Valor'] = num(log_tech['Valor'])

        def val(planta, metrica):
            r = log_tech[(log_tech['Subgrupo'] == planta) & (log_tech['Metrica'] == metrica)]['Valor']
            return abs(r.iloc[0]) if len(r) and pd.notna(r.iloc[0]) else 0.0

        destinos = ['EE.UU.', 'China', 'Europa']
        filas_heat = ['EE.UU. (interna)', 'China (interna)', 'Subcontratado']
        matriz = pd.DataFrame(0.0, index=filas_heat, columns=destinos)

        for planta in ['EE.UU.', 'China']:
            interna = val(planta, 'Producción interna')
            contratada = val(planta, 'Producción contratada')
            total_prod = interna + contratada
            flows = {d: val(planta, f'Ventas en {planta}' if d == planta else f'Exportado a {d}') for d in destinos}
            total_flow = sum(flows.values())
            if total_prod == 0 or total_flow == 0:
                continue
            share_interna = interna / total_prod
            share_contratada = contratada / total_prod
            fila_interna = 'EE.UU. (interna)' if planta == 'EE.UU.' else 'China (interna)'
            for d in destinos:
                matriz.loc[fila_interna, d] += flows[d] * share_interna
                matriz.loc['Subcontratado', d] += flows[d] * share_contratada

        if matriz.sum().sum() == 0:
            st.info(f'{empresa_analisis} no tiene flujos de {tech_sel} para mostrar en {ronda_snapshot}.')
        else:
            fig = px.imshow(matriz.values, x=destinos, y=filas_heat, text_auto='.0f', aspect='auto',
                             color_continuous_scale=[[0, COLOR_GAUGE_BG1], [1, BRAND_ACCENT]],
                             labels=dict(x='Destino', y='Origen', color='Unidades'))
            fig.update_layout(title=f'Origen → Destino — {empresa_analisis}, {tech_sel}, {ronda_snapshot}', height=350)
            fig.update_coloraxes(showscale=False)
            mostrar(fig)


# =================================================================
# SECCIÓN 4 — FINANZAS (una sola pantalla)
# =================================================================
def seccion_finanzas():
    pl_ronda = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Ronda'] == ronda_snapshot)].copy()
    pl_ronda['Valor'] = num(pl_ronda['Valor'])
    ratios_ronda = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)].copy()
    ratios_ronda['Valor'] = num(ratios_ronda['Valor'])
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)].copy()
    val_ronda['Valor'] = num(val_ronda['Valor'])

    def wacc_por_empresa(empresa):
        de = valor_de(val_ronda, metrica='Deuda a patrimonio', empresa=empresa)
        re_ = valor_de(val_ronda, metrica='Rendimiento esperado del patrimonio, %', empresa=empresa)
        rd = valor_de(val_ronda, metrica='Costo de la deuda después de impuestos, %', empresa=empresa)
        if de is None or re_ is None or rd is None:
            return None
        e_w = 1 / (1 + de)
        d_w = de / (1 + de)
        return e_w * re_ + d_w * rd

    ejes_data = {
        'EBITDA': {emp: valor_de(pl_ronda, metrica='Beneficio operativo antes de depreciación (EBITDA)', empresa=emp) for emp in COMPANIES},
        'Margen bruto, %': {emp: valor_de(ratios_ronda, metrica='Margen bruto', empresa=emp) for emp in COMPANIES},
        'ROS, %': {emp: valor_de(ratios_ronda, metrica='Rentabilidad de las ventas (ROS)', empresa=emp) for emp in COMPANIES},
        'ROE, %': {emp: valor_de(ratios_ronda, metrica='Rendimiento de los Fondos Propios (ROE)', empresa=emp) for emp in COMPANIES},
        'Apalancamiento': {emp: valor_de(ratios_ronda, metrica='Endeudamiento neto/patrimonio (apalancamiento)', empresa=emp) for emp in COMPANIES},
        'WACC, %': {emp: wacc_por_empresa(emp) for emp in COMPANIES},
    }

    st.subheader('Tarjetas de desempeño')
    st.caption(f'{empresa_analisis} — {ronda_snapshot}. Delta = variación % contra el promedio de los 7 equipos.')
    cols = st.columns(3)
    formatos = {'EBITDA': ',.0f', 'Margen bruto, %': '.1f', 'ROS, %': '.1f', 'ROE, %': '.1f',
                'Apalancamiento': '.1f', 'WACC, %': '.1f'}
    for i, (nombre, vals) in enumerate(ejes_data.items()):
        validos = [v for v in vals.values() if v is not None]
        if not validos:
            continue
        promedio = np.nanmean(validos)
        with cols[i % 3]:
            tarjeta_delta(nombre, vals.get(empresa_analisis), promedio, fmt=formatos.get(nombre, ',.1f'))

    st.divider()
    st.subheader(f'{empresa_analisis} vs. rango de la industria')
    st.caption('Cada pista muestra el mínimo y máximo de los 7 equipos, la mediana (gris), y dónde está CADIZ (verde).')
    ejes_validos = {k: v for k, v in ejes_data.items() if len([x for x in v.values() if x is not None]) >= 2}
    if not ejes_validos:
        st.info('Sin datos suficientes para el gráfico de rango en esta ronda.')
    else:
        n = len(ejes_validos)
        fig = go.Figure()
        for i, (nombre, vals) in enumerate(ejes_validos.items()):
            valores = sorted(v for v in vals.values() if v is not None)
            v_min, v_max, v_med = valores[0], valores[-1], np.median(valores)
            v_cadiz = vals.get(empresa_analisis)
            rango = (v_max - v_min) or 1
            pos = lambda x: (x - v_min) / rango * 100
            fig.add_trace(go.Scatter(x=[0, 100], y=[i, i], mode='lines',
                                      line=dict(color='#B7B9C6', width=8), showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=[pos(v_med)], y=[i], mode='markers',
                                      marker=dict(symbol='line-ns', size=16, color='#5C5F6E', line_width=3),
                                      showlegend=False, hovertemplate=f'Mediana: {v_med:,.1f}<extra></extra>'))
            if v_cadiz is not None:
                fig.add_trace(go.Scatter(x=[pos(v_cadiz)], y=[i], mode='markers',
                                          marker=dict(size=18, color=BRAND_ACCENT, line=dict(color=COLOR_TOTAL_BAR, width=1.5)),
                                          showlegend=False, hovertemplate=f'{empresa_analisis}: {v_cadiz:,.1f}<extra></extra>'))
            fig.add_annotation(x=0, y=i, text=f'{v_min:,.1f}', showarrow=False, xshift=-28, font=dict(size=10, color=COLOR_REF_LINE))
            fig.add_annotation(x=100, y=i, text=f'{v_max:,.1f}', showarrow=False, xshift=28, font=dict(size=10, color=COLOR_REF_LINE))
        fig.update_layout(
            yaxis=dict(tickmode='array', tickvals=list(range(n)), ticktext=list(ejes_validos.keys()), range=[-0.7, n - 0.3]),
            xaxis=dict(range=[-8, 108]), height=110 + n * 55, title=f'Rango de industria — {ronda_snapshot}')
        mostrar(fig, ocultar_eje_valores='x')

    st.divider()
    st.subheader('Riesgo vs. retorno y tendencia')
    col_a, col_b = st.columns(2)
    with col_a:
        apal_vals = ejes_data['Apalancamiento']
        roe_vals = ejes_data['ROE, %']
        rr = pd.DataFrame({'Empresa': COMPANIES,
                            'Apalancamiento': [apal_vals.get(e) for e in COMPANIES],
                            'ROE': [roe_vals.get(e) for e in COMPANIES]}).dropna()
        if len(rr) < 2:
            st.info('Sin datos suficientes de apalancamiento/ROE para esta ronda.')
        else:
            fig = px.scatter(rr, x='Apalancamiento', y='ROE', color='Empresa', color_discrete_map=COLOR_MAP,
                              text='Empresa', title=f'Apalancamiento vs. ROE — {ronda_snapshot}')
            fig.update_traces(marker=dict(size=14), textposition='top center', showlegend=False)
            mostrar(fig)
    with col_b:
        ben = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Metrica'] == 'Beneficio de la ronda')]
        chart_evolucion(ben, 'Beneficio de la ronda (Global)')


# =================================================================
# SECCIÓN 5 — RRHH Y SOSTENIBILIDAD (una sola pantalla)
# =================================================================
def seccion_rrhh_sostenibilidad():
    st.subheader('Salarios vs. rotación')
    rrhh = df[(df['Estado'] == 'Informe de RRHH') & (df['Empresa'] == empresa_analisis)].copy()
    rrhh['Valor'] = num(rrhh['Valor'])
    salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
    rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
    if salario.empty and rotacion.empty:
        st.info('Sin datos de RRHH para este equipo.')
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario mensual, USD',
                                  line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
        fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación de personal, %',
                                  line=dict(color=COLOR_TEXT, width=3, dash='dot'), yaxis='y2'))
        fig.update_layout(
            title=f'Salario vs. rotación — {empresa_analisis}',
            yaxis=dict(title='Salario mensual, USD'),
            yaxis2=dict(title='Rotación, %', overlaying='y', side='right'))
        mostrar(fig)

    st.divider()
    st.subheader('KPIs ambientales')
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_ambiental')
    indicadores = {
        'Emisiones de CO2': 'Total, toneladas métricas',
        'Consumo de energía': 'Total, MWh',
        'Consumo de agua': 'Total, miles de m3',
    }
    sub_sel = c2.selectbox('Indicador', list(indicadores.keys()), key='indicador_ambiental')
    metrica_real = indicadores[sub_sel]
    sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_sel}') &
                 (df['Metrica'] == metrica_real) & (df['Ronda'] == ronda_snapshot)]
    chart_comparacion_equipos(sub_amb, f'{sub_sel} ({metrica_real}) — {pais_sel}', ronda=ronda_snapshot)

    st.divider()
    st.subheader('Sensibilidad regional a ESG')
    st.caption('Cruza el puntaje ESG de los 7 equipos contra su cuota de mercado en cada región, en la ronda seleccionada.')
    esg = df[(df['Estado'] == 'Informe ESG') & (df['Subgrupo'] == 'Puntuación final') &
             (df['Metrica'] == 'Reputación ESG') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
    esg = esg.rename(columns={'Valor': 'ESG'})
    esg['ESG'] = num(esg['ESG'])

    cols = st.columns(3)
    for col, pais_sel in zip(cols, ['EE.UU.', 'China', 'Europa']):
        with col:
            mkt = df[(df['Estado'] == f'Informe de mercado, {pais_sel}') &
                     (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') &
                     (df['Metrica'] == 'Total') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
            mkt = mkt.rename(columns={'Valor': 'Cuota_mercado'})
            mkt['Cuota_mercado'] = num(mkt['Cuota_mercado'])
            d = esg.merge(mkt, on='Empresa', how='inner').dropna()
            if len(d) < 2:
                st.info(f'Sin datos suficientes en {pais_sel}.')
                continue
            fig = px.scatter(d, x='ESG', y='Cuota_mercado', color='Empresa', color_discrete_map=COLOR_MAP,
                              text='Empresa', title=f'{pais_sel} — Cuota de mercado, %',
                              trendline='ols' if len(d) > 2 else None)
            fig.update_traces(showlegend=False, textposition='top center')
            fig.update_layout(height=350)
            mostrar(fig)


# ---------------- Router ----------------
st.title(seccion)

if seccion == '1. El Resultado':
    seccion_resultado()
elif seccion == '2. El Frente de Batalla (Mercado)':
    seccion_mercado()
elif seccion == '3. La Sala de Máquinas (Operaciones)':
    seccion_operaciones()
elif seccion == '4. La Salud del Negocio (Finanzas)':
    seccion_finanzas()
elif seccion == '5. El Largo Plazo (RRHH y Sostenibilidad)':
    seccion_rrhh_sostenibilidad()
