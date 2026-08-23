"""
app.py — Tablero de Control Directivo, Grupo CADIZ (Cesim Global Automotive)
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

# --- IDENTIDAD CÁDIZ AUTOMOTIVE ---
MY_COMPANY = 'CADIZ'
COMPANIES = ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CUORE', 'FOCUS', 'TOKIO']
BRAND_ACCENT = '#B3261E'       # Rojo CÁDIZ (Identidad / Costos)
BRAND_DARK = '#1A1714'         # Negro Grafito
BRAND_LIGHT = '#F5F2ED'        # Crema (Ingresos / Positivo)
MUTED_PALETTE = ['#A1A1AA', '#71717A', '#52525B', '#3F3F46', '#27272A', '#D4D4D8'] # Grises

COLOR_MAP = {MY_COMPANY: BRAND_ACCENT}
for i, c in enumerate([c for c in COMPANIES if c != MY_COMPANY]):
    COLOR_MAP[c] = MUTED_PALETTE[i % len(MUTED_PALETTE)]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

st.set_page_config(page_title='CÁDIZ | Tablero Directivo', layout='wide')

# ---------------- Carga de datos ----------------
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

def get_data() -> pd.DataFrame:
    xls_files = sorted(glob.glob(f'{DATA_DIR}/*.xls') + glob.glob(f'{DATA_DIR}/*.XLS'))
    if not xls_files:
        st.warning(f'No se encontraron archivos .xls en {DATA_DIR}/. Subí al menos una ronda.')
        st.stop()
    return cargar_historico(tuple(xls_files))

def num(series):
    return pd.to_numeric(series, errors='coerce')

df_all = get_data()

# ---------------- Sidebar: filtros globales ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')

filtro_tipo = st.sidebar.radio('Rondas a incluir', ['Todas', 'Solo oficiales', 'Solo prácticas'], horizontal=False)
if filtro_tipo == 'Solo oficiales': df = df_all[df_all['Tipo_Ronda'] == 'Oficial'].copy()
elif filtro_tipo == 'Solo prácticas': df = df_all[df_all['Tipo_Ronda'] == 'Práctica'].copy()
else: df = df_all.copy()

if df.empty:
    st.warning('No hay rondas para ese filtro.')
    st.stop()

rondas_disponibles = df[['Ronda', 'Ronda_Orden']].drop_duplicates().sort_values('Ronda_Orden')['Ronda'].tolist()
ronda_ultima = rondas_disponibles[-1]

st.sidebar.caption(f"{len(rondas_disponibles)} ronda(s): {', '.join(rondas_disponibles)}")
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_disponibles, value=ronda_ultima)
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0)

st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True)

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
COLOR_TEXT = BRAND_LIGHT if modo_oscuro else BRAND_DARK
COLOR_REF_LINE = 'rgba(255,255,255,0.25)' if modo_oscuro else 'rgba(0,0,0,0.25)'

# Paleta funcional semántica (Evitar rojo para ingresos)
COLOR_POSITIVE = BRAND_LIGHT if modo_oscuro else '#D4D4D8'
COLOR_NEGATIVE = BRAND_ACCENT

try:
    st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Falta el archivo style.css en la carpeta assets.")

def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    fig.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=COLOR_TEXT, family='JetBrains Mono, monospace'),
                       title_font=dict(family='Oswald, sans-serif', size=16))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    
    if ocultar_eje_valores == 'y': fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x': fig.update_xaxes(showticklabels=False, title=None)
    
    if en_card:
        with st.container(border=True):
            st.plotly_chart(fig, use_container_width=True, **kwargs)
    else:
        st.plotly_chart(fig, use_container_width=True, **kwargs)

def linea_media(fig, valor, eje='y', etiqueta='Promedio'):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)): return
    kwargs = dict(line_dash='dash', line_color=COLOR_REF_LINE, line_width=1,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color=COLOR_REF_LINE)
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)

def tarjeta_delta(label, valor, promedio, fmt=',.0f', sufijo=''):
    if valor is None:
        st.metric(label, '—')
        return
    delta = None
    if promedio not in (None, 0) and not (isinstance(promedio, float) and np.isnan(promedio)):
        delta = (valor - promedio) / promedio * 100
    st.metric(label, f'{valor:{fmt}}{sufijo}', delta=f'{delta:+.1f}% vs. Prom' if delta is not None else None)

def format_num(val):
    """Acorta números grandes para evitar saturación visual."""
    if val is None or pd.isna(val): return ""
    if abs(val) >= 1_000_000: return f"{val/1_000_000:,.1f}M"
    if abs(val) >= 1_000: return f"{val/1_000:,.0f}k"
    return f"{val:,.0f}"

def chart_comparacion_equipos(sub: pd.DataFrame, titulo: str, ronda=None):
    ronda = ronda or ronda_ultima
    d = sub[sub['Ronda'] == ronda].copy()
    d['Valor'] = num(d['Valor'])
    d = d.dropna(subset=['Valor']).sort_values('Valor', ascending=False)
    if d.empty: return st.info('Sin datos numéricos.')
    fig = px.bar(d, x='Empresa', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP, title=f'{titulo} — {ronda}')
    fig.update_traces(text=d['Valor'].apply(format_num), textposition='outside', cliponaxis=False, showlegend=False)
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
        fig.add_trace(go.Scatter(x=promedio_x_ronda['Ronda'], y=promedio_x_ronda['Valor'], mode='lines',
                                  name='Promedio', line=dict(color=COLOR_REF_LINE, width=1, dash='dash')))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)

def valor_de(sub_df, estado=None, pais=None, seccion_f=None, subgrupo=None, metrica=None, empresa=None, ronda=None):
    d = sub_df
    if estado: d = d[d['Estado'] == estado]
    if pais: d = d[d['Pais'] == pais]
    if seccion_f: d = d[d['Seccion'] == seccion_f]
    if subgrupo: d = d[d['Subgrupo'] == subgrupo]
    if metrica: d = d[d['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    if ronda: d = d[d['Ronda'] == ronda]
    if d.empty: return None
    v = pd.to_numeric(d['Valor'].iloc[0], errors='coerce')
    return None if pd.isna(v) else v

def valores_industria(sub_df, metrica, estado=None, ronda=None):
    return {emp: valor_de(sub_df, estado=estado, metrica=metrica, empresa=emp, ronda=ronda) for emp in COMPANIES}

def valor_fuzzy(sub_df, keyword):
    """Busca métricas parcialmente para atrapar diferencias de formato de Cesim (ej. Ventas en China)."""
    d = sub_df[sub_df['Metrica'].str.contains(keyword, case=False, na=False)]
    if d.empty: return None
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce')

# =================================================================
# SECCIÓN 1 — EL RESULTADO
# =================================================================
def seccion_resultado():
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)].copy()
    cv_ronda = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == 'Valor total creado') & (df['Ronda'] == ronda_snapshot)].copy()
    cv_vals = {emp: num(cv_ronda[cv_ronda['Empresa'] == emp]['Valor']).sum() for emp in COMPANIES if not cv_ronda[cv_ronda['Empresa'] == emp].empty}
    prom_cv = np.nanmean(list(cv_vals.values())) if cv_vals else None
    cap_vals = valores_industria(val_ronda, 'Capitalización de mercado, miles USD')
    prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None

    st.subheader('KPIs')
    c1, c2, c3 = st.columns(3)
    with c1: tarjeta_delta('Creación de valor', cv_vals.get(empresa_analisis), prom_cv)
    with c2:
        ranking_orden = sorted(cv_vals, key=cv_vals.get, reverse=True) if cv_vals else []
        pos = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else None
        st.metric('Posición', f'{pos}° de {len(ranking_orden)}' if pos else '—')
    with c3: tarjeta_delta('Market Cap', cap_vals.get(empresa_analisis), prom_cap)

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def g(metrica): return pd.to_numeric(pl[pl['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not pl[pl['Metrica'] == metrica].empty else 0.0
        
        ingresos = g('Ingresos por ventas')
        costos_prod = g('Costos de fabricación interna') + g('Costos de la característica') + g('Costos de fabricación contratada')
        costos_op = g('Costos de transporte y aranceles') + g('I+D') + g('Promoción') + g('Administración')
        depr = g('Depreciación de Activos Fijos')
        ints = g('Gastos financieros netos')
        imp = g('Impuesto sobre el beneficio')
        ben = g('Beneficio de la ronda')

        if ingresos > 0:
            fig = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Ingresos', '- Prod', '- Op/Admin', '- Depr', '- Int', '- Imp', '= Neto'],
                y=[ingresos, -costos_prod, -costos_op, -depr, -ints, -imp, ben],
                text=[format_num(v) for v in [ingresos, -costos_prod, -costos_op, -depr, -ints, -imp, ben]], textposition='outside',
                decreasing={'marker': {'color': COLOR_NEGATIVE}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': COLOR_POSITIVE}}
            ))
            fig.update_layout(title=f'Puente de valor — {empresa_analisis}')
            mostrar(fig, ocultar_eje_valores='y')

    with col_b:
        if cv_vals:
            ranking = pd.DataFrame(list(cv_vals.items()), columns=['Empresa', 'Valor']).sort_values('Valor', ascending=True)
            fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa', color_discrete_map=COLOR_MAP)
            fig.update_traces(text=ranking['Valor'].apply(format_num), textposition='outside', cliponaxis=False, showlegend=False)
            fig.update_layout(title='Ranking de Creación de Valor', xaxis=dict(range=[0, ranking['Valor'].max() * 1.2]))
            mostrar(fig, ocultar_eje_valores='x')

    st.divider()
    col_c, col_d = st.columns(2)
    with col_c:
        cv_all = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == 'Valor total creado')].copy()
        cv_all['Valor'] = num(cv_all['Valor'])
        puestos = cv_all.groupby(['Ronda', 'Ronda_Orden', 'Empresa'])['Valor'].sum().reset_index().sort_values(['Ronda_Orden', 'Valor'], ascending=[True, False])
        puestos['Puesto'] = puestos.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
        cadiz_puesto = puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden')
        fig2 = px.line(cadiz_puesto, x='Ronda', y='Puesto', markers=True, title='Evolución Puesto CADIZ')
        fig2.update_yaxes(autorange='reversed', dtick=1)
        fig2.update_traces(line=dict(color=BRAND_ACCENT, width=3))
        mostrar(fig2)
    with col_d:
        cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')]
        chart_evolucion(cap_sub, 'Market Cap')

# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('País', ['EE.UU.', 'China', 'Europa'])
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

    estado_pais = f'Informe de mercado, {pais_sel}'
    sub = df[(df['Estado'] == estado_pais) & (df['Seccion'] == tech_sel) & (df['Ronda'] == ronda_snapshot)]
    
    # Arreglo Fuzzy para capturar ventas
    ventas_data = []
    for emp in COMPANIES:
        val = valor_fuzzy(sub[sub['Empresa'] == emp], 'Ventas')
        if val is not None: ventas_data.append({'Empresa': emp, 'Share': val}) # Usamos la venta absoluta como proxy de masa para el scatter
    share = pd.DataFrame(ventas_data)

    def scatter_posicionamiento(eje_x_metrica, eje_x_label):
        eje_x = sub[sub['Metrica'] == eje_x_metrica][['Empresa', 'Valor']].rename(columns={'Valor': eje_x_label})
        if share.empty or eje_x.empty: return None
        pos = eje_x.merge(share, on='Empresa', how='inner')
        pos[eje_x_label] = num(pos[eje_x_label])
        pos = pos.dropna()
        pos = pos[pos['Share'] > 0]
        if pos.empty: return None
        fig = px.scatter(pos, x=eje_x_label, y='Share', color='Empresa', color_discrete_map=COLOR_MAP, size=pos['Share'].abs(), text='Empresa', title=f'{eje_x_label} vs. Volumen')
        fig.update_traces(textposition='top center', showlegend=False)
        fig.update_layout(yaxis_title='Volumen Vendido')
        mostrar(fig)
        return True

    col_a, col_b = st.columns(2)
    with col_a: 
        if not scatter_posicionamiento('Precio de venta, USD', 'Precio'): st.info(f'Sin datos de {tech_sel} en {pais_sel}.')
    with col_b: 
        scatter_posicionamiento('Cantidad de características ofrecidas', 'Características')

    st.divider()
    share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') & (df['Metrica'] == 'Total')].copy()
    share_hist['Valor'] = num(share_hist['Valor'])
    share_hist = share_hist.dropna(subset=['Valor']).sort_values('Ronda_Orden')
    
    if not share_hist.empty:
        orden_empresas = [MY_COMPANY] + [c for c in COMPANIES if c != MY_COMPANY] # CADIZ como base sólida
        fig = px.area(share_hist, x='Ronda', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                      category_orders={'Empresa': orden_empresas}, groupnorm='percent', title=f'Evolución Share — {pais_sel}')
        fig.update_layout(yaxis_title='%')
        mostrar(fig)

# =================================================================
# SECCIÓN 3 — OPERACIONES Y COSTOS
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y costos', 'Inventario y logística'])

    with bloque1:
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') &
                 (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        cap = cap.dropna()
        if not cap.empty:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                with col:
                    fig = go.Figure(go.Indicator(mode='gauge+number', value=row['Valor'], title={'text': row['Subgrupo']},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': BRAND_ACCENT}, 'steps': [{'range': [0, 100], 'color': '#27272A'}]}))
                    fig.update_layout(height=220, margin=dict(t=40, b=10))
                    mostrar(fig)

        st.divider()
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def g(metrica): return pd.to_numeric(pl[pl['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not pl[pl['Metrica'] == metrica].empty else 0.0

        ingresos = g('Ingresos por ventas')
        if ingresos > 0:
            etapas = [('Ingresos', ingresos), ('- Fab. Interna', ingresos - g('Costos de fabricación interna'))]
            etapas.append(('- Caract.', etapas[-1][1] - g('Costos de la característica')))
            etapas.append(('- Fab. Contratada', etapas[-1][1] - g('Costos de fabricación contratada')))
            etapas.append(('- Logística', etapas[-1][1] - g('Costos de transporte y aranceles')))
            etapas.append(('- Op/Admin', etapas[-1][1] - g('I+D') - g('Promoción') - g('Administración')))
            etapas.append(('= EBITDA', etapas[-1][1]))
            
            fig = go.Figure(go.Funnel(y=[e[0] for e in etapas], x=[e[1] for e in etapas], textinfo='value+percent initial',
                                      marker={'color': [COLOR_POSITIVE] + [MUTED_PALETTE[i%len(MUTED_PALETTE)] for i in range(len(etapas)-2)] + [COLOR_POSITIVE]}))
            fig.update_layout(title='Estructura Macro de Costos (Funnel)')
            mostrar(fig, ocultar_eje_valores='x')

        st.divider()
        c3, c4 = st.columns(2)
        pais_ue = c3.selectbox('País Unit Econ', ['EE.UU.', 'China', 'Europa'])
        tech_ue = c4.selectbox('Tech Unit Econ', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])
        margen = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        
        # Fuzzy match para ventas
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, 'Ventas')

        def gm(metrica): return pd.to_numeric(margen[margen['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not margen[margen['Metrica'] == metrica].empty else 0.0

        if unidades and unidades > 0:
            p_venta = gm('Ingresos por ventas') / unidades
            c_prod = -gm('Fabricación propia y por contrato') / unidades
            c_flete = -gm('Transporte y aranceles') / unidades
            c_caract = -gm('Costos de la característica') / unidades
            m_bruto = gm('Beneficio bruto') / unidades

            fig_ue = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'total'],
                x=['Precio', '- Prod', '- Logística', '- Caract.', '= Margen'],
                y=[p_venta, c_prod, c_flete, c_caract, m_bruto],
                text=[format_num(v) for v in [p_venta, c_prod, c_flete, c_caract, m_bruto]], textposition='outside',
                decreasing={'marker': {'color': COLOR_NEGATIVE}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': COLOR_POSITIVE}}
            ))
            fig_ue.update_layout(title=f'Unit Economics (Waterfall) — {tech_ue} {pais_ue}')
            mostrar(fig_ue, ocultar_eje_valores='y')
        else:
            st.info('Sin ventas para calcular Unit Economics.')

    with bloque2:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('País Inventario', ['EE.UU.', 'China', 'Europa'])
        tech_sel = c2.selectbox('Tech Inventario', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

        log = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) &
                 (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Subgrupo'] == pais_sel) & (df['Ronda'] == ronda_snapshot)].copy()
        log['Valor'] = num(log['Valor'])
        d = log.set_index('Metrica')['Valor']

        if not d.empty:
            inv_ini = d.get('Inventario inicial', 0) or 0
            prod = (d.get('Producción interna', 0) or 0) + (d.get('Producción contratada', 0) or 0)
            imp = sum(v for k, v in d.items() if k.startswith('Importado desde') and pd.notna(v))
            ventas = abs(d.get(f'Ventas en {pais_sel}', 0) or 0)
            exp = sum(abs(v) for k, v in d.items() if k.startswith('Exportado a') and pd.notna(v))
            inv_fin = d.get('Inventario final', 0) or 0
            demanda_insat = d.get('Demanda insatisfecha', 0) or 0

            fig_inv = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Inv Inicial', '+ Prod', '+ Import', '- Ventas', '- Export', '= Inv Final'],
                y=[inv_ini, prod, imp, -ventas, -exp, inv_fin],
                text=[format_num(v) for v in [inv_ini, prod, imp, -ventas, -exp, inv_fin]], textposition='outside',
                decreasing={'marker': {'color': COLOR_NEGATIVE}}, increasing={'marker': {'color': COLOR_POSITIVE}},
                totals={'marker': {'color': COLOR_POSITIVE}}
            ))
            fig_inv.update_layout(title='Puente de Inventario Físico')
            mostrar(fig_inv, ocultar_eje_valores='y')
            
            if demanda_insat > 0 and 'm_bruto' in locals() and m_bruto > 0:
                perdida = demanda_insat * m_bruto
                st.error(f'⚠️ COSTO OPORTUNIDAD: **{format_num(perdida)} USD** de ganancia perdidos por quiebre de stock.')
        
        st.divider()
        log_tech = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) & (df['Seccion'] == f'{tech_sel}, miles unidades') & (df['Ronda'] == ronda_snapshot)]
        def val(planta, metrica):
            r = log_tech[(log_tech['Subgrupo'] == planta) & (log_tech['Metrica'] == metrica)]['Valor']
            return abs(pd.to_numeric(r.iloc[0], errors='coerce')) if len(r) else 0.0

        destinos = ['EE.UU.', 'China', 'Europa']
        matriz = pd.DataFrame(0.0, index=['EE.UU.', 'China', 'Subcontratado'], columns=destinos)
        
        for planta in ['EE.UU.', 'China']:
            interna, contratada = val(planta, 'Producción interna'), val(planta, 'Producción contratada')
            tot = interna + contratada
            flows = {dst: val(planta, f'Ventas en {planta}' if dst == planta else f'Exportado a {dst}') for dst in destinos}
            if tot > 0:
                for dst in destinos:
                    matriz.loc[planta, dst] += flows[dst] * (interna/tot)
                    matriz.loc['Subcontratado', dst] += flows[dst] * (contratada/tot)

        if matriz.sum().sum() > 0:
            fig3 = px.imshow(matriz.values, x=destinos, y=matriz.index, text_auto='.0f', aspect='auto', color_continuous_scale=[[0, 'rgba(0,0,0,0)'], [1, BRAND_ACCENT]])
            fig3.update_coloraxes(showscale=False)
            fig3.update_layout(title='Matriz Logística (Heatmap)')
            mostrar(fig3)

# =================================================================
# SECCIÓN 4 — FINANZAS
# =================================================================
def seccion_finanzas():
    pl_ronda = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]
    ratios_ronda = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)]
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)]

    def wacc(emp):
        de = valor_de(val_ronda, metrica='Deuda a patrimonio', empresa=emp)
        re_ = valor_de(val_ronda, metrica='Rendimiento esperado del patrimonio, %', empresa=emp)
        rd = valor_de(val_ronda, metrica='Costo de la deuda después de impuestos, %', empresa=emp)
        if None in (de, re_, rd): return None
        return (1/(1+de))*re_ + (de/(1+de))*rd

    datos = {
        'EBITDA': {e: valor_de(pl_ronda, metrica='Beneficio operativo antes de depreciación (EBITDA)', empresa=e) for e in COMPANIES},
        'Margen %': {e: valor_de(ratios_ronda, metrica='Margen bruto', empresa=e) for e in COMPANIES},
        'ROS %': {e: valor_de(ratios_ronda, metrica='Rentabilidad de las ventas (ROS)', empresa=e) for e in COMPANIES},
        'ROE %': {e: valor_de(ratios_ronda, metrica='Rendimiento de los Fondos Propios (ROE)', empresa=e) for e in COMPANIES},
        'Apalanc.': {e: valor_de(ratios_ronda, metrica='Endeudamiento neto/patrimonio (apalancamiento)', empresa=e) for e in COMPANIES},
        'WACC %': {e: wacc(e) for e in COMPANIES},
    }

    bloque1, bloque2 = st.tabs(['Desempeño vs. Industria', 'Riesgo y Tendencia'])

    with bloque1:
        cols = st.columns(3)
        for i, (nombre, vals) in enumerate(datos.items()):
            validos = [v for v in vals.values() if pd.notna(v)]
            prom = np.nanmean(validos) if validos else None
            fmt = ',.0f' if nombre == 'EBITDA' else '.1f'
            with cols[i % 3]: tarjeta_delta(nombre, vals.get(empresa_analisis), prom, fmt=fmt)

        st.divider()
        ejes_validos = {k: v for k, v in datos.items() if len([x for x in v.values() if pd.notna(x)]) >= 2}
        if ejes_validos:
            fig2 = go.Figure()
            for i, (nombre, vals) in enumerate(ejes_validos.items()):
                valores = sorted(v for v in vals.values() if pd.notna(v))
                vmin, vmax, vmed = valores[0], valores[-1], np.median(valores)
                vcadiz = vals.get(empresa_analisis)
                rango = (vmax - vmin) or 1
                pos = lambda x: (x - vmin) / rango * 100
                fig2.add_trace(go.Scatter(x=[0, 100], y=[i, i], mode='lines', line=dict(color=MUTED_PALETTE[3], width=6), showlegend=False))
                fig2.add_trace(go.Scatter(x=[pos(vmed)], y=[i], mode='markers', marker=dict(symbol='line-ns', size=16, color=MUTED_PALETTE[1], line_width=2), showlegend=False))
                if vcadiz is not None:
                    fig2.add_trace(go.Scatter(x=[pos(vcadiz)], y=[i], mode='markers', marker=dict(size=14, color=BRAND_ACCENT), showlegend=False))
            fig2.update_layout(yaxis=dict(tickmode='array', tickvals=list(range(len(ejes_validos))), ticktext=list(ejes_validos.keys())), height=300, title='Rango Competitivo (Mín/Med/Máx)')
            mostrar(fig2, ocultar_eje_valores='x')

    with bloque2:
        c1, c2 = st.columns(2)
        with c1:
            rr = pd.DataFrame({'Empresa': COMPANIES, 'Apalancamiento': [datos['Apalanc.'].get(e) for e in COMPANIES], 'ROE': [datos['ROE %'].get(e) for e in COMPANIES]}).dropna()
            if len(rr) > 1:
                fig = px.scatter(rr, x='Apalancamiento', y='ROE', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa', title='Matriz Riesgo / Retorno')
                fig.update_traces(textposition='top center', showlegend=False)
                linea_media(fig, rr['Apalancamiento'].mean(), eje='x')
                linea_media(fig, rr['ROE'].mean(), eje='y')
                mostrar(fig)
        with c2:
            ben = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Metrica'] == 'Beneficio de la ronda')]
            chart_evolucion(ben, 'Beneficio vs. Deuda Histórico') # Mostramos la evolución del beneficio (se podría añadir deuda a y2 si se requiere cruzar en el mismo gráfico)

# =================================================================
# SECCIÓN 5 — RRHH Y SOSTENIBILIDAD
# =================================================================
def seccion_rrhh_sostenibilidad():
    col_a, col_b = st.columns(2)
    with col_a:
        rrhh = df[(df['Estado'] == 'Informe de RRHH') & (df['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])
        salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
        rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
        
        if not salario.empty and not rotacion.empty:
            fig = go.Figure()
            # Eje Y1 para Salario (Rojo Cadiz)
            fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
            # Eje Y2 para Rotacion (Crema/Claro)
            fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', line=dict(color=COLOR_POSITIVE, width=2, dash='dash'), yaxis='y2'))
            fig.update_layout(title='Salario vs Rotación',
                              yaxis=dict(title='Salario', side='left'),
                              yaxis2=dict(title='Rotación', overlaying='y', side='right', showgrid=False))
            mostrar(fig)

    with col_b:
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'])
        dicc = {'Emisiones de CO2': 'Total, toneladas métricas', 'Consumo de energía': 'Total, MWh', 'Consumo de agua': 'Total, miles de m3'}
        sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_esg}') & (df['Metrica'] == dicc[ind])]
        chart_comparacion_equipos(sub_amb, f'{ind} — {pais_esg}')

    st.divider()
    esg = df[(df['Estado'] == 'Informe ESG') & (df['Subgrupo'] == 'Puntuación final') & (df['Metrica'] == 'Reputación ESG') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
    esg['Valor'] = num(esg['Valor'])
    
    cols = st.columns(3)
    for i, pais in enumerate(['EE.UU.', 'China', 'Europa']):
        with cols[i]:
            mkt = df[(df['Estado'] == f'Informe de mercado, {pais}') & (df['Seccion'] == f'{pais} cuotas de mercado, %') & (df['Metrica'] == 'Total') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].rename(columns={'Valor': 'Share'})
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
