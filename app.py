"""
app.py — Tablero de Control Directivo, CÁDIZ Automotive
"""
import glob
import os"""
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

BRAND_ACCENT = '#B3261E'       # Rojo CÁDIZ
COLOR_POSITIVE = '#94D02D'     # Verde Lima
BRAND_DARK = '#1A1714'         # Negro Grafito
BRAND_LIGHT = '#F5F2ED'        # Crema
MUTED_PALETTE = ['#A1A1AA', '#71717A', '#52525B', '#3F3F46', '#27272A', '#D4D4D8']

COLOR_MAP = {MY_COMPANY: BRAND_ACCENT}
for i, c in enumerate([c for c in COMPANIES if c != MY_COMPANY]):
    COLOR_MAP[c] = MUTED_PALETTE[i % len(MUTED_PALETTE)]

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

def num(series):
    return pd.to_numeric(series, errors='coerce')

def format_num(val, dec=0):
    if pd.isna(val) or val is None: return ""
    try:
        val = float(val)
        if abs(val) >= 1_000_000: return f"{val/1_000_000:,.1f}M"
        if abs(val) >= 1_000: return f"{val/1_000:,.0f}k"
        return f"{val:,.{dec}f}"
    except (ValueError, TypeError):
        return ""

def valor_de(sub_df, metrica, empresa=None):
    d = sub_df[sub_df['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

def valor_fuzzy(sub_df, keyword):
    d = sub_df[sub_df['Metrica'].str.contains(rf'{keyword}', case=False, na=False)]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    fig.update_layout(template='plotly_dark' if st.session_state.get('modo_oscuro', True) else 'plotly_white', 
                       paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=BRAND_LIGHT if st.session_state.get('modo_oscuro', True) else BRAND_DARK, family='JetBrains Mono, monospace'),
                       title_font=dict(family='Oswald, sans-serif', size=16),
                       margin=dict(l=20, r=20, t=50, b=20),
                       bargap=0.4) 
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor='#3F3F46')
    fig.update_yaxes(showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor='#3F3F46')
    
    if ocultar_eje_valores == 'y': fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x': fig.update_xaxes(showticklabels=False, title=None)
    
    if en_card:
        with st.container(border=True): st.plotly_chart(fig, use_container_width=True, **kwargs)
    else: st.plotly_chart(fig, use_container_width=True, **kwargs)

def linea_media(fig, valor, eje='y', etiqueta='Promedio'):
    if pd.isna(valor): return
    kwargs = dict(line_dash='dash', line_color='rgba(255,255,255,0.25)', line_width=1.5,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color='rgba(255,255,255,0.25)')
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)

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
                                  name='Promedio', line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash')))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)

# ---------------- Sidebar ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')
filtro_tipo = st.sidebar.radio('Ecosistema', ['Práctica', 'Oficial'], horizontal=True)

rondas_timeline = ['Práctica 1', 'Práctica 2', 'Práctica 3'] if filtro_tipo == 'Práctica' else [f'Ronda {i}' for i in range(1, 13)]
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_timeline, value=rondas_timeline[0])
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0)

st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True, key='modo_oscuro')

SECCIONES = ['Resultados', 'Mercado', 'Operaciones', 'Finanzas', 'RRHH y Sostenibilidad']
seccion = st.sidebar.radio('Sección', SECCIONES)

df_all = get_data(filtro_tipo)

if df_all.empty or ronda_snapshot not in df_all['Ronda'].unique():
    st.info(f"📁 Faltan datos: No se encontraron archivos para **{ronda_snapshot}** en el entorno **{filtro_tipo}**.")
    st.stop()

df = df_all.copy()
ronda_ultima = ronda_snapshot

try:
    st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass

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
    with c1: 
        prom_cv = np.nanmean(list(cv_vals.values())) if cv_vals else None
        delta_cv = ((cv_vals.get(empresa_analisis, 0) - prom_cv)/prom_cv*100) if prom_cv else None
        st.metric('Creación de Valor (USD)', format_num(cv_vals.get(empresa_analisis)), delta=f'{delta_cv:+.1f}% vs Prom' if delta_cv else None)
    with c2:
        ranking_orden = sorted(cv_vals, key=cv_vals.get, reverse=True)
        pos = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else '-'
        st.metric('Posición del Equipo', f'{pos}° de {len(COMPANIES)}')
    with c3: 
        prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None
        val_cap = cap_vals.get(empresa_analisis)
        delta_cap = ((val_cap - prom_cap)/prom_cap*100) if prom_cap and val_cap else None
        st.metric('Market Cap (USD)', format_num(val_cap), delta=f'{delta_cap:+.1f}% vs Prom' if delta_cap else None)

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
        fig2 = px.line(puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden'), x='Ronda', y='Puesto', markers=True, title=f'Evolución de Posición — {MY_COMPANY}')
        fig2.update_yaxes(autorange='reversed', dtick=1)
        fig2.update_traces(line=dict(color=BRAND_ACCENT, width=3), marker=dict(size=8))
        mostrar(fig2)
    with col_d:
        cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')].copy()
        chart_evolucion(cap_sub, 'Evolución Market Cap (USD)')

# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'])
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])
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
    st.subheader('Eficiencia Comercial y Evolución')
    col_c, col_d = st.columns(2)
    with col_c:
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

    with col_d:
        share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') & (df['Metrica'].str.strip() == 'Total')].copy()
        share_hist['Valor'] = num(share_hist['Valor'])
        share_hist = share_hist.dropna().sort_values('Ronda_Orden')
        if not share_hist.empty:
            fig_hist = go.Figure()
            for emp in COMPANIES:
                d_emp = share_hist[share_hist['Empresa'] == emp]
                fig_hist.add_trace(go.Scatter(x=d_emp['Ronda'], y=d_emp['Valor'], mode='lines+markers', name=emp,
                                          line=dict(color=COLOR_MAP[emp], width=4 if emp == MY_COMPANY else 1.5),
                                          marker=dict(size=6 if emp == MY_COMPANY else 0)))
            fig_hist.update_layout(title=f'Evolución de Market Share', yaxis_title='% Share', legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            mostrar(fig_hist)
        else: st.info("Sin datos históricos de cuota de mercado.")

# =================================================================
# SECCIÓN 3 — OPERACIONES
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y Costos', 'Inventario y Logística'])
    with bloque1:
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        if not cap.empty:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                titulo = row['Subgrupo'] if pd.notna(row['Subgrupo']) else 'Capacidad'
                with col:
                    fig = go.Figure(go.Indicator(mode='gauge+number', value=row['Valor'], title={'text': f'Capacidad Instalada ({titulo})'},
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
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, '^Ventas')
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

    # Subsección 1: Corto Plazo (Liquidez y Operación)
    st.subheader('Corto Plazo: Liquidez y Operación')
    c_cp1, c_cp2, c_cp3, c_cp4 = st.columns(4)
    ebitda_val = valor_de(pl_ronda, 'Beneficio operativo antes de depreciación (EBITDA)', empresa_analisis)
    margen_val = valor_de(ratios_ronda, 'Margen bruto', empresa_analisis)
    ros_val = valor_de(ratios_ronda, 'Rentabilidad de las ventas (ROS)', empresa_analisis)
    caja_val = valor_de(val_ronda, 'Caja y equivalentes de efectivo', empresa_analisis)

    with c_cp1: st.metric('EBITDA (USD)', format_num(ebitda_val))
    with c_cp2: st.metric('Margen Bruto', f"{margen_val:,.1f}%" if pd.notna(margen_val) else '—')
    with c_cp3: st.metric('ROS', f"{ros_val:,.1f}%" if pd.notna(ros_val) else '—')
    with c_cp4: st.metric('Caja Final (USD)', format_num(caja_val) if pd.notna(caja_val) else '—')

    st.divider()

    # Subsección 2: Largo Plazo (Estructura, Retorno y Rangos)
    st.subheader('Largo Plazo: Estructura, Retorno y Competencia')
    
    datos_lp = {
        'ROA': {e: valor_fuzzy(ratios_ronda, 'Rendimiento del activo') for e in COMPANIES},
        'ROE': {e: valor_de(ratios_ronda, 'Rendimiento de los Fondos Propios (ROE)', e) for e in COMPANIES},
        'Apalancamiento': {e: valor_de(ratios_ronda, 'Endeudamiento neto/patrimonio (apalancamiento)', e) for e in COMPANIES},
        'WACC': {e: wacc(e) for e in COMPANIES},
    }

    ejes_validos = {k: v for k, v in datos_lp.items() if len([x for x in v.values() if pd.notna(x)]) >= 2}
    if ejes_validos:
        fig_rango = go.Figure()
        for i, (nombre, vals) in enumerate(ejes_validos.items()):
            valores = sorted(v for v in vals.values() if pd.notna(v))
            vmin, vmax, vmed = valores[0], valores[-1], np.median(valores)
            vcadiz = vals.get(empresa_analisis)
            rango = (vmax - vmin) or 1
            pos = lambda x: (x - vmin) / rango * 100
            suf = "%" if nombre in ['ROA', 'ROE', 'WACC'] else "x"
            
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
            
            fig_rango.add_annotation(x=0, y=i, text=f'{vmin:,.1f}{suf}', showarrow=False, xshift=-30, font=dict(size=11, color='rgba(255,255,255,0.5)'))
            fig_rango.add_annotation(x=100, y=i, text=f'{vmax:,.1f}{suf}', showarrow=False, xshift=30, font=dict(size=11, color='rgba(255,255,255,0.5)'))
            
        fig_rango.update_layout(yaxis=dict(tickmode='array', tickvals=list(range(len(ejes_validos))), ticktext=list(ejes_validos.keys())), xaxis=dict(range=[-15, 115]), height=280, title='Rango de Industria (Mín / Mediana / CÁDIZ / Máx)')
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
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ben['Ronda'], y=ben['Valor'], name='Beneficio (USD)', marker_color=COLOR_POSITIVE, yaxis='y1', width=0.15))
            fig.add_trace(go.Scatter(x=deuda['Ronda'], y=deuda['Valor'], name='Apalancamiento (x)', mode='lines+markers', line=dict(color=MUTED_PALETTE[1], width=3), yaxis='y2'))
            fig.update_layout(title='Beneficio Neto vs. Nivel de Deuda',
                              yaxis=dict(title='Beneficio (USD)', side='left', rangemode='tozero'),
                              yaxis2=dict(title='Apalancamiento (x)', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                              legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            mostrar(fig)

# =================================================================
# SECCIÓN 5 — RRHH Y SOSTENIBILIDAD
# =================================================================
def seccion_rrhh_sostenibilidad():
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader('SALARIOS VS ROTACIÓN')
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])
        salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
        rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
        if not salario.empty and not rotacion.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', mode='lines+markers', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
            fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers', line=dict(color=COLOR_POSITIVE, width=2, dash='dash'), yaxis='y2'))
            
            # Forzar escala limpia para el eje de rotación y salarios
            max_rot = max(20, rotacion['Valor'].max() * 1.3 if not rotacion['Valor'].empty else 20)
            max_sal = max(6000, salario['Valor'].max() * 1.2 if not salario['Valor'].empty else 6000)
            
            fig.update_layout(title='Evolución: Salario vs Rotación',
                              yaxis=dict(title='Salario (USD)', range=[0, max_sal], rangemode='tozero', side='left'),
                              yaxis2=dict(title='Rotación (%)', range=[0, max_rot], overlaying='y', side='right', showgrid=False),
                              legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            mostrar(fig)

    with col_b:
        st.subheader('IMPACTO AMBIENTAL')
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'])
        dicc = {'Emisiones de CO2': 'Total, toneladas métricas', 'Consumo de energía': 'Total, MWh', 'Consumo de agua': 'Total, miles de m3'}
        sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_esg}') & (df['Metrica'] == dicc[ind])]
        chart_comparacion_equipos(sub_amb, f'{ind} — {pais_esg}')

    st.divider()
    st.subheader('REPUTACIÓN ESG VS MARKET SHARE')
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

BRAND_ACCENT = '#B3261E'       # Rojo CÁDIZ
COLOR_POSITIVE = '#94D02D'     # Verde Lima
BRAND_DARK = '#1A1714'         # Negro Grafito
BRAND_LIGHT = '#F5F2ED'        # Crema
MUTED_PALETTE = ['#A1A1AA', '#71717A', '#52525B', '#3F3F46', '#27272A', '#D4D4D8']

COLOR_MAP = {MY_COMPANY: BRAND_ACCENT}
for i, c in enumerate([c for c in COMPANIES if c != MY_COMPANY]):
    COLOR_MAP[c] = MUTED_PALETTE[i % len(MUTED_PALETTE)]

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

def num(series):
    return pd.to_numeric(series, errors='coerce')

def format_num(val, dec=0):
    if pd.isna(val) or val is None: return ""
    try:
        val = float(val)
        if abs(val) >= 1_000_000: return f"{val/1_000_000:,.1f}M"
        if abs(val) >= 1_000: return f"{val/1_000:,.0f}k"
        return f"{val:,.{dec}f}"
    except (ValueError, TypeError):
        return ""

def valor_de(sub_df, metrica, empresa=None):
    d = sub_df[sub_df['Metrica'] == metrica]
    if empresa: d = d[d['Empresa'] == empresa]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

def valor_fuzzy(sub_df, keyword):
    d = sub_df[sub_df['Metrica'].str.contains(rf'{keyword}', case=False, na=False)]
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce') if not d.empty else None

def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    fig.update_layout(template='plotly_dark' if st.session_state.get('modo_oscuro', True) else 'plotly_white', 
                       paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                       font=dict(color=BRAND_LIGHT if st.session_state.get('modo_oscuro', True) else BRAND_DARK, family='JetBrains Mono, monospace'),
                       title_font=dict(family='Oswald, sans-serif', size=16),
                       margin=dict(l=20, r=20, t=50, b=20),
                       bargap=0.4) 
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor='#3F3F46')
    fig.update_yaxes(showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor='#3F3F46')
    
    if ocultar_eje_valores == 'y': fig.update_yaxes(showticklabels=False, title=None)
    elif ocultar_eje_valores == 'x': fig.update_xaxes(showticklabels=False, title=None)
    
    if en_card:
        with st.container(border=True): st.plotly_chart(fig, use_container_width=True, **kwargs)
    else: st.plotly_chart(fig, use_container_width=True, **kwargs)

def linea_media(fig, valor, eje='y', etiqueta='Promedio'):
    if pd.isna(valor): return
    kwargs = dict(line_dash='dash', line_color='rgba(255,255,255,0.25)', line_width=1.5,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color='rgba(255,255,255,0.25)')
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)

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
                                  name='Promedio', line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash')))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)

# ---------------- Sidebar ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')
filtro_tipo = st.sidebar.radio('Ecosistema', ['Práctica', 'Oficial'], horizontal=True)

rondas_timeline = ['Práctica 1', 'Práctica 2', 'Práctica 3'] if filtro_tipo == 'Práctica' else [f'Ronda {i}' for i in range(1, 13)]
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_timeline, value=rondas_timeline[0])
empresa_analisis = st.sidebar.selectbox('Equipo in foco', COMPANIES, index=0)

st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True, key='modo_oscuro')

SECCIONES = ['Resultados', 'Mercado', 'Operaciones', 'Finanzas', 'RRHH y Sostenibilidad']
seccion = st.sidebar.radio('Sección', SECCIONES)

df_all = get_data(filtro_tipo)

if df_all.empty or ronda_snapshot not in df_all['Ronda'].unique():
    st.info(f"📁 Faltan datos: No se encontraron archivos para **{ronda_snapshot}** en el entorno **{filtro_tipo}**.")
    st.stop()

df = df_all.copy()
ronda_ultima = ronda_snapshot

try:
    st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass

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
    with c1: 
        prom_cv = np.nanmean(list(cv_vals.values())) if cv_vals else None
        delta_cv = ((cv_vals.get(empresa_analisis, 0) - prom_cv)/prom_cv*100) if prom_cv else None
        st.metric('Creación de Valor (USD)', format_num(cv_vals.get(empresa_analisis)), delta=f'{delta_cv:+.1f}% vs Prom' if delta_cv else None)
    with c2:
        ranking_orden = sorted(cv_vals, key=cv_vals.get, reverse=True)
        pos = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else '-'
        st.metric('Posición del Equipo', f'{pos}° de {len(COMPANIES)}')
    with c3: 
        prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None
        val_cap = cap_vals.get(empresa_analisis)
        delta_cap = ((val_cap - prom_cap)/prom_cap*100) if prom_cap and val_cap else None
        st.metric('Market Cap (USD)', format_num(val_cap), delta=f'{delta_cap:+.1f}% vs Prom' if delta_cap else None)

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
        fig2 = px.line(puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden'), x='Ronda', y='Puesto', markers=True, title=f'Evolución de Posición — {MY_COMPANY}')
        fig2.update_yaxes(autorange='reversed', dtick=1)
        fig2.update_traces(line=dict(color=BRAND_ACCENT, width=3), marker=dict(size=8))
        mostrar(fig2)
    with col_d:
        cap_sub = df[(df['Estado'] == 'Valuación - Global') & (df['Metrica'] == 'Capitalización de mercado, miles USD')].copy()
        chart_evolucion(cap_sub, 'Evolución Market Cap (USD)')

# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'])
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])
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
    st.subheader('Eficiencia Comercial y Evolución')
    col_c, col_d = st.columns(2)
    with col_c:
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

    with col_d:
        share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') & (df['Metrica'].str.strip() == 'Total')].copy()
        share_hist['Valor'] = num(share_hist['Valor'])
        share_hist = share_hist.dropna().sort_values('Ronda_Orden')
        if not share_hist.empty:
            fig_hist = go.Figure()
            for emp in COMPANIES:
                d_emp = share_hist[share_hist['Empresa'] == emp]
                fig_hist.add_trace(go.Scatter(x=d_emp['Ronda'], y=d_emp['Valor'], mode='lines+markers', name=emp,
                                          line=dict(color=COLOR_MAP[emp], width=4 if emp == MY_COMPANY else 1.5),
                                          marker=dict(size=6 if emp == MY_COMPANY else 0)))
            fig_hist.update_layout(title=f'Evolución de Market Share', yaxis_title='% Share', legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            mostrar(fig_hist)
        else: st.info("Sin datos históricos de cuota de mercado.")

# =================================================================
# SECCIÓN 3 — OPERACIONES
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y Costos', 'Inventario y Logística'])
    with bloque1:
        cap = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Capacidad empleada, %') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot) & (df['Subgrupo'].isin(['EE.UU.', 'China']))].copy()
        cap['Valor'] = num(cap['Valor'])
        if not cap.empty:
            cols = st.columns(len(cap))
            for col, (_, row) in zip(cols, cap.iterrows()):
                titulo = row['Subgrupo'] if pd.notna(row['Subgrupo']) else 'Capacidad'
                with col:
                    fig = go.Figure(go.Indicator(mode='gauge+number', value=row['Valor'], title={'text': f'Capacidad Instalada ({titulo})'},
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
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_ue}') & (df['Seccion'] == tech_ue) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, '^Ventas')
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

    # Subsección 1: Corto Plazo (Liquidez y Operación)
    st.subheader('Corto Plazo: Liquidez y Operación')
    c_cp1, c_cp2, c_cp3, c_cp4 = st.columns(4)
    ebitda_val = valor_de(pl_ronda, 'Beneficio operativo antes de depreciación (EBITDA)', empresa_analisis)
    margen_val = valor_de(ratios_ronda, 'Margen bruto', empresa_analisis)
    ros_val = valor_de(ratios_ronda, 'Rentabilidad de las ventas (ROS)', empresa_analisis)
    
    # Búsqueda robusta para Caja Final (busca CUALQUIER métrica que contenga la palabra 'caja')
    caja_val = valor_fuzzy(val_ronda, 'Caja')

    with c_cp1: st.metric('EBITDA (USD)', format_num(ebitda_val))
    with c_cp2: st.metric('Margen Bruto', f"{margen_val:,.1f}%" if pd.notna(margen_val) else '—')
    with c_cp3: st.metric('ROS', f"{ros_val:,.1f}%" if pd.notna(ros_val) else '—')
    with c_cp4: st.metric('Caja Final (USD)', format_num(caja_val) if pd.notna(caja_val) else '—')

    st.divider()

    # Subsección 2: Largo Plazo (Estructura, Retorno y Rangos)
    st.subheader('Largo Plazo: Estructura, Retorno y Competencia')
    
    datos_lp = {
        'ROA': {e: valor_fuzzy(ratios_ronda, 'Rendimiento del activo') for e in COMPANIES},
        'ROE': {e: valor_de(ratios_ronda, 'Rendimiento de los Fondos Propios (ROE)', e) for e in COMPANIES},
        'Apalancamiento': {e: valor_de(ratios_ronda, 'Endeudamiento neto/patrimonio (apalancamiento)', e) for e in COMPANIES},
        'WACC': {e: wacc(e) for e in COMPANIES},
    }

    ejes_validos = {k: v for k, v in datos_lp.items() if len([x for x in v.values() if pd.notna(x)]) >= 2}
    if ejes_validos:
        fig_rango = go.Figure()
        for i, (nombre, vals) in enumerate(ejes_validos.items()):
            valores = sorted(v for v in vals.values() if pd.notna(v))
            vmin, vmax, vmed = valores[0], valores[-1], np.median(valores)
            vcadiz = vals.get(empresa_analisis)
            rango = (vmax - vmin) or 1
            pos = lambda x: (x - vmin) / rango * 100
            suf = "%" if nombre in ['ROA', 'ROE', 'WACC'] else "x"
            
            fig_rango.add_trace(go.Scatter(x=[0, 100], y=[i, i], mode='lines', line=dict(color=MUTED_PALETTE[3], width=6), showlegend=False))
            fig_rango.add_trace(go.Scatter(x=[pos(vmed)], y=[i], mode='markers', marker=dict(symbol='line-ns', size=16, color=MUTED_PALETTE[1], line_width=2), showlegend=False))
            if vcadiz is not None:
                fig_rango.add_trace(go.Scatter(x=[pos(vcadiz)], y=[i], mode='markers', marker=dict(size=14, color=BRAND_ACCENT), showlegend=False))
            fig_rango.add_annotation(x=0, y=i, text=f'{vmin:,.1f}{suf}', showarrow=False, xshift=-30, font=dict(size=11, color='rgba(255,255,255,0.5)'))
            fig_rango.add_annotation(x=100, y=i, text=f'{vmax:,.1f}{suf}', showarrow=False, xshift=30, font=dict(size=11, color='rgba(255,255,255,0.5)'))
            
        fig_rango.update_layout(yaxis=dict(tickmode='array', tickvals=list(range(len(ejes_validos))), ticktext=list(ejes_validos.keys())), xaxis=dict(range=[-10, 110]), height=250, title='Rango de Industria (Mín / Mediana / CÁDIZ / Máx)')
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
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ben['Ronda'], y=ben['Valor'], name='Beneficio (USD)', marker_color=COLOR_POSITIVE, yaxis='y1', width=0.15))
            fig.add_trace(go.Scatter(x=deuda['Ronda'], y=deuda['Valor'], name='Apalancamiento (x)', mode='lines+markers', line=dict(color=MUTED_PALETTE[1], width=3), yaxis='y2'))
            fig.update_layout(title='Beneficio Neto vs. Nivel de Deuda',
                              yaxis=dict(title='Beneficio (USD)', side='left', rangemode='tozero'),
                              yaxis2=dict(title='Apalancamiento (x)', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                              legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            mostrar(fig)

# =================================================================
# SECCIÓN 5 — RRHH Y SOSTENIBILIDAD
# =================================================================
def seccion_rrhh_sostenibilidad():
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader('SALARIOS VS ROTACIÓN')
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])
        salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
        rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
        if not salario.empty and not rotacion.empty:
            # Si hay 1 sola ronda, mostramos métricas ejecutivas directas limpias para evitar puntos flotantes deformes
            if len(salario) == 1:
                st.metric("Salario Mensual Actual", f"${salario['Valor'].iloc[0]:,.0f}")
                st.metric("Rotación de Personal Actual", f"{rotacion['Valor'].iloc[0]:,.1f}%")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', mode='lines+markers', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
                fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers', line=dict(color=COLOR_POSITIVE, width=2, dash='dash'), yaxis='y2'))
                max_rot = max(15, rotacion['Valor'].max() * 1.2)
                fig.update_layout(title='Evolución: Salario vs Rotación',
                                  yaxis=dict(title='Salario (USD)', rangemode='tozero', side='left'),
                                  yaxis2=dict(title='Rotación (%)', range=[0, max_rot], overlaying='y', side='right', showgrid=False),
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                mostrar(fig)

    with col_b:
        st.subheader('IMPACTO AMBIENTAL')
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'])
        dicc = {'Emisiones de CO2': 'Total, toneladas métricas', 'Consumo de energía': 'Total, MWh', 'Consumo de agua': 'Total, miles de m3'}
        sub_amb = df[(df['Estado'] == 'Informe ESG') & (df['Seccion'] == f'Impacto ambiental, {pais_esg}') & (df['Metrica'] == dicc[ind])]
        chart_comparacion_equipos(sub_amb, f'{ind} — {pais_esg}')

    st.divider()
    st.subheader('REPUTACIÓN ESG VS MARKET SHARE')
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
