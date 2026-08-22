import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Tablero Directivo - Bull Automotive", layout="wide")

# Dejamos fijo a CADIZ para todo el desarrollo
MI_EQUIPO = "CADIZ"

@st.cache_data
def cargar_datos():
    # Datos combinados para mostrar el impacto visual
    data = {
        'Métrica': ['Beneficio de la ronda', 'Beneficio de la ronda', 'Beneficio de la ronda', 
                    'Ingresos por ventas', 'Ingresos por ventas', 'Ingresos por ventas',
                    'Total (Cuota global)', 'Total (Cuota global)', 'Total (Cuota global)'],
        'Equipo': ['CADIZ', 'CEOS', 'CHIEF', 'CADIZ', 'CEOS', 'CHIEF', 'CADIZ', 'CEOS', 'CHIEF'],
        'Valor': [7.7, 10.2, 5.4, 45.9, 49.8, 44.0, 18.5, 22.1, 14.3]
    }
    return pd.DataFrame(data)

df = cargar_datos()

st.title(f"📊 Resumen Ejecutivo - {MI_EQUIPO}")
st.divider()

# --- BLOQUE 1: KPIs ABSOLUTOS (Solo CADIZ) ---
st.subheader("Performance Absoluta")
col1, col2, col3, col4 = st.columns(4)

# Filtramos la data solo para CADIZ
ben_cadiz = df[(df['Métrica'] == 'Beneficio de la ronda') & (df['Equipo'] == MI_EQUIPO)]['Valor'].values[0]
ven_cadiz = df[(df['Métrica'] == 'Ingresos por ventas') & (df['Equipo'] == MI_EQUIPO)]['Valor'].values[0]
share_cadiz = df[(df['Métrica'] == 'Total (Cuota global)') & (df['Equipo'] == MI_EQUIPO)]['Valor'].values[0]

# Tarjetas limpias y directas
col1.metric("Beneficio Neto (USD)", f"${ben_cadiz}M")
col2.metric("Ingresos Totales (USD)", f"${ven_cadiz}M")
col3.metric("Cuota Global", f"{share_cadiz}%")
col4.metric("Alerta Logística", "Sin quiebres de stock") # Placeholder para demanda insatisfecha

st.markdown("---")

# --- BLOQUE 2: COMPARATIVA RELATIVA (Industria) ---
st.subheader("Posición Competitiva vs. Industria")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    df_ben = df[df['Métrica'] == 'Beneficio de la ronda'].copy().sort_values(by='Valor')
    df_ben['Color'] = df_ben['Equipo'].apply(lambda x: '#00E676' if x == MI_EQUIPO else '#555555')
    
    fig_ben = px.bar(df_ben, x='Valor', y='Equipo', orientation='h', 
                     title="Beneficio Neto (USD M)", color='Color', 
                     color_discrete_map="identity", text='Valor')
    fig_ben.update_layout(showlegend=False, xaxis_title="", yaxis_title="")
    st.plotly_chart(fig_ben, use_container_width=True)

with col_chart2:
    df_share = df[df['Métrica'] == 'Total (Cuota global)'].copy().sort_values(by='Valor')
    df_share['Color'] = df_share['Equipo'].apply(lambda x: '#00BFFF' if x == MI_EQUIPO else '#555555')
    
    fig_share = px.bar(df_share, x='Valor', y='Equipo', orientation='h', 
                       title="Cuota de Mercado Global (%)", color='Color', 
                       color_discrete_map="identity", text='Valor')
    fig_share.update_layout(showlegend=False, xaxis_title="", yaxis_title="")
    st.plotly_chart(fig_share, use_container_width=True)
