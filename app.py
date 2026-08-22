import streamlit as st
import pandas as pd
import numpy as np

# --- 1. CONFIGURACIÓN DE PÁGINA Y UI ---
st.set_page_config(
    page_title="Tablero Directivo - Bull Automotive",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00E676;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE INGESTA DE DATOS ---
@st.cache_data
def limpiar_y_unpivot_cesim(ruta_archivo, ronda_nro):
    df_raw = pd.read_excel(ruta_archivo, header=None)
    fila_equipos_idx = None
    for i, row in df_raw.iterrows():
        if 'CADIZ' in row.values:
            fila_equipos_idx = i
            break
    if fila_equipos_idx is None:
        raise ValueError("No se encontró la fila con los nombres de los equipos (CADIZ).")
        
    nombres_equipos = [x for x in df_raw.iloc[fila_equipos_idx].values if pd.notna(x) and str(x).strip() != '']
    
    parsed_data = []
    seccion_principal = pd.NA
    grupo = pd.NA
    
    for i, row in df_raw.iterrows():
        met = str(row[0]).strip()
        if met == 'nan' or met == '' or i == fila_equipos_idx or i == 0:
            continue
            
        vals = row[1:len(nombres_equipos)+1]
        if vals.isnull().all() or vals.astype(str).str.strip().eq('').all():
            keywords_seccion = ['cuenta de', 'hoja de', 'informe', 'clasificación', 'valuación', 'creación de', 'sostenibilidad', 'ratios', 'flujo de efectivo', 'detalles de']
            if any(kw in met.lower() for kw in keywords_seccion) or i < fila_equipos_idx:
                seccion_principal = met
                grupo = pd.NA 
            else:
                grupo = met 
        else:
            for equipo, val in zip(nombres_equipos, vals):
                parsed_data.append({
                    'Ronda': ronda_nro, 'Sección': seccion_principal,
                    'Grupo': grupo if pd.notna(grupo) else seccion_principal,
                    'Métrica': met, 'Equipo': equipo,
                    'Valor': pd.to_numeric(val, errors='coerce') 
                })
                
    df_final = pd.DataFrame(parsed_data)
    return df_final.dropna(subset=['Valor']).copy()

try:
    df = limpiar_y_unpivot_cesim('results-pr01.xls', 1)
except Exception as e:
    st.error(f"Error al cargar el Excel: {e}")
    st.stop()

# --- 3. BARRA LATERAL ---
st.sidebar.title("🎛️ Controles")
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", ["CADIZ", "CEOS", "CHIEF", "CLAVE", "CUORE", "FOCUS", "TOKIO"])
ronda_seleccionada = 1 

# --- 4. EXTRACCIÓN SEGURA DE KPIs ---
def extraer_kpi(df_datos, equipo, metrica, seccion_clave):
    filtro = df_datos[
        (df_datos['Equipo'] == equipo) & 
        (df_datos['Métrica'] == metrica) & 
        (df_datos['Sección'].astype(str).str.contains(seccion_clave, case=False, na=False))
    ]
    return filtro['Valor'].values[0] if not filtro.empty else 0

# --- 5. RENDERIZADO DEL DASHBOARD ---
st.title(f"📊 Resumen Ejecutivo - Ronda {ronda_seleccionada}")
st.markdown(f"**Equipo Activo:** {equipo_seleccionado} | **Industria:** Automotriz")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["🚀 High-Level KPIs", "🌍 Dinámica de Mercado", "⚙️ Operaciones & Costos", "🔬 I+D & Largo Plazo"])

with tab1:
    st.subheader("Indicadores Críticos del Negocio")
    
    # --- SELECTOR REGIONAL ---
    region = st.radio(
        "Filtro de Análisis Regional:",
        ["Global", "EE.UU.", "Europa", "China"],
        horizontal=True
    )
    
    # Mapeo de sufijos para buscar en las secciones del Excel
    sufijo_finanzas = "Global" if region == "Global" else region
    sufijo_mercado = "global" if region == "Global" else region

    # Cálculos dinámicos basados en la región elegida
    ben_val = extraer_kpi(df, equipo_seleccionado, 'Beneficio de la ronda', f'Cuenta de resultados, miles USD, {sufijo_finanzas}')
    ven_val = extraer_kpi(df, equipo_seleccionado, 'Ingresos por ventas', f'Cuenta de resultados, miles USD, {sufijo_finanzas}')
    
    share_val = extraer_kpi(df, equipo_seleccionado, 'Total', f'Informe de mercado, {sufijo_mercado}')
    share_val = round(share_val, 1) if share_val != 0 else 0
    
    # El ROS siempre se extrae de 'Ratios' para la visión Global. 
    # Para la visión regional, usamos el Margen de Contribución de Combustión como proxy rápido (luego se puede complejizar)
    if region == "Global":
        margen_val = extraer_kpi(df, equipo_seleccionado, 'Rentabilidad de las ventas (ROS)', 'Ratios')
        titulo_margen = "Margen ROS"
    else:
        margen_val = extraer_kpi(df, equipo_seleccionado, 'Margen de contribución', f'Desglose de margen por tec, miles USD, {region}')
        # Convertimos el margen absoluto a % sobre las ventas regionales
        margen_val = (margen_val / ven_val) * 100 if ven_val > 0 else 0
        titulo_margen = "Margen Contribución (Combustión)"
        
    margen_val = round(margen_val, 1) if margen_val != 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(f"Beneficio Neto ({region})", f"${ben_val / 1000000:.2f}M")
    col2.metric(f"Ingresos ({region})", f"${ven_val / 1000000:.2f}M")
    col3.metric(f"Cuota de Mercado ({region})", f"{share_val}%")
    col4.metric(titulo_margen, f"{margen_val}%")
    
    st.markdown("---")
    st.info("Espacio reservado para Gráficos de barra apiladas comparativos.")

with tab2:
    st.write("Acá cruzamos elasticidad de precio y promoción vs share de mercado (Scatter Plots).")
with tab3:
    st.write("Análisis de estructura de costos, aranceles y capacidad de planta.")
with tab4:
    st.write("Tracking de inversión y transición hacia nuevas tecnologías (Híbridos, EV, Hidrógeno).")
