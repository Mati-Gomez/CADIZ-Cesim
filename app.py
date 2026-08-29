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
                       font=dict(color=BRAND_LIGHT if oscuro else BRAND_DARK, family='Inter, sans-serif'),
                       title_font=dict(family='Inter, sans-serif', size=14, weight=600),
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

    # --- Expansión de capacidad de la industria: Cesim publica las fábricas que va a haber
    #     después de la próxima ronda, así que se sabe de antemano quién está por agrandarse.
    # OJO con la forma del reporte: Cesim pone el PAÍS en 'Metrica' (EE.UU. / China) y el
    # HORIZONTE en 'Subgrupo' (Ronda actual / Próxima ronda / Después de la próxima ronda).
    # Filtrando al revés no matchea nada y el conteo actual daba 0.
    fab = df[(df['Estado'] == 'Detalles de fabricación') & (df['Seccion'] == 'Número de fábricas') &
             (df['Ronda'] == ronda_snapshot)].copy()
    if not fab.empty:
        fab['Valor'] = num(fab['Valor'])
        act = fab[fab['Subgrupo'] == 'Ronda actual'].groupby('Empresa')['Valor'].sum()
        fut = fab[fab['Subgrupo'] == 'Después de la próxima ronda'].groupby('Empresa')['Valor'].sum()
        expansiones = [f'{e}: {act.get(e, 0):.0f} → {fut.get(e, 0):.0f}'
                       for e in COMPANIES if fut.get(e, 0) > act.get(e, 0)]
        if expansiones:
            alertas.append(('aviso', 'Expansión de capacidad planificada (próximas 2 rondas)',
                            ' · '.join(expansiones)))
    return alertas

