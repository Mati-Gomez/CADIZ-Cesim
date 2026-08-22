import streamlit as st
import pandas as pd
import numpy as np

# Configuración inicial de la página
st.set_page_config(
    page_title="Tablero Directivo - Bull Automotive",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para limpiar la UI
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

# --- INGESTA SIMULADA ---
@st.cache_data
def cargar_datos():
    data = {
        'Métrica': ['Beneficio de la ronda', 'Ingresos por ventas', 'Total (Cuota de mercado global)', 'Rentabilidad de las ventas (ROS)'],
        'Valor': [7707447, 45915832, 18.5, 12.4],
        'Delta': [5.2, 10.1, -1.2, 0.5] 
    }
    return pd.DataFrame(data)

df = cargar_datos()

# --- BARRA LATERAL ---
st.sidebar.title("🎛️ Controles")
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", ["CADIZ", "CEOS", "CHIEF", "CLAVE"])
ronda_seleccionada = st.sidebar.slider("Ronda a analizar", min_value=1, max_value=12, value=1)

# --- TÍTULO PRINCIPAL ---
st.title(f"📊 Resumen Ejecutivo - Ronda {ronda_seleccionada}")
st.markdown(f"**Equipo Activo:** {equipo_seleccionado} | **Industria:** Automotriz Global")
st.divider()

# --- PESTAÑAS (Arquitectura modular) ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 High-Level KPIs", "🌍 Dinámica de Mercado", "⚙️ Operaciones & Costos", "🔬 I+D & Largo Plazo"])

with tab1:
    st.subheader("Indicadores Críticos del Negocio")
    
    col1, col2, col3, col4 = st.columns(4)
    
    beneficio = df.loc[df['Métrica'] == 'Beneficio de la ronda', 'Valor'].values[0] / 1000000
    delta_ben = df.loc[df['Métrica'] == 'Beneficio de la ronda', 'Delta'].values[0]
    col1.metric("Beneficio Neto (USD)", f"${beneficio:.2f}M", f"{delta_ben}%")
    
    ventas = df.loc[df['Métrica'] == 'Ingresos por ventas', 'Valor'].values[0] / 1000000
    delta_ven = df.loc[df['Métrica'] == 'Ingresos por ventas', 'Delta'].values[0]
    col2.metric("Ingresos Totales (USD)", f"${ventas:.2f}M", f"{delta_ven}%")
    
    share = df.loc[df['Métrica'] == 'Total (Cuota de mercado global)', 'Valor'].values[0]
    delta_share = df.loc[df['Métrica'] == 'Total (Cuota de mercado global)', 'Delta'].values[0]
    col3.metric("Cuota de Mercado Global", f"{share}%", f"{delta_share}%", delta_color="inverse" if delta_share < 0 else "normal")
    
    ros = df.loc[df['Métrica'] == 'Rentabilidad de las ventas (ROS)', 'Valor'].values[0]
    delta_ros = df.loc[df['Métrica'] == 'Rentabilidad de las ventas (ROS)', 'Delta'].values[0]
    col4.metric("Margen ROS", f"{ros}%", f"{delta_ros}%")
    
    st.markdown("---")
    st.markdown("#### 🚨 Alertas Operativas (Fallas de Stock)")
    st.info("Espacio reservado para el seguimiento de Demanda Insatisfecha.")

with tab2:
    st.write("Sensibilidad de mercado por región (Precios, Promoción y Características).")
with tab3:
    st.write("Análisis de estructura de costos, aranceles y capacidad de planta.")
with tab4:
    st.write("Tracking de inversión y transición hacia nuevas tecnologías (Híbridos, EV, Hidrógeno).")
