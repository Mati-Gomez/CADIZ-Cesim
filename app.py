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

# --- IDENTIDAD CÁDIZ ---
MY_COMPANY = 'CADIZ'
COMPANIES = ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CUORE', 'FOCUS', 'TOKIO']
BRAND_ACCENT = '#B3261E'
BRAND_DARK = '#1A1714'
BRAND_LIGHT = '#F5F2ED'
# Grises planos para la competencia
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
        st.warning(f'No se encontraron archivos en {DATA_DIR}/.')
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
modo_oscuro = st.sidebar.toggle('Modo oscuro', value=True)

SECCIONES = [
    '1. El Resultado (Valor y Posición)',
    '2. El Frente de Batalla (Mercado)',
    '3. La Sala de Máquinas (Operaciones)',
    '4. La Salud del Negocio (Finanzas)',
    '5. El Largo Plazo (RRHH y ESG)',
]
seccion = st.sidebar.radio('Sección', SECCIONES)

# Filtrar df global a solo la ronda seleccionada o anteriores si es necesario
df = df_all.copy()

# ---------------- Tema y Helpers ----------------
PLOTLY_TEMPLATE = 'plotly_dark' if modo_oscuro else 'plotly_white'
BG_COLOR = BRAND_DARK if modo_oscuro else BRAND_LIGHT
TEXT_COLOR = BRAND_LIGHT if modo_oscuro else BRAND_DARK
GRID_COLOR = 'rgba(255,255,255,0.05)' if modo_oscuro else 'rgba(0,0,0,0.05)'
REF_COLOR = 'rgba(255,255,255,0.2)' if modo_oscuro else 'rgba(0,0,0,0.2)'

st.markdown(f'<style>{open(os.path.join(BASE_DIR, "assets", "style.css"), encoding="utf-8").read()}</style>', unsafe_allow_html=True)

def mostrar(fig, ocultar_eje_valores=None, en_card=True, **kwargs):
    fig.update_layout(
        template=PLOTLY_TEMPLATE, 
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT_COLOR, family='JetBrains Mono, monospace'),
        title_font=dict(family='Oswald, sans-serif', size=18)
    )
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
    kwargs = dict(line_dash='dash', line_color=REF_COLOR, line_width=1,
                  annotation_text=etiqueta, annotation_font_size=10, annotation_font_color=REF_COLOR)
    if eje == 'y': fig.add_hline(y=valor, **kwargs)
    else: fig.add_vline(x=valor, **kwargs)

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

def valor_fuzzy(sub_df, keyword):
    """Busca métricas por palabra clave para evitar fallos de traducción/formato de Cesim."""
    d = sub_df[sub_df['Metrica'].str.contains(keyword, case=False, na=False)]
    if d.empty: return None
    return pd.to_numeric(d['Valor'].iloc[0], errors='coerce')