def panel_alertas():
    alertas = evaluar_alertas()
    if not alertas:
        st.markdown('<div class="alerta-fila ok">✅ <b>Sin alertas</b> '
                    f'<span class="detalle">— nada fuera de rango en {ronda_snapshot} para {empresa_analisis}.</span></div>',
                    unsafe_allow_html=True)
        return
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
filtro_tipo = st.sidebar.radio('Ecosistema', ['Práctica', 'Oficial'], horizontal=True, key='filtro_ecosistema')
rondas_timeline = ['Práctica 1', 'Práctica 2', 'Práctica 3'] if filtro_tipo == 'Práctica' else [f'Ronda {i}' for i in range(1, 13)]
ronda_snapshot = st.sidebar.select_slider('Ronda de análisis', options=rondas_timeline, value=rondas_timeline[0], key='slider_rondas')
empresa_analisis = st.sidebar.selectbox('Equipo en foco', COMPANIES, index=0, key='select_equipo')
st.sidebar.divider()
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
    # Títulos cortos: los largos se cortaban con puntos suspensivos y no se entendía qué métrica era.
    c1, c2, c3, c4, c5 = st.columns(5)
    prom_ret_acum = np.nanmean([v for v in retorno_acum_vals.values() if v is not None]) if any(v is not None for v in retorno_acum_vals.values()) else None
    val_ret_acum = retorno_acum_vals.get(empresa_analisis)
    delta_ret_acum = ((val_ret_acum - prom_ret_acum) / abs(prom_ret_acum) * 100) if prom_ret_acum and val_ret_acum is not None else None
    kpi_con_tendencia(c1, 'Retorno acumulado', f'{val_ret_acum:,.1f}%' if val_ret_acum is not None else '—',
                       serie_metrica('Ratios e indicadores financieros clave', 'Retorno total acumulado del accionista (p.a.), %', empresa_analisis),
                       delta=f'{delta_ret_acum:+.1f}% vs Prom' if delta_ret_acum is not None else None)

    ranking_acum = sorted([e for e in retorno_acum_vals if retorno_acum_vals.get(e) is not None], key=retorno_acum_vals.get, reverse=True)
    pos = ranking_acum.index(empresa_analisis) + 1 if empresa_analisis in ranking_acum else '-'
    ret_hist = df_all[(df_all['Estado'] == 'Ratios e indicadores financieros clave') &
                       (df_all['Metrica'] == 'Retorno total acumulado del accionista (p.a.), %')].copy()
    ret_hist['Valor'] = num(ret_hist['Valor'])
    puestos_hist = ret_hist.dropna(subset=['Valor']).copy()
    puestos_hist['Puesto'] = puestos_hist.groupby('Ronda')['Valor'].rank(ascending=False, method='min')
    serie_puesto = puestos_hist[puestos_hist['Empresa'] == empresa_analisis].sort_values('Ronda_Orden')['Puesto'].tolist()
    # invertir: en el ranking, "para arriba" en el gráfico tiene que ser mejorar de puesto
    kpi_con_tendencia(c2, 'Posición en el ranking', f'{pos}° de {len(COMPANIES)}', serie_puesto, invertir=True)

    prom_cv = np.nanmean([v for v in cv_vals.values() if v is not None]) if any(v is not None for v in cv_vals.values()) else None
    val_cv = cv_vals.get(empresa_analisis)
    delta_cv = ((val_cv - prom_cv)/prom_cv*100) if prom_cv and val_cv is not None else None
    kpi_con_tendencia(c3, 'Beneficio del accionista', format_num(val_cv),
                       serie_metrica('Creación de valor, miles USD', 'Total', empresa_analisis, seccion='Accionistas'),
                       delta=f'{delta_cv:+.1f}% vs Prom' if delta_cv is not None else None)

    prom_cap = np.nanmean([v for v in cap_vals.values() if v is not None]) if any(v is not None for v in cap_vals.values()) else None
    val_cap = cap_vals.get(empresa_analisis)
    delta_cap = ((val_cap - prom_cap)/prom_cap*100) if prom_cap and val_cap else None
    kpi_con_tendencia(c4, 'Market Cap (USD)', format_num(val_cap),
                       serie_metrica('Valuación - Global', 'Capitalización de mercado, miles USD', empresa_analisis),
                       delta=f'{delta_cap:+.1f}% vs Prom' if delta_cap else None)

    prom_ret_ronda = np.nanmean([v for v in retorno_ronda_vals.values() if v is not None]) if any(v is not None for v in retorno_ronda_vals.values()) else None
    val_ret_ronda = retorno_ronda_vals.get(empresa_analisis)
    delta_ret_ronda = ((val_ret_ronda - prom_ret_ronda) / abs(prom_ret_ronda) * 100) if prom_ret_ronda and val_ret_ronda is not None else None
    kpi_con_tendencia(c5, 'Retorno de la acción',
                       f'{val_ret_ronda:+,.1f}%' if val_ret_ronda is not None else 'Sin ronda previa',
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
    tab_pos, tab_pan, tab_evo = st.tabs(['Posicionamiento', 'Panorama Competitivo', 'Evolución'])
    tecnologias = ['Combustión', 'Híbrido', 'Eléctrico', 'Hidrógeno']

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

        st.markdown('**Demanda total vs. ventas totales de la industria**')
        st.caption('Toda la torta del mercado (7 equipos sumados): la brecha entre demanda y ventas es oportunidad que nadie capturó.')
        dv_rows = []
        for tech in tecnologias:
            dem = df[(df['Estado'] == estado_evo) & (df['Seccion'] == tech) & (df['Metrica'] == 'Demanda, miles unidades')].copy()
            ven = df[(df['Estado'] == estado_evo) & (df['Seccion'] == tech) & (df['Metrica'] == 'Ventas, miles unidades')].copy()
            dem['Valor'] = num(dem['Valor']); ven['Valor'] = num(ven['Valor'])
            for ronda, grupo in dem.groupby('Ronda'):
                dv_rows.append({'Ronda': ronda, 'Ronda_Orden': grupo['Ronda_Orden'].iloc[0], 'Tipo': 'Demanda', 'Valor': grupo['Valor'].sum()})
            for ronda, grupo in ven.groupby('Ronda'):
                dv_rows.append({'Ronda': ronda, 'Ronda_Orden': grupo['Ronda_Orden'].iloc[0], 'Tipo': 'Ventas', 'Valor': grupo['Valor'].sum()})
        dv_df = pd.DataFrame(dv_rows)
        if not dv_df.empty:
            dv_piv = dv_df.groupby(['Ronda', 'Ronda_Orden', 'Tipo'])['Valor'].sum().reset_index().sort_values('Ronda_Orden')
            fig_dv = go.Figure()
            for tipo, color in [('Demanda', MUTED_PALETTE[0]), ('Ventas', BRAND_ACCENT)]:
                d_t = dv_piv[dv_piv['Tipo'] == tipo]
                fig_dv.add_trace(go.Bar(x=d_t['Ronda'], y=d_t['Valor'], name=tipo, marker_color=color))
            fig_dv.update_layout(barmode='group', title=f'Demanda vs. Ventas — industria, {pais_evo}')
            mostrar(fig_dv)
        else:
            st.info('Sin datos suficientes.')

        st.divider()
        st.markdown(f'**Evolución de la cuota de mercado — {pais_evo}**')
        st.caption('Los 7 equipos, CADIZ resaltado. Complementa el gráfico de abajo: acá se ve el resultado, abajo la jugada (precio/características) que lo explica.')
        share_hist = df[(df['Estado'] == estado_evo) & (df['Seccion'] == f'{pais_evo} cuotas de mercado, %') &
                         (df['Metrica'].str.strip() == 'Total')].copy()
        chart_evolucion(share_hist, f'Cuota de mercado, % — {pais_evo}')

        st.divider()
        st.markdown(f'**Trayectoria de {empresa_analisis}: precio y características en el tiempo**')
        tech_traj = st.selectbox('Tecnología', tecnologias, key='sel_evo_tech')
        traj = df[(df['Estado'] == estado_evo) & (df['Seccion'] == tech_traj) & (df['Empresa'] == empresa_analisis) &
                  (df['Metrica'].isin(['Precio de venta, USD', 'Cantidad de características ofrecidas']))].copy()
        traj['Valor'] = num(traj['Valor'])
        traj = traj.dropna(subset=['Valor']).sort_values('Ronda_Orden')
        if not traj.empty:
            precio_t = traj[traj['Metrica'] == 'Precio de venta, USD']
            caract_t = traj[traj['Metrica'] == 'Cantidad de características ofrecidas']
            fig_traj = go.Figure()
            fig_traj.add_trace(go.Scatter(x=precio_t['Ronda'], y=precio_t['Valor'], name='Precio, USD', mode='lines+markers',
                                           line=dict(color=BRAND_ACCENT, width=3), yaxis='y1'))
            fig_traj.add_trace(go.Scatter(x=caract_t['Ronda'], y=caract_t['Valor'], name='Características', mode='lines+markers',
                                           line=dict(color=MUTED_PALETTE[0], width=3, dash='dot'), yaxis='y2'))
            fig_traj.update_layout(title=f'{empresa_analisis} — {tech_traj}, {pais_evo}',
                                    yaxis=dict(title='Precio, USD', side='left', rangemode='tozero'),
                                    yaxis2=dict(title='Características', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                    legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
            mostrar(fig_traj)
        else:
            st.info(f'{empresa_analisis} no tiene datos de {tech_traj} en {pais_evo}.')
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
                uso = float(row['Valor'])
                # El semicírculo gastaba media pantalla para mostrar un solo número, y el
                # "gauge+number" recortaba el valor con height=220. Una barra horizontal
                # comunica lo mismo, entra en un tercio del espacio y deja leer el número.
                # Sin semáforo: no hay un rango "sano" publicado por Cesim, así que poner
                # umbrales propios sería inventar un criterio que el reporte no da.
                with col:
                    with st.container(border=True):
                        st.markdown(f'**Capacidad empleada — {titulo}**')
                        st.markdown(
                            f'<div style="display:flex;align-items:baseline;gap:10px;margin:2px 0 8px">'
                            f'<span style="font-size:1.9rem;font-weight:700;color:{BRAND_ACCENT}">{uso:,.1f}%</span>'
                            f'<span style="opacity:0.6;font-size:0.85rem">de la capacidad instalada</span></div>'
                            f'<div style="background:rgba(128,128,128,0.18);border-radius:999px;height:10px;width:100%">'
                            f'<div style="background:{BRAND_ACCENT};border-radius:999px;height:10px;'
                            f'width:{min(uso, 100):.1f}%"></div></div>',
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
            fig = go.Figure(go.Funnel(y=[e[0] for e in etapas], x=[e[1] for e in etapas], textinfo='value+percent initial', marker={'color': colores}))
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

    def delta_str(vals, empresa=empresa_analisis):
        # Mismo cálculo que el resto de la app: % de distancia contra el promedio de los 7 equipos.
        prom = np.nanmean([v for v in vals.values() if v is not None]) if any(v is not None for v in vals.values()) else None
        val = vals.get(empresa)
        if prom in (None, 0) or val is None:
            return None
        d = (val - prom) / abs(prom) * 100
        return f'{d:+.1f}% vs Prom'

    f1, f2, f3, f4 = st.columns(4)
    with f1: st.metric('EBITDA (USD)', format_num(ebitda_vals.get(empresa_analisis)), delta=delta_str(ebitda_vals))
    with f2: st.metric('Margen bruto', f"{margen_vals.get(empresa_analisis):,.1f}%" if pd.notna(margen_vals.get(empresa_analisis)) else '—', delta=delta_str(margen_vals))
    with f3: st.metric('ROS', f"{ros_vals.get(empresa_analisis):,.1f}%" if pd.notna(ros_vals.get(empresa_analisis)) else '—', delta=delta_str(ros_vals))
    with f4: st.metric('Caja final (USD)', format_num(caja_vals.get(empresa_analisis)) if pd.notna(caja_vals.get(empresa_analisis)) else '—', delta=delta_str(caja_vals))
    f5, f6, f7, _f8 = st.columns(4)
    with f5: st.metric('Deuda CP no planificada (USD)', format_num(val_deuda_cp) if val_deuda_cp is not None else '—',
                        delta=delta_str(deuda_cp_vals), delta_color='inverse')
    with f6: st.metric('Deuda LP (USD)', format_num(deuda_lp_vals.get(empresa_analisis)), delta=delta_str(deuda_lp_vals), delta_color='inverse')
    with f7: st.metric('Calificación crediticia', calif_val if calif_val else '—')
    st.write('')

    tab_cp, tab_lp = st.tabs(['Corto Plazo: Liquidez y Operación', 'Largo Plazo: Estructura, Retorno y Competencia'])

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
                fig = go.Figure()
                fig.add_trace(go.Bar(x=ben['Ronda'], y=ben['Valor'], name='Beneficio (USD)', marker_color=COLOR_POSITIVE, yaxis='y1', width=0.15))
                fig.add_trace(go.Scatter(x=deuda['Ronda'], y=deuda['Valor'], name='Apalancamiento (x)', mode='lines+markers', line=dict(color=MUTED_PALETTE[1], width=3), yaxis='y2'))
                fig.update_layout(title='Beneficio Neto vs. Nivel de Deuda',
                                  yaxis=dict(title='Beneficio (USD)', side='left', rangemode='tozero'),
                                  yaxis2=dict(title='Apalancamiento (x)', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                  legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
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
            st.subheader('Salario y rotación')
            salario = rrhh[rrhh['Metrica'] == 'Salario mensual, USD'].sort_values('Ronda_Orden')
            rotacion = rrhh[rrhh['Metrica'] == 'Rotación de personal, %'].sort_values('Ronda_Orden')
            if not salario.empty and not rotacion.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=salario['Ronda'], y=salario['Valor'], name='Salario (USD)', mode='lines+markers', line=dict(color=COLOR_METRICA['dinero'], width=3), yaxis='y1'))
                fig.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers', line=dict(color=COLOR_METRICA['riesgo'], width=2, dash='dash'), yaxis='y2'))
                # El eje fijo en 0-20 dejaba la línea pegada al piso cuando la rotación anda en 2-5%.
                max_rot = (rotacion['Valor'].max() * 1.4) if rotacion['Valor'].notna().any() else 20
                max_sal = (salario['Valor'].max() * 1.25) if salario['Valor'].notna().any() else 6000
                fig.update_layout(title='Evolución: Salario vs Rotación',
                                  yaxis=dict(title='Salario (USD)', range=[0, max_sal], rangemode='tozero', side='left'),
                                  yaxis2=dict(title='Rotación (%)', range=[0, max_rot], overlaying='y', side='right', showgrid=False),
                                  legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
                mostrar(fig)
        with col_b:
            st.subheader('Rotación y contrataciones')
            contrat = rrhh[rrhh['Metrica'] == 'Contrataciones + / despidos -'].sort_values('Ronda_Orden')
            if not salario.empty and not contrat.empty and not rotacion.empty:
                fig_ch = go.Figure()
                fig_ch.add_trace(go.Bar(x=contrat['Ronda'], y=contrat['Valor'], name='Contrataciones netas (personas)',
                                         marker_color=COLOR_METRICA['personas'], yaxis='y1'))
                fig_ch.add_trace(go.Scatter(x=rotacion['Ronda'], y=rotacion['Valor'], name='Rotación (%)', mode='lines+markers',
                                             line=dict(color=COLOR_METRICA['riesgo'], width=3), yaxis='y2'))
                fig_ch.update_layout(title='Rotación vs. Contrataciones netas',
                                      yaxis=dict(title='Personas', side='left', rangemode='tozero'),
                                      yaxis2=dict(title='Rotación, %', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                      legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
                mostrar(fig_ch)
                st.caption('Cuántas contrataciones netas hizo falta hacer, en la misma ronda en que se dio la rotación.')

        st.divider()
        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader('Inversión en I+D')
            idn = rrhh[rrhh['Metrica'] == 'Número de personal de I+D, esta ronda'].sort_values('Ronda_Orden')
            idc = rrhh[rrhh['Metrica'] == 'Otros costos variables de I + D'].sort_values('Ronda_Orden')
            if not idn.empty and not idc.empty:
                fig_id = go.Figure()
                fig_id.add_trace(go.Bar(x=idc['Ronda'], y=idc['Valor'], name='Costo variable I+D (USD)',
                                         marker_color=COLOR_METRICA['dinero'], yaxis='y1'))
                fig_id.add_trace(go.Scatter(x=idn['Ronda'], y=idn['Valor'], name='Personal I+D (headcount)', mode='lines+markers',
                                             line=dict(color=COLOR_METRICA['personas'], width=3), yaxis='y2'))
                fig_id.update_layout(title='Inversión en I+D: costo vs. dotación',
                                      yaxis=dict(title='Costo variable, USD', side='left', rangemode='tozero'),
                                      yaxis2=dict(title='Personal I+D', overlaying='y', side='right', showgrid=False, rangemode='tozero'),
                                      legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
                mostrar(fig_id)
            else:
                st.info('Sin datos de I+D para este equipo.')
        with col_d:
            st.subheader('Capacitación e impacto')
            capac = rrhh[rrhh['Metrica'] == 'Presupuesto mensual para capacitación, USD'].sort_values('Ronda_Orden')
            efic = rrhh[rrhh['Metrica'] == 'Multiplicador de la eficiencia de RRHH'].sort_values('Ronda_Orden')
            if not capac.empty and not efic.empty:
                fig_cap = go.Figure()
                fig_cap.add_trace(go.Bar(x=capac['Ronda'], y=capac['Valor'], name='Presupuesto capacitación (USD)',
                                          marker_color=COLOR_METRICA['dinero'], yaxis='y1'))
                fig_cap.add_trace(go.Scatter(x=efic['Ronda'], y=efic['Valor'], name='Multiplicador eficiencia RRHH', mode='lines+markers',
                                              line=dict(color=COLOR_METRICA['eficiencia'], width=3), yaxis='y2'))
                fig_cap.update_layout(title='Capacitación vs. eficiencia de RRHH',
                                       yaxis=dict(title='Presupuesto, USD', side='left', rangemode='tozero'),
                                       yaxis2=dict(title='Multiplicador eficiencia', overlaying='y', side='right', showgrid=False),
                                       legend=dict(orientation="h", yanchor="top", y=-0.30, xanchor="center", x=0.5))
                mostrar(fig_cap)
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
