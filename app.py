"""
app.py — Tablero de Control Directivo, CÁDIZ Automotive
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

# --- IDENTIDAD Y PALETA SEMÁNTICA ---
MY_COMPANY = 'CADIZ'
COMPANIES = ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CUORE', 'FOCUS', 'TOKIO']

BRAND_ACCENT = '#B3261E'       # Rojo CÁDIZ (Marca / Selección)
COLOR_POSITIVE = '#94D02D'     # Verde Lima (Ingresos / Ganancias / Positivo)
BRAND_DARK = '#1A1714'         # Negro Grafito
BRAND_LIGHT = '#F5F2ED'        # Crema
MUTED_PALETTE = ['#A1A1AA', '#71717A', '#52525B', '#3F3F46', '#27272A', '#D4D4D8']

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
        st.warning(f'No se encontraron archivos .xls en {DATA_DIR}/.')
        st.stop()
    return cargar_historico(tuple(xls_files))

def num(series):
    return pd.to_numeric(series, errors='coerce')

df_all = get_data()

# ---------------- Sidebar ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')

rondas_disponibles = df_all[['Ronda', 'Ronda_Orden']].drop_duplicates().sort_values('Ronda_Orden')['Ronda'].tolist()
ronda_ultima = rondas_disponibles[-1]

ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_disponibles, value=ronda_ultima)
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0)

st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True)

SECCIONES = [
    'Resultados',
    'Mercado',
    'Operaciones',
    'Finanzas',
    'RRHH y Sostenibilidad',
]
seccion = st.sidebar.radio('Sección', SECCIONES)

df = df_all.copy()

# ---------------- Tema y Helpers ----------------
PLOTLY_TEMPLATE = 'plotly_dark' if modo_oscuro else 'plotly_white'
COLOR_TEXT = BRAND_LIGHT if modo_oscuro else BRAND_DARK
COLOR_REF_LINE = 'rgba(255,255,255,0.25)' if modo_oscuro else 'rgba(0,0,0,0.25)'

try:
    st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass

def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    fig.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=COLOR_TEXT, family='JetBrains Mono, monospace'),
                       title_font=dict(family='Oswald, sans-serif', size=16),
                       margin=dict(l=20, r=20, t=50, b=20))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    
    if ocultar_eje_valores == 'y': fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x': fig.update_xaxes(showticklabels=False, title=None)
    
    if en_card:
        with st.container(border=True): st.plotly_chart(fig, use_container_width=True, **kwargs)
    else: st.plotly_chart(fig, use_container_width=True, **kwargs)

def linea_media(fig, valor, eje='y', etiqueta='Promedio'):
    if pd.isna(valor): return
    kwargs = dict(line_dash='dash', line_color=COLOR_REF_LINE, line_width=1.5,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color=COLOR_REF_LINE)
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)

def format_num(val, dec=0):
    if pd.isna(val): return ""
    if abs(val) >= 1_000_000: return f"{val/1_000_000:,.1f}M"
    if abs(val) >= 1_000: return f"{val/1_000:,.0f}k"
    return f"{val:,.{dec}f}"

def tarjeta_delta(label, valor, promedio, is_pct=False, is_x=False):
    if valor is None or pd.isna(valor): return st.metric(label, '—')
    
    fmt_val = f"{valor:,.1f}%" if is_pct else (f"{valor:,.1f}x" if is_x else format_num(valor))
    delta = ((valor - promedio) / promedio * 100) if promedio and promedio != 0 else None
    
    st.metric(label, fmt_val, delta=f'{delta:+.1f}% vs Prom' if delta is not None else None)

def valor_de(sub_df, metrica, empresa=None):
    d = sub_df[sub_df['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

def valor_fuzzy(sub_df, keyword):
    d = sub_df[sub_df['Metrica'].str.contains(rf'^{keyword}', case=False, na=False)]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

# =================================================================
# SECCIÓN 1 — RESULTADOS
# =================================================================
def seccion_resultado():
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)]
    cv_ronda = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == 'Valor total creado') & (df['Ronda'] == ronda_snapshot)]
    
    cv_vals = {emp: num(cv_ronda[cv_ronda['Empresa'] == emp]['Valor']).sum() for emp in COMPANIES}
    cap_vals = {emp: valor_de(val_ronda, 'Capitalización de mercado, miles USD', emp) for emp in COMPANIES}

    st.subheader('KPIs de Valor')
    c1, c2, c3 = st.columns(3)
    with c1: tarjeta_delta('Creación de Valor (USD)', cv_vals.get(empresa_analisis), np.nanmean(list(cv_vals.values())))
    with c2:
        ranking_orden = sorted(cv_vals, key=cv_vals.get, reverse=True)
        pos = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else '-'
        st.metric('Posición del Equipo', f'{pos}° de {len(COMPANIES)}')
    with c3: tarjeta_delta('Market Cap (USD)', cap_vals.get(empresa_analisis), np.nanmean(list(cap_vals.values())))

    st.divider()
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
        ranking = pd.DataFrame(list(cv_vals.items()), columns=['Empresa', 'Valor']).sort_values('Valor', ascending=True).dropna()
        fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa', color_discrete_map=COLOR_MAP)
        fig.update_traces(text=ranking['Valor'].apply(format_num), textposition='outside', cliponaxis=False, showlegend=False)
        fig.update_layout(title='Ranking: Creación de Valor', xaxis=dict(range=[0, ranking['Valor'].max() * 1.25]))
        mostrar(fig, ocultar_eje_valores='x')

    st.divider()
    col_c, col_d = st.columns(2)
    with col_c:
        cv_all = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == 'Valor total creado')].copy()
        cv_all['Valor'] = num(cv_all['Valor'])
        puestos = cv_all.groupby(['Ronda', 'Ronda_Orden', 'Empresa'])['Valor'].sum().reset_index().sort_values(['Ronda_Orden', 'Valor'], ascending=[True, False])
        puestos['Puesto'] = puestos.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
        fig2 = px.line(puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden'), x='Ronda', y='Puesto', markers=True, title=f'Inercia de Posición — {MY_COMPANY}')
        fig2.update_yaxes(autorange='reversed', dtick=1)
        fig2.update_traces(line=dict(color=BRAND_ACCENT, width=3), marker=dict(size=8))
        mostrar(fig2)

    with col_d:
        cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')].copy()
        cap_sub['Valor'] = num(cap_sub['Valor'])
        cap_sub = cap_sub.dropna().sort_values('Ronda_Orden')
        fig3 = go.Figure()
        for emp in COMPANIES:
            d_emp = cap_sub[cap_sub['Empresa'] == emp]
            fig3.add_trace(go.Scatter(x=d_emp['Ronda'], y=d_emp['Valor'], mode='lines+markers', name=emp,
                                      line=dict(color=COLOR_MAP[emp], width=3 if emp == MY_COMPANY else 1)))
        fig3.update_layout(title='Evolución Market Cap')
        mostrar(fig3)

# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'])
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

    estado_pais = f'Informe de mercado, {pais_sel}'
    sub = df[(df['Estado'] == estado_pais) & (df['Seccion'] == tech_sel) & (df['Ronda'] == ronda_snapshot)]
    
    ventas_data = []
    for emp in COMPANIES:
        val = valor_fuzzy(sub[sub['Empresa'] == emp], 'Ventas')
        if pd.notna(val): ventas_data.append({'Empresa': emp, 'Volumen': val})
    vol_df = pd.DataFrame(ventas_data)

    def scatter_posicionamiento(eje_x_metrica, titulo_x):
        eje_x = sub[sub['Metrica'] == eje_x_metrica][['Empresa', 'Valor']].rename(columns={'Valor': titulo_x})
        if vol_df.empty or eje_x.empty: return None
        pos = eje_x.merge(vol_df, on='Empresa').dropna()
        pos[titulo_x] = num(pos[titulo_x])
        if pos.empty: return None
        
        fig = px.scatter(pos, x=titulo_x, y='Volumen', color='Empresa', color_discrete_map=COLOR_MAP, size='Volumen', text='Empresa', title=f'{titulo_x} vs Volumen')
        fig.update_traces(textposition='top center', showlegend=False)
        linea_media(fig, pos['Volumen'].mean(), eje='y', etiqueta='Vol Promedio')
        linea_media(fig, pos[titulo_x].mean(), eje='x', etiqueta=f'{titulo_x} Prom')
        mostrar(fig)
        return True

    col_a, col_b = st.columns(2)
    with col_a: 
        if not scatter_posicionamiento('Precio de venta, USD', 'Precio (USD)'): st.info(f'Falta información de {tech_sel} en {pais_sel}.')
    with col_b: scatter_posicionamiento('Cantidad de características ofrecidas', 'Características')

    st.divider()
    share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') & (df['Metrica'] == 'Total')].copy()
    share_hist['Valor'] = num(share_hist['Valor'])
    share_hist = share_hist.dropna().sort_values('Ronda_Orden')
    
    if not share_hist.empty:
        fig = go.Figure()
        for emp in COMPANIES:
            d_emp = share_hist[share_hist['Empresa'] == emp]
            fig.add_trace(go.Scatter(x=d_emp['Ronda'], y=d_emp['Valor'], mode='lines+markers', name=emp,
                                      line=dict(color=COLOR_MAP[emp], width=4 if emp == MY_COMPANY else 1.5)))
        fig.update_layout(title=f'Evolución de Market Share — {pais_sel}', yaxis_title='% Share')
        mostrar(fig)

# =================================================================
# SECCIÓN 3 — OPERACIONES
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y Costos', 'Inventario y Logística'])

    with bloque1:
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') &
                 (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        cap = cap.dropna()
        if not cap.empty:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                titulo = row['Subgrupo'] if pd.notna(row['Subgrupo']) else 'Capacidad'
                with col:
                    fig = go.Figure(go.Indicator(mode='gauge+number', value=row['Valor'], title={'text': titulo},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': BRAND_ACCENT}, 'steps': [{'range': [0, 100], 'color': '#27272A'}]}))
                    fig.update_layout(height=220, margin=dict(t=40, b=10))
                    mostrar(fig)

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
            fig = go.Figure(go.Funnel(y=[e[0] for e in etapas], x=[e[1] for e in etapas], textinfo='value+percent initial', marker={'color': colores}))
            fig.update_layout(title='Estructura Macro de Costos (Funnel)')
            mostrar(fig, ocultar_eje_valores='x')

        st.divider()
        c3, c4 = st.columns(2)
        pais_ue = c3.selectbox('País Unit Econ', ['EE.UU.', 'China', 'Europa'])
        tech_ue = c4.selectbox('Tech Unit Econ', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])
        margen = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, 'Ventas')

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
            fig_ue.update_layout(title=f'Unit Economics — {tech_ue} {pais_ue}')
            mostrar(fig_ue, ocultar_eje_valores='y')

    with bloque2:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('País Inventario', ['EE.UU.', 'China', 'Europa'])
        tech_sel = c2.selectbox('Tech Inventario', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

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
            demanda_insat = d.get('Demanda insatisfecha', 0) or 0

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
            
            if demanda_insat > 0 and 'm_bruto' in locals() and m_bruto > 0:
                perdida = demanda_insat * m_bruto
                st.error(f'⚠️ COSTO OPORTUNIDAD: **{format_num(perdida)} USD** dejados en la mesa por quiebre de stock ({format_num(demanda_insat)} unidades).')
        
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
            fig3.update_layout(title='Matriz Logística (Heatmap Origen -> Destino)')
            mostrar(fig3)

# =================================================================
# SECCIÓN 4 — FINANZAS
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

    datos = {
        'EBITDA (USD)': {e: valor_de(pl_ronda, 'Beneficio operativo antes de depreciación (EBITDA)', e) for e in COMPANIES},
        'Margen Bruto': {e: valor_de(ratios_ronda, 'Margen bruto', e) for e in COMPANIES},
        'ROS': {e: valor_de(ratios_ronda, 'Rentabilidad de las ventas (ROS)', e) for e in COMPANIES},
        'ROE': {e: valor_de(ratios_ronda, 'Rendimiento de los Fondos Propios (ROE)', e) for e in COMPANIES},
        'Apalancamiento': {e: valor_de(ratios_ronda, 'Endeudamiento neto/patrimonio (apalancamiento)', e) for e in COMPANIES},
        'WACC': {e: wacc(e) for e in COMPANIES},
    }

    bloque1, bloque2 = st.tabs(['Desempeño vs Industria', 'Riesgo y Tendencia'])

    with bloque1:
        cols = st.columns(3)
        for i, (nombre, vals) in enumerate(datos.items()):
            validos = [v for v in vals.values() if pd.notna(v)]
            prom = np.nanmean(validos) if validos else None
            is_pct = nombre in ['Margen Bruto', 'ROS', 'ROE', 'WACC']
            is_x = nombre == 'Apalancamiento'
            with cols[i % 3]: tarjeta_delta(nombre, vals.get(empresa_analisis), prom, is_pct=is_pct, is_x=is_x)

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
                
                # Formato del sufijo
                suf = "%" if nombre in ['Margen Bruto', 'ROS', 'ROE', 'WACC'] else ("x" if nombre == 'Apalancamiento' else "")
                
                fig2.add_trace(go.Scatter(x=[0, 100], y=[i, i], mode='lines', line=dict(color=MUTED_PALETTE[3], width=6), showlegend=False))
                fig2.add_trace(go.Scatter(x=[pos(vmed)], y=[i], mode='markers', marker=dict(symbol='line-ns', size=16, color=MUTED_PALETTE[1], line_width=2), showlegend=False))
                if vcadiz is not None:
                    fig2.add_trace(go.Scatter(x=[pos(vcadiz)], y=[i], mode='markers+text', text=f" {vcadiz:,.1f}{suf}", textposition="middle right", textfont=dict(color=BRAND_ACCENT, size=12, family="JetBrains Mono"), marker=dict(size=14, color=BRAND_ACCENT), showlegend=False))
                
                fig2.add_annotation(x=0, y=i, text=f'{vmin:,.1f}{suf}', showarrow=False, xshift=-30, font=dict(size=11, color=COLOR_REF_LINE))
                fig2.add_annotation(x=100, y=i, text=f'{vmax:,.1f}{suf}', showarrow=False, xshift=30, font=dict(size=11, color=COLOR_REF_LINE))
                
            fig2.update_layout(yaxis=dict(tickmode='array', tickvals=list(range(len(ejes_validos))), ticktext=list(ejes_validos.keys())), xaxis=dict(range=[-10, 115]), height=350, title='Rango Competitivo (Mín/Med/Máx)')
            mostrar(fig2, ocultar_eje_valores='x')

    with bloque2:
        c1, c2 = st.columns(2)
        with c1:
            rr = pd.DataFrame({'Empresa': COMPANIES, 'Apalancamiento': [datos['Apalancamiento'].get(e) for e in COMPANIES], 'ROE': [datos['ROE'].get(e) for e in COMPANIES]}).dropna()
            if len(rr) > 1:
                fig = px.scatter(rr, x='Apalancamiento', y='ROE', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa', title='Matriz Riesgo / Retorno')
                fig.update_traces(textposition='top center', showlegend=False)
                linea_media(fig, rr['Apalancamiento'].mean(), eje='x', etiqueta='Apalanc. Prom')
                linea_media(fig, rr['ROE'].mean(), eje='y', etiqueta='ROE Prom')
                mostrar(fig)
        with c2:
            ben = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Metrica'] == 'Beneficio de la ronda')].copy()
            deuda = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Metrica'] == 'Endeudamiento neto/patrimonio (apalancamiento)')].copy()
            ben['Valor'] = num(ben['Valor'])
            deuda['Valor'] = num(deuda['Valor'])
            
            ben = ben[ben['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')
            deuda = deuda[deuda['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')
            
            if not ben.empty and not deuda.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=ben['Ronda'], y=ben['Valor'], name='Beneficio (USD)', marker_color=COLOR_POSITIVE, yaxis='y1'))
                fig.add_trace(go.Scatter(x=deuda['Ronda'], y=deuda['Valor'], name='Apalancamiento (x)', mode='lines+markers', line=dict(color=MUTED_PALETTE[1], width=3), yaxis='y2'))
                fig.update_layout(title='Beneficio Neto vs. Nivel de Deuda',
                                  yaxis=dict(title='Beneficio (USD)', side='left'),
                                  yaxis2=dict(title='Apalancamiento (x)', overlaying='y', side='right', showgrid=False),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                mostrar(fig)

# =================================================================
# SECCIÓN 5 — RRHH Y SOSTENIBILIDAD
# =================================================================
def seccion_rrhh_sostenibilidad():
    col_a, col_b = st.columns(2)
    with col_a:
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])
        salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
        rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
        
        if not salario.empty and not rotacion.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
            fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', line=dict(color=MUTED_PALETTE[1], width=2, dash='dash'), yaxis='y2'))
            
            # Anclando a cero y dándole espacio al % de rotación
            max_rot = max(15, rotacion['Valor'].max() * 1.2)
            fig.update_layout(title='Evolución: Salario vs Rotación',
                              yaxis=dict(title='Salario (USD)', rangemode='tozero', side='left'),
                              yaxis2=dict(title='Rotación (%)', range=[0, max_rot], overlaying='y', side='right', showgrid=False),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            mostrar(fig)

    with col_b:
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'])
        dicc = {'Emisiones de CO2': 'Total, toneladas métricas', 'Consumo de energía': 'Total, MWh', 'Consumo de agua': 'Total, miles de m3'}
        sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_esg}') & (df['Metrica'] == dicc[ind])]
        chart_comparacion_equipos(sub_amb, f'{ind} — {pais_esg}')

    st.divider()
    esg = df[(df['Estado'] == 'Informe ESG') & (df['Subgrupo'] == 'Puntuación final') & (df['Metrica'] == 'Reputación ESG') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].copy()
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