# =================================================================
# SECCIÓN 1 — EL RESULTADO
# =================================================================
def seccion_resultado():
    val_ronda = df[(df['Estado'] == 'Valuación - Global') & (df['Ronda'] == ronda_snapshot)].copy()
    cv_ronda = df[(df['Modulo'] == 'Creación de valor') & (df['Metrica'] == 'Valor total creado') & (df['Ronda'] == ronda_snapshot)].copy()
    
    cv_vals = {emp: valor_de(cv_ronda, empresa=emp) for emp in COMPANIES}
    prom_cv = np.nanmean([v for v in cv_vals.values() if v is not None])
    
    cap_vals = {emp: valor_de(val_ronda, metrica='Capitalización de mercado, miles USD', empresa=emp) for emp in COMPANIES}
    prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None])

    st.subheader('POSICIÓN FINANCIERA DIRECTIVA')
    c1, c2, c3 = st.columns(3)
    c1.metric('Creación de Valor', f'{cv_vals.get(empresa_analisis, 0):,.0f}', delta=f'{((cv_vals.get(empresa_analisis, 0) or 0) - prom_cv)/prom_cv*100:+.1f}% vs Prom' if prom_cv else None)
    
    ranking_orden = sorted([k for k, v in cv_vals.items() if v is not None], key=cv_vals.get, reverse=True)
    posicion = ranking_orden.index(empresa_analisis) + 1 if empresa_analisis in ranking_orden else '-'
    c2.metric('Ranking Global', f'{posicion}° de {len(ranking_orden)}')
    c3.metric('Market Cap', f'{cap_vals.get(empresa_analisis, 0):,.0f}', delta=f'{((cap_vals.get(empresa_analisis, 0) or 0) - prom_cap)/prom_cap*100:+.1f}% vs Prom' if prom_cap else None)

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        pl = df[(df['Estado'] == 'Cuenta de resultados, miles USD, Global') & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        def g(metrica): return pd.to_numeric(pl[pl['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not pl[pl['Metrica'] == metrica].empty else 0.0
        
        ingresos = g('Ingresos por ventas')
        costos_prod = g('Costos de fabricación interna') + g('Costos de la característica') + g('Costos de fabricación contratada')
        costos_op = g('Costos de transporte y aranceles') + g('I+D') + g('Promoción') + g('Administración')
        ben = g('Beneficio de la ronda')
        
        fig = go.Figure(go.Waterfall(
            orientation='v', measure=['absolute', 'relative', 'relative', 'total'],
            x=['Ingresos', '- Prod', '- Op/Admin', '= Neto'],
            y=[ingresos, -costos_prod, -costos_op, ben],
            text=[f'{v:,.0f}' for v in [ingresos, -costos_prod, -costos_op, ben]], textposition='outside',
            decreasing={'marker': {'color': MUTED_PALETTE[1]}}, increasing={'marker': {'color': BRAND_ACCENT}},
            totals={'marker': {'color': BRAND_ACCENT}}
        ))
        fig.update_layout(title='PUENTE DE BENEFICIO NETO')
        mostrar(fig, ocultar_eje_valores='y')

    with col_b:
        ranking = cv_ronda[['Empresa', 'Valor']].copy()
        ranking['Valor'] = num(ranking['Valor'])
        ranking = ranking.sort_values(by='Valor', ascending=True).dropna()
        fig = px.bar(ranking, x='Valor', y='Empresa', orientation='h', color='Empresa', color_discrete_map=COLOR_MAP, text_auto='.2s')
        fig.update_traces(textposition='outside', showlegend=False, cliponaxis=False)
        fig.update_layout(title='RANKING: CREACIÓN DE VALOR')
        mostrar(fig, ocultar_eje_valores='x')

# =================================================================
# SECCIÓN 2 — MERCADO
# =================================================================
def seccion_mercado():
    c1, c2 = st.columns(2)
    pais_sel = c1.selectbox('Mercado', ['EE.UU.', 'China', 'Europa'])
    tech_sel = c2.selectbox('Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

    estado_pais = f'Informe de mercado, {pais_sel}'
    sub = df[(df['Estado'] == estado_pais) & (df['Seccion'] == tech_sel) & (df['Ronda'] == ronda_snapshot)]
    
    # Fuzzy match para atrapar las ventas sin importar si dice "miles unidades" o "unidades RMB"
    ventas_data = []
    for emp in COMPANIES:
        val = valor_fuzzy(sub[sub['Empresa'] == emp], 'Ventas')
        if val is not None: ventas_data.append({'Empresa': emp, 'Ventas': val})
    ventas_df = pd.DataFrame(ventas_data)

    def scatter_posicionamiento(eje_x_metrica, titulo_x):
        eje_x = sub[sub['Metrica'] == eje_x_metrica][['Empresa', 'Valor']].rename(columns={'Valor': titulo_x})
        if ventas_df.empty or eje_x.empty: return None
        
        pos = eje_x.merge(ventas_df, on='Empresa')
        pos[titulo_x] = num(pos[titulo_x])
        pos = pos.dropna()
        if pos.empty: return None
        
        fig = px.scatter(pos, x=titulo_x, y='Ventas', color='Empresa', color_discrete_map=COLOR_MAP,
                         size=pos['Ventas'], text='Empresa', title=f'{titulo_x.upper()} VS VOLUMEN')
        fig.update_traces(textposition='top center', showlegend=False, textfont=dict(family='JetBrains Mono'))
        linea_media(fig, pos['Ventas'].mean(), eje='y')
        linea_media(fig, pos[titulo_x].mean(), eje='x')
        mostrar(fig)
        return True

    col_a, col_b = st.columns(2)
    with col_a: 
        if not scatter_posicionamiento('Precio de venta, USD', 'Precio'): st.info(f'Sin datos de precio para {tech_sel} en {pais_sel}.')
    with col_b: 
        scatter_posicionamiento('Cantidad de características ofrecidas', 'Características')

    st.divider()
    share_hist = df[(df['Estado'] == estado_pais) & (df['Seccion'] == f'{pais_sel} cuotas de mercado, %') & (df['Metrica'] == 'Total')].copy()
    share_hist['Valor'] = num(share_hist['Valor'])
    if not share_hist.empty:
        # Ordenamos las empresas para que CADIZ sea siempre la base del gráfico de áreas
        orden_empresas = [MY_COMPANY] + [c for c in COMPANIES if c != MY_COMPANY]
        fig = px.area(share_hist, x='Ronda', y='Valor', color='Empresa', color_discrete_map=COLOR_MAP,
                      category_orders={'Empresa': orden_empresas}, groupnorm='percent', title=f'INERCIA DE CUOTA DE MERCADO — {pais_sel.upper()}')
        fig.update_layout(yaxis_title='%', xaxis_title=None)
        mostrar(fig)

# =================================================================
# SECCIÓN 3 — OPERACIONES Y COSTOS
# =================================================================
def seccion_operaciones():
    c1, c2 = st.columns(2)
    pais_op = c1.selectbox('Operación País', ['EE.UU.', 'China', 'Europa'])
    tech_op = c2.selectbox('Operación Tecnología', ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno'])

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader('UNIT ECONOMICS (Margen Unitario Real)')
        margen = df[(df['Estado'] == f'Desglose de margen por tec, miles USD, {pais_op}') & 
                    (df['Seccion'] == tech_op) & (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        
        mercado = df[(df['Estado'] == f'Informe de mercado, {pais_op}') & (df['Seccion'] == tech_op) & 
                     (df['Empresa'] == empresa_analisis) & (df['Ronda'] == ronda_snapshot)]
        unidades = valor_fuzzy(mercado, 'Ventas')

        def gm(metrica): return pd.to_numeric(margen[margen['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not margen[margen['Metrica'] == metrica].empty else 0.0

        if not unidades or unidades <= 0:
            st.info(f'Sin ventas de {tech_op} en {pais_op}.')
        else:
            p_venta = gm('Ingresos por ventas') / unidades
            c_prod = -gm('Fabricación propia y por contrato') / unidades
            c_flete = -gm('Transporte y aranceles') / unidades
            c_caract = -gm('Costos de la característica') / unidades
            m_bruto = gm('Beneficio bruto') / unidades

            fig = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'total'],
                x=['Precio', '- Prod', '- Logística', '- Caract.', '= Margen'],
                y=[p_venta, c_prod, c_flete, c_caract, m_bruto],
                text=[f'{v:,.0f}' for v in [p_venta, c_prod, c_flete, c_caract, m_bruto]], textposition='outside',
                decreasing={'marker': {'color': MUTED_PALETTE[2]}}, increasing={'marker': {'color': MUTED_PALETTE[4]}},
                totals={'marker': {'color': BRAND_ACCENT}}
            ))
            mostrar(fig, ocultar_eje_valores='y')

    with col_b:
        st.subheader('PUENTE DE INVENTARIO FÍSICO')
        log = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) &
                 (df['Seccion'] == f'{tech_op}, miles unidades') & (df['Subgrupo'] == pais_op) & (df['Ronda'] == ronda_snapshot)]
        
        def l(metrica): return pd.to_numeric(log[log['Metrica'] == metrica]['Valor'].iloc[0], errors='coerce') if not log[log['Metrica'] == metrica].empty else 0.0
        
        inv_ini = l('Inventario inicial')
        prod = l('Producción interna') + l('Producción contratada')
        imp = l('Importado desde EE.UU.') + l('Importado desde China') + l('Importado desde Europa')
        ventas = abs(l(f'Ventas en {pais_op}'))
        exp = abs(l('Exportado a EE.UU.')) + abs(l('Exportado a China')) + abs(l('Exportado a Europa'))
        inv_fin = l('Inventario final')
        demanda_insat = l('Demanda insatisfecha')

        if prod == 0 and inv_ini == 0 and imp == 0:
            st.info('Sin actividad logística.')
        else:
            fig2 = go.Figure(go.Waterfall(
                orientation='v', measure=['absolute', 'relative', 'relative', 'relative', 'relative', 'total'],
                x=['Inv Inicial', '+ Prod', '+ Import', '- Ventas', '- Export', '= Inv Final'],
                y=[inv_ini, prod, imp, -ventas, -exp, inv_fin],
                text=[f'{v:,.0f}' for v in [inv_ini, prod, imp, -ventas, -exp, inv_fin]], textposition='outside',
                decreasing={'marker': {'color': MUTED_PALETTE[1]}}, increasing={'marker': {'color': MUTED_PALETTE[3]}},
                totals={'marker': {'color': BRAND_ACCENT}}
            ))
            mostrar(fig2, ocultar_eje_valores='y')
            
            if demanda_insat > 0 and 'm_bruto' in locals():
                perdida = demanda_insat * m_bruto
                st.error(f'⚠️ COSTO DE OPORTUNIDAD: Se perdieron **{perdida:,.0f} USD** de ganancia bruta por quiebre de stock ({demanda_insat:,.0f} unidades de demanda insatisfecha).')

    st.divider()
    st.subheader('MATRIZ TÉRMICA LOGÍSTICA (HEATMAP)')
    log_tech = df[(df['Estado'] == 'Detalles de logística') & (df['Empresa'] == empresa_analisis) & (df['Seccion'] == f'{tech_op}, miles unidades') & (df['Ronda'] == ronda_snapshot)]
    def val(planta, metrica):
        r = log_tech[(log_tech['Subgrupo'] == planta) & (log_tech['Metrica'] == metrica)]['Valor']
        return abs(pd.to_numeric(r.iloc[0], errors='coerce')) if len(r) else 0.0

    matriz = pd.DataFrame(0.0, index=['EE.UU.', 'China', 'Subcontratado'], columns=['EE.UU.', 'China', 'Europa'])
    
    for planta in ['EE.UU.', 'China']:
        interna = val(planta, 'Producción interna')
        contratada = val(planta, 'Producción contratada')
        total = interna + contratada
        flows = {d: val(planta, f'Ventas en {planta}' if d == planta else f'Exportado a {d}') for d in matriz.columns}
        if total > 0:
            for d in matriz.columns:
                matriz.loc[planta, d] += flows[d] * (interna/total)
                matriz.loc['Subcontratado', d] += flows[d] * (contratada/total)

    if matriz.sum().sum() > 0:
        fig3 = px.imshow(matriz.values, x=matriz.columns, y=matriz.index, text_auto='.0f', aspect='auto',
                         color_continuous_scale=[[0, 'rgba(0,0,0,0)'], [1, BRAND_ACCENT]])
        fig3.update_coloraxes(showscale=False)
        mostrar(fig3)
    else:
        st.info('Sin flujos para rastrear.')

# =================================================================
# SECCIÓN 4 — FINANZAS
# =================================================================
def seccion_finanzas():
    ratios = df[(df['Estado'] == 'Ratios e indicadores financieros clave') & (df['Ronda'] == ronda_snapshot)]
    
    def r(emp, met): return valor_de(ratios, metrica=met, empresa=emp)
    
    datos = {
        'ROS %': {e: r(e, 'Rentabilidad de las ventas (ROS)') for e in COMPANIES},
        'ROE %': {e: r(e, 'Rendimiento de los Fondos Propios (ROE)') for e in COMPANIES},
        'Apalancamiento': {e: r(e, 'Endeudamiento neto/patrimonio (apalancamiento)') for e in COMPANIES}
    }

    col_a, col_b = st.columns([1, 1.2])
    
    with col_a:
        st.subheader('MATRIZ RIESGO/RETORNO')
        apal_vals = datos['Apalancamiento']
        roe_vals = datos['ROE %']
        rr = pd.DataFrame({'Empresa': COMPANIES, 'Apalancamiento': [apal_vals.get(e) for e in COMPANIES], 'ROE': [roe_vals.get(e) for e in COMPANIES]}).dropna()
        
        if len(rr) > 1:
            fig = px.scatter(rr, x='Apalancamiento', y='ROE', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa')
            fig.update_traces(marker=dict(size=14), textposition='top center', showlegend=False, textfont=dict(family='JetBrains Mono'))
            linea_media(fig, rr['Apalancamiento'].mean(), eje='x')
            linea_media(fig, rr['ROE'].mean(), eje='y')
            mostrar(fig)
        else: st.info('Datos insuficientes.')

    with col_b:
        st.subheader('RANGO DE LA INDUSTRIA (BULLET)')
        ejes_validos = {k: v for k, v in datos.items() if len([x for x in v.values() if x is not None]) >= 2}
        if ejes_validos:
            fig2 = go.Figure()
            for i, (nombre, vals) in enumerate(ejes_validos.items()):
                valores = sorted(v for v in vals.values() if v is not None)
                v_min, v_max, v_med = valores[0], valores[-1], np.median(valores)
                v_cadiz = vals.get(empresa_analisis)
                
                # Pista base
                fig2.add_trace(go.Scatter(x=[v_min, v_max], y=[nombre, nombre], mode='lines', line=dict(color=MUTED_PALETTE[2], width=6), showlegend=False))
                # Mediana
                fig2.add_trace(go.Scatter(x=[v_med], y=[nombre], mode='markers', marker=dict(symbol='line-ns', size=20, color=MUTED_PALETTE[0], line_width=2), showlegend=False))
                # CADIZ
                if v_cadiz is not None:
                    fig2.add_trace(go.Scatter(x=[v_cadiz], y=[nombre], mode='markers', marker=dict(size=16, color=BRAND_ACCENT), showlegend=False))
            fig2.update_layout(height=300)
            mostrar(fig2)

# =================================================================
# SECCIÓN 5 — RRHH Y ESG
# =================================================================
def seccion_rrhh_sostenibilidad():
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader('SALARIOS VS ROTACIÓN')
        rrhh = df_all[(df_all['Estado'] == 'Informe de RRHH') & (df_all['Empresa'] == empresa_analisis)]
        salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
        rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
        
        salario['Valor'] = num(salario['Valor'])
        rotacion['Valor'] = num(rotacion['Valor'])

        if not salario.empty and not rotacion.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
            fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', line=dict(color=MUTED_PALETTE[1], width=2, dash='dash'), yaxis='y2'))
            
            # Ajuste de ejes para que no se pisen (escalas independientes forzadas a cero)
            fig.update_layout(
                yaxis=dict(title='Salario', rangemode='tozero', side='left'),
                yaxis2=dict(title='Rotación', rangemode='tozero', overlaying='y', side='right', showgrid=False),
                showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            mostrar(fig)

    with col_b:
        st.subheader('REPUTACIÓN ESG VS MERCADO')
        esg = df[(df['Estado'] == 'Informe ESG') & (df['Subgrupo'] == 'Puntuación final') & (df['Metrica'] == 'Reputación ESG') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']]
        esg['Valor'] = num(esg['Valor'])
        
        mkt = df[(df['Estado'] == 'Informe de mercado, Global') & (df['Seccion'] == 'Global cuotas de mercado, %') & (df['Metrica'] == 'Total') & (df['Ronda'] == ronda_snapshot)][['Empresa', 'Valor']].rename(columns={'Valor': 'Share'})
        mkt['Share'] = num(mkt['Share'])
        
        d = esg.merge(mkt, on='Empresa').dropna()
        if len(d) > 1:
            fig2 = px.scatter(d, x='Valor', y='Share', color='Empresa', color_discrete_map=COLOR_MAP, text='Empresa', labels={'Valor': 'Score ESG'})
            fig2.update_traces(textposition='top center', showlegend=False, textfont=dict(family='JetBrains Mono'))
            linea_media(fig2, d['Valor'].mean(), eje='x')
            linea_media(fig2, d['Share'].mean(), eje='y')
            mostrar(fig2)

# ---------------- Router ----------------
st.title(seccion)

if seccion == SECCIONES[0]: seccion_resultado()
elif seccion == SECCIONES[1]: seccion_mercado()
elif seccion == SECCIONES[2]: seccion_operaciones()
elif seccion == SECCIONES[3]: seccion_finanzas()
elif seccion == SECCIONES[4]: seccion_rrhh_sostenibilidad()
