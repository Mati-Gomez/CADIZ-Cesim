# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuración inicial de la página
st.set_page_config(
    page_title="Tablero Directivo - Bull Automotive",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyectamos algo de CSS para limpiar la UI y que quede estético (tu estilo)
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

# --- FUNCIÓN DE INGESTA (Acá va tu función a prueba de balas) ---
@st.cache_data
def cargar_datos():
    # Simulamos que ya tenés el DataFrame limpio usando la función que armamos antes
    # En tu archivo real, acá ejecutás `limpiar_y_unpivot_cesim()`
    
    # --- Datos Simulados para la Maqueta Visual ---
    data = {
        'Métrica': ['Beneficio de la ronda', 'Ingresos por ventas', 'Total (Cuota de mercado global)', 'Rentabilidad de las ventas (ROS)'],
        'Valor': [7707447, 45915832, 18.5, 12.4],
        'Delta': [5.2, 10.1, -1.2, 0.5] # Crecimiento vs Ronda Anterior
    }
    return pd.DataFrame(data)

df = cargar_datos()

# --- BARRA LATERAL (Filtros) ---
st.sidebar.title("🎛️ Controles")
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", ["CADIZ", "CEOS", "CHIEF", "CLAVE"])
ronda_seleccionada = st.sidebar.slider("Ronda a analizar", min_value=1, max_value=12, value=1)

# --- TÍTULO PRINCIPAL ---
st.title(f"📊 Resumen Ejecutivo - Ronda {ronda_seleccionada}")
st.markdown(f"**Equipo Activo:** {equipo_seleccionado} | **Industria:** Automotriz Global")
st.divider()

# --- PESTAÑAS (La arquitectura modular) ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 High-Level KPIs", "🌍 Dinámica de Mercado", "⚙️ Operaciones & Costos", "🔬 I+D & Largo Plazo"])

# --- PESTAÑA 1: Resumen Ejecutivo ---
with tab1:
    st.subheader("Indicadores Críticos del Negocio")
    
    # Armamos 4 columnas para las tarjetas de KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    # KPI 1: Beneficio (El bottom line)
    # Formateamos a millones para no marear con decimales
    beneficio = df.loc[df['Métrica'] == 'Beneficio de la ronda', 'Valor'].values[0] / 1000000
    delta_ben = df.loc[df['Métrica'] == 'Beneficio de la ronda', 'Delta'].values[0]
    col1.metric("Beneficio Neto (USD)", f"${beneficio:.2f}M", f"{delta_ben}%", help="Beneficio después de impuestos.")
    
    # KPI 2: Ventas
    ventas = df.loc[df['Métrica'] == 'Ingresos por ventas', 'Valor'].values[0] / 1000000
    delta_ven = df.loc[df['Métrica'] == 'Ingresos por ventas', 'Delta'].values[0]
    col2.metric("Ingresos Totales (USD)", f"${ventas:.2f}M", f"{delta_ven}%", help="Facturación global.")
    
    # KPI 3: Market Share Global
    share = df.loc[df['Métrica'] == 'Total (Cuota de mercado global)', 'Valor'].values[0]
    delta_share = df.loc[df['Métrica'] == 'Total (Cuota de mercado global)', 'Delta'].values[0]
    col3.metric("Cuota de Mercado Global", f"{share}%", f"{delta_share}%", delta_color="inverse" if delta_share < 0 else "normal")
    
    # KPI 4: Rentabilidad (ROS)
    ros = df.loc[df['Métrica'] == 'Rentabilidad de las ventas (ROS)', 'Valor'].values[0]
    delta_ros = df.loc[df['Métrica'] == 'Rentabilidad de las ventas (ROS)', 'Delta'].values[0]
    col4.metric("Margen ROS", f"{ros}%", f"{delta_ros}%", help="Rentabilidad operativa sobre ventas.")
    
    st.markdown("---")
    
    # Espacio para el gráfico principal de esta pestaña (Ej: Evolución de la demanda insatisfecha)
    st.markdown("#### 🚨 Alertas Operativas (Fallas de Stock)")
    st.info("Acá iría un gráfico de barras apiladas mostrando la Demanda Insatisfecha por región. Recordá que el caso advierte que han perdido ventas por ser demasiado cautelosos con los inventarios.")

# --- ESPACIOS PARA LAS OTRAS PESTAÑAS ---
with tab2:
    st.write("Cruce de precios vs. cuota de mercado regional. Sensibilidad a promoción en EE.UU. y precios en China.")
with tab3:
    st.write("Análisis de costos logísticos, aranceles e ineficiencias de planta.")
with tab4:
    st.write("Tracking de transición hacia híbridos y eléctricos.")
