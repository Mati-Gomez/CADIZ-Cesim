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

# --- 2. MOTOR DE INGESTA DE DATOS (Parser) ---
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
                    'Ronda': ronda_nro,
                    'Sección': seccion_principal,
                    'Grupo': grupo if pd.notna(grupo) else seccion_principal,
                    'Métrica': met,
                    'Equipo': equipo,
                    'Valor': pd.to_numeric(val, errors='coerce') 
                })
                
    df_final = pd.DataFrame(parsed_data)
    df_final = df_final.dropna(subset=['Valor']).copy()
    
    return df_final

# Cargamos la ronda de práctica 1
try:
    df = limpiar_y_unpivot_cesim('results-pr01.xls', 1)
except Exception as e:
    st.error(f"Error al cargar el Excel: {e}")
    st.stop()

# --- 3. BARRA LATERAL ---
st.sidebar.title("🎛️ Controles")
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", ["CADIZ", "CEOS", "CHIEF", "CLAVE", "CUORE", "FOCUS", "TOKIO"])
# Si tuvieras más rondas, acá concatenarías los dataframes. Por ahora fijamos la 1.
ronda_seleccionada = 1 

# --- 4. EXTRACCIÓN SEGURA DE KPIs ---
def extraer_kpi(df_datos, equipo, metrica, seccion_clave):
    """Filtra el DF asegurando que trae la métrica de la sección correcta."""
    filtro = df_datos[
        (df_datos['Equipo'] == equipo) & 
        (df_datos['Métrica'] == metrica) & 
        (df_datos['Sección'].astype(str).str.contains(seccion_clave, case=False, na=False))
    ]
    return filtro['Valor'].values[0] if not filtro.empty else 0

# --- CÁLCULO DE KPIs PARA EL EQUIPO SELECCIONADO ---
# Beneficio Global
ben_val = extraer_kpi(df, equipo_seleccionado, 'Beneficio de la ronda', 'Cuenta de resultados, miles USD, Global')
# Ingresos Globales
ven_val = extraer_kpi(df, equipo_seleccionado, 'Ingresos por ventas', 'Cuenta de resultados, miles USD, Global')

# Share Global (Acá redondeamos a 1 decimal)
share_val = extraer_kpi(df, equipo_seleccionado, 'Total', 'Informe de mercado, global')
share_val = round(share_val, 1) if share_val != 0 else 0

# ROS (Corregimos la palabra clave de búsqueda a 'Ratios' y redondeamos)
ros_val = extraer_kpi(df, equipo_seleccionado, 'Rentabilidad de las ventas (ROS)', 'Ratios')
ros_val = round(ros_val, 1) if ros_val != 0 else 0

# Deltas temporales (Ronda 1 = 0)
delta_ben = 0.0
delta_ven = 0.0
delta_share = 0.0
delta_ros = 0.0
