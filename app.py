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
    color_ref = 'rgba(255,255,255,0.35)' if st.session_state.get('modo_oscuro', True) else 'rgba(26,23,20,0.35)'
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
        color_ref = 'rgba(255,255,255,0.35)' if st.session_state.get('modo_oscuro', True) else 'rgba(26,23,20,0.35)'
        fig.add_trace(go.Scatter(x=promedio_x_ronda['Ronda'], y=promedio_x_ronda['Valor'], mode='lines+markers',
                                  name='Promedio', line=dict(color=color_ref, width=1, dash='dash'), marker=dict(size=4)))
    fig.update_layout(title=f'Evolución — {titulo}')
    mostrar(fig)
# ---------------- Sidebar ----------------
st.sidebar.markdown('### CÁDIZ AUTOMOTIVE')
filtro_tipo = st.sidebar.radio('Ecosistema', ['Práctica', 'Oficial'], horizontal=True, key='filtro_ecosistema')
rondas_timeline = ['Práctica 1', 'Práctica 2', 'Práctica 3'] if filtro_tipo == 'Práctica' else [f'Ronda {i}' for i in range(1, 13)]
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_timeline, value=rondas_timeline[0], key='slider_rondas')
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0, key='select_equipo')
st.sidebar.divider()
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True, key='modo_oscuro')
SECCIONES = ['Resultados', 'Mercado', 'Operaciones', 'Finanzas', 'RRHH y Sostenibilidad']
seccion = st.sidebar.radio('Sección', SECCIONES, key='select_seccion_router')
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

    cap_vals = {emp: valor_de(val_ronda, 'Capitalización de mercado, miles USD', emp) for emp in COMPANIES}
    st.subheader('KPIs de Valor')
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        prom_ret_acum = np.nanmean([v for v in retorno_acum_vals.values() if v is not None]) if any(v is not None for v in retorno_acum_vals.values()) else None
        val_ret_acum = retorno_acum_vals.get(empresa_analisis)
        delta_ret_acum = ((val_ret_acum - prom_ret_acum) / abs(prom_ret_acum) * 100) if prom_ret_acum and val_ret_acum is not None else None
        st.metric('Retorno del Accionista — ACUMULADO', f'{val_ret_acum:,.1f}%' if val_ret_acum is not None else '—',
                   delta=f'{delta_ret_acum:+.1f}% vs Prom' if delta_ret_acum is not None else None)
    with c2:
        ranking_acum = sorted([e for e in retorno_acum_vals if retorno_acum_vals.get(e) is not None], key=retorno_acum_vals.get, reverse=True)
        pos = ranking_acum.index(empresa_analisis) + 1 if empresa_analisis in ranking_acum else '-'
        st.metric('Posición ACUMULADA', f'{pos}° de {len(COMPANIES)}')
    with c3:
        prom_cv = np.nanmean([v for v in cv_vals.values() if v is not None]) if any(v is not None for v in cv_vals.values()) else None
        val_cv = cv_vals.get(empresa_analisis)
        delta_cv = ((val_cv - prom_cv)/prom_cv*100) if prom_cv and val_cv is not None else None
        st.metric(f'Beneficio del Accionista — {ronda_snapshot} (USD)', format_num(val_cv), delta=f'{delta_cv:+.1f}% vs Prom' if delta_cv is not None else None)
    with c4: 
        prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None
        val_cap = cap_vals.get(empresa_analisis)
        delta_cap = ((val_cap - prom_cap)/prom_cap*100) if prom_cap and val_cap else None
        st.metric('Market Cap (USD)', format_num(val_cap), delta=f'{delta_cap:+.1f}% vs Prom' if delta_cap else None)
    st.caption('"Retorno acumulado" y "Beneficio del accionista" miden solo lo que le corresponde al accionista '
               '(no incluyen lo pagado a proveedores, personal o gobierno).')
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
        vista_ranking = st.radio('Vista del ranking', ['Acumulado (Retorno del Accionista, %)', f'Solo {ronda_snapshot} (USD)'], horizontal=True, key='vista_ranking_cv')
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
    col_c, col_d = st.columns(2)
    with col_c:
        ret_all = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Metrica'] == 'Retorno total acumulado del accionista (p.a.), %')].copy()
        ret_all['Valor'] = num(ret_all['Valor'])
        puestos = ret_all.groupby(['Ronda', 'Ronda_Orden', 'Empresa'])['Valor'].sum().reset_index().sort_values('Ronda_Orden')
        puestos['Puesto'] = puestos.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
        fig2 = px.line(puestos[puestos['Empresa'] == MY_COMPANY].sort_values('Ronda_Orden'), x='Ronda', y='Puesto', markers=True,
                        title=f'Evolución de Posición ACUMULADA — {MY_COMPANY}')
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
    pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'], key='sel_mercado_pais')
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'], key='sel_mercado_tech')
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
# =================================================================
# SECCIÓN 3 — OPERACIONES
# =================================================================
def seccion_operaciones():
    bloque1, bloque2 = st.tabs(['Capacidad y Costos', 'Inventario y Logística'])
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
        pais_ue = c3.selectbox('País Unit Econ', ['EE.UU.', 'China', 'Europa'], key='sel_op_pais')
        tech_ue = c4.selectbox('Tech Unit Econ', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'], key='sel_op_tech')
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
            fig_ue.update_layout(title=f'Unit Economics — {tech_ue} {pais_ue}')
            mostrar(fig_ue, ocultar_eje_valores='y')
    with bloque2:
        c1, c2 = st.columns(2)
        pais_sel = c1.selectbox('País Inventario', ['EE.UU.', 'China', 'Europa'], key='sel_inv_pais')
        tech_sel = c2.selectbox('Tech Inventario', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'], key='sel_inv_tech')
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
    tab_cp, tab_lp = st.tabs(['Corto Plazo: Liquidez y Operación', 'Largo Plazo: Estructura, Retorno y Competencia'])

    with tab_cp:
        c_cp1, c_cp2, c_cp3, c_cp4 = st.columns(4)
        ebitda_val = valor_de(pl_ronda, 'Beneficio operativo antes de depreciación (EBITDA)', empresa_analisis)
        margen_val = valor_de(ratios_ronda, 'Margen bruto', empresa_analisis)
        ros_val = valor_de(ratios_ronda, 'Rentabilidad de las ventas (ROS)', empresa_analisis)
        caja_val = valor_de(df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Ronda'] == ronda_snapshot)],
                             'Efectivo y equivalentes de efectivo', empresa_analisis)
        with c_cp1: st.metric('EBITDA (USD)', format_num(ebitda_val))
        with c_cp2: st.metric('Margen Bruto', f"{margen_val:,.1f}%" if pd.notna(margen_val) else '—')
        with c_cp3: st.metric('ROS', f"{ros_val:,.1f}%" if pd.notna(ros_val) else '—')
        with c_cp4: st.metric('Caja Final (USD)', format_num(caja_val) if pd.notna(caja_val) else '—')
        st.divider()

        # Subsección 1.5: Deuda y Liquidez — "¿tuvimos que salir a pedir plata de apuro?"
        st.subheader('Deuda y Liquidez')
        bal_ronda = df[(df['Estado'] == 'Hoja de Balance, miles USD, Global') & (df['Ronda'] == ronda_snapshot)]
        deuda_cp_vals = {e: valor_de(bal_ronda, 'Deudas a corto plazo (no planificadas)', e) for e in COMPANIES}
        deuda_lp_vals = {e: valor_de(bal_ronda, 'Deudas a largo plazo', e) for e in COMPANIES}
        calif_val = valor_texto(ratios_ronda, 'Calificación crediticia', empresa_analisis)
        prom_deuda_cp = np.nanmean([v for v in deuda_cp_vals.values() if v is not None]) if any(v is not None for v in deuda_cp_vals.values()) else None
        val_deuda_cp = deuda_cp_vals.get(empresa_analisis)

        c_dl1, c_dl2, c_dl3 = st.columns(3)
        with c_dl1:
            delta_cp = ((val_deuda_cp - prom_deuda_cp) / prom_deuda_cp * 100) if prom_deuda_cp and val_deuda_cp is not None else None
            st.metric('Deuda CP no planificada (USD)', format_num(val_deuda_cp) if val_deuda_cp is not None else '—',
                       delta=f'{delta_cp:+.1f}% vs Prom' if delta_cp is not None else None, delta_color='inverse')
        with c_dl2:
            st.metric('Deuda LP (USD)', format_num(deuda_lp_vals.get(empresa_analisis)))
        with c_dl3:
            st.metric('Calificación crediticia', calif_val if calif_val else '—')
        if val_deuda_cp and val_deuda_cp > 0:
            st.caption(f'⚠️ {empresa_analisis} tomó {format_num(val_deuda_cp)} USD de deuda de corto plazo NO planificada en {ronda_snapshot} '
                       '— es el sobregiro automático de Cesim cuando la caja no alcanza para cubrir obligaciones, y suele venir con tasa de interés penal.')

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
            colores_activo = [BRAND_ACCENT] + MUTED_PALETTE[:3]
            colores_pasivo = MUTED_PALETTE[:3] + [BRAND_ACCENT, MUTED_PALETTE[4]]
            for (nombre, val), color in zip(activo_items.items(), colores_activo):
                fig_bal.add_trace(go.Bar(x=['Activo'], y=[val], name=nombre, marker_color=color,
                                          text=format_num(val), textposition='inside'))
            for (nombre, val), color in zip(pasivo_pn_items.items(), colores_pasivo):
                fig_bal.add_trace(go.Bar(x=['Pasivo + PN'], y=[val], name=nombre, marker_color=color,
                                          text=format_num(val), textposition='inside'))
            fig_bal.update_layout(barmode='stack', title=f'Estructura del Balance — {empresa_analisis}, {ronda_snapshot}',
                                   legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
            mostrar(fig_bal, ocultar_eje_valores='y')
            st.caption('Los dos lados deben dar la misma altura (el Balance siempre cierra) — Activo total = Pasivo + Patrimonio Neto.')
        else:
            st.info('Sin datos de balance para esta combinación.')

        st.divider()
        st.markdown('**Costo de la deuda por mercado**')
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
            st.caption('Tasas más altas en general reflejan menor calificación crediticia — se pueden comparar directo contra la calificación de arriba.')

        datos_lp = {
            'ROCE': {e: valor_fuzzy(ratios_ronda, 'Rentabilidad del capital empleado', empresa=e) for e in COMPANIES},
            'ROE': {e: valor_de(ratios_ronda, 'Rendimiento de los Fondos Propios (ROE)', e) for e in COMPANIES},
            'Apalancamiento': {e: valor_de(ratios_ronda, 'Endeudamiento neto/patrimonio (apalancamiento)', e) for e in COMPANIES},
            'WACC': {e: wacc(e) for e in COMPANIES},
        }
        ejes_validos = {k: v for k, v in datos_lp.items() if len([x for x in v.values() if pd.notna(x)]) >= 2}
        if ejes_validos:
            color_ref = 'rgba(255,255,255,0.5)' if st.session_state.get('modo_oscuro', True) else 'rgba(26,23,20,0.5)'
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
    bloque_rrhh, bloque_sost = st.tabs(['Personal y Talento', 'Sostenibilidad'])

    with bloque_rrhh:
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)].copy()
        rrhh['Valor'] = num(rrhh['Valor'])

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader('SALARIO VS ROTACIÓN')
            salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
            rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
            if not salario.empty and not rotacion.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', mode='lines+markers', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
                fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers', line=dict(color=COLOR_POSITIVE, width=2, dash='dash'), yaxis='y2'))
                max_rot = max(20, rotacion['Valor'].max() * 1.3 if not rotacion['Valor'].empty else 20)
                max_sal = max(6000, salario['Valor'].max() * 1.2 if not salario['Valor'].empty else 6000)
                fig.update_layout(title='Evolución: Salario vs Rotación',
                                  yaxis=dict(title='Salario (USD)', range=[0, max_sal], rangemode='tozero', side='left'),
                                  yaxis2=dict(title='Rotación (%)', range=[0, max_rot], overlaying='y', side='right', showgrid=False),
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                mostrar(fig)
        with col_b:
            st.subheader('ROTACIÓN VS CONTRATACIONES')
            st.caption('Cuántas contrataciones netas hizo falta hacer, en la misma ronda en que se dio la rotación.')
            contrat = rrhh[rrhh['Metrica'] == 'Contrataciones + / despidos -'].sort_values('Ronda_Orden')
            if not salario.empty and not contrat.empty and not rotacion.empty:
                fig_ch = go.Figure()
                fig_ch.add_trace(go.Bar(x=contrat['Ronda'], y=contrat['Valor'], name='Contrataciones netas (personas)',
                                         marker_color=MUTED_PALETTE[0], yaxis='y1'))
                fig_ch.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers',
                                             line=dict(color=BRAND_ACCENT, width=3), yaxis='y2'))
                fig_ch.update_layout(title='Rotación vs. Contrataciones netas',
                                      yaxis=dict(title='Personas', side='left', rangemode='tozero'),
                                      yaxis2=dict(title='Rotación, %', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                      legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                mostrar(fig_ch)

        st.divider()
        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader('INVERSIÓN EN I+D')
            idn = rrhh[rrhh['Metrica'] == 'Número de personal de I+D, esta ronda'].sort_values('Ronda_Orden')
            idc = rrhh[rrhh['Metrica'] == 'Otros costos variables de I + D'].sort_values('Ronda_Orden')
            if not idn.empty and not idc.empty:
                fig_id = go.Figure()
                fig_id.add_trace(go.Bar(x=idc['Ronda'], y=idc['Valor'], name='Costo variable I+D (USD)',
                                         marker_color=MUTED_PALETTE[0], yaxis='y1'))
                fig_id.add_trace(go.Scatter(x=idn['Ronda'], y=idn['Valor'], name='Personal I+D (headcount)', mode='lines+markers',
                                             line=dict(color=BRAND_ACCENT, width=3), yaxis='y2'))
                fig_id.update_layout(title='Inversión en I+D: costo vs. dotación',
                                      yaxis=dict(title='Costo variable, USD', side='left', rangemode='tozero'),
                                      yaxis2=dict(title='Personal I+D', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                      legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                mostrar(fig_id)
            else:
                st.info('Sin datos de I+D para este equipo.')
        with col_d:
            st.subheader('CAPACITACIÓN: INVERSIÓN VS. IMPACTO')
            capac = rrhh[rrhh['Metrica'] == 'Presupuesto mensual para capacitación, USD'].sort_values('Ronda_Orden')
            efic = rrhh[rrhh['Metrica'] == 'Multiplicador de la eficiencia de RRHH'].sort_values('Ronda_Orden')
            if not capac.empty and not efic.empty:
                fig_cap = go.Figure()
                fig_cap.add_trace(go.Bar(x=capac['Ronda'], y=capac['Valor'], name='Presupuesto capacitación (USD)',
                                          marker_color=MUTED_PALETTE[0], yaxis='y1'))
                fig_cap.add_trace(go.Scatter(x=efic['Ronda'], y=efic['Valor'], name='Multiplicador eficiencia RRHH', mode='lines+markers',
                                              line=dict(color=BRAND_ACCENT, width=3), yaxis='y2'))
                fig_cap.update_layout(title='Capacitación vs. eficiencia de RRHH',
                                       yaxis=dict(title='Presupuesto, USD', side='left', rangemode='tozero'),
                                       yaxis2=dict(title='Multiplicador eficiencia', overlaying='y', side='right', showgrid=False),
                                       legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                mostrar(fig_cap)
                st.caption('Con una sola ronda esto es un punto de referencia — el "impacto" real de la capacitación se lee '
                           'en la pendiente entre rondas, no en un valor aislado.')
            else:
                st.info('Sin datos de capacitación para este equipo.')

    with bloque_sost:
        st.subheader('IMPACTO AMBIENTAL')
        c1, c2 = st.columns(2)
        pais_esg = c1.selectbox('País', ['EE.UU.', 'China'], key='pais_esg_rrhh')
        ind = c2.selectbox('Indicador', ['Emisiones de CO2', 'Consumo de energía', 'Consumo de agua'], key='ind_esg_rrhh')
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
