import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Tablero Directivo - Bull Automotive", layout="wide")

# --- INGESTA SIMULADA ---
@st.cache_data
def cargar_datos():
    # Datos simulados con varios equipos para probar el cruce
    data = {
        'Métrica': ['Beneficio de la ronda', 'Beneficio de la ronda', 'Beneficio de la ronda', 'Beneficio de la ronda',
                    'Total (Cuota global)', 'Total (Cuota global)', 'Total (Cuota global)', 'Total (Cuota global)'],
        'Equipo': ['CADIZ', 'CEOS', 'CHIEF', 'CLAVE', 'CADIZ', 'CEOS', 'CHIEF', 'CLAVE'],
        'Valor': [7.7, 10.2, 5.4, 8.1, 18.5, 22.1, 14.3, 19.0] # Valores en millones / porcentajes
    }
    return pd.DataFrame(data)

df = cargar_datos()

# --- CONTROLES LATERLES ---
st.sidebar.title("🎛️ Controles")
# Ahora esto no filtra, solo le avisa al gráfico cuál es nuestro equipo
mi_equipo = st.sidebar.selectbox("Resaltar a Nuestro Equipo", ["CADIZ", "CEOS", "CHIEF", "CLAVE"])

st.title("📊 Resumen Ejecutivo y Posición Competitiva")
st.divider()

tab1, tab2 = st.tabs(["🚀 Ranking y KPIs", "🌍 Dinámica de Mercado"])

with tab1:
    st.subheader("Comparativa Directa vs. Industria")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Filtramos solo la métrica de Beneficio
        df_ben = df[df['Métrica'] == 'Beneficio de la ronda'].copy()
        
        # Lógica de colores: Gris para la competencia, Verde para nuestro equipo
        df_ben['Color'] = df_ben['Equipo'].apply(lambda x: '#00E676' if x == mi_equipo else '#555555')
        
        # Gráfico de barras ordenado de mayor a menor
        df_ben = df_ben.sort_values(by='Valor', ascending=True)
        fig_ben = px.bar(df_ben, x='Valor', y='Equipo', orientation='h',
                         title="Beneficio Neto por Equipo (Millones USD)",
                         color='Color', color_discrete_map="identity", text='Valor')
        
        fig_ben.update_layout(showlegend=False, xaxis_title="Millones USD", yaxis_title="")
        st.plotly_chart(fig_ben, use_container_width=True)

    with col2:
        # Hacemos lo mismo para Cuota de Mercado
        df_share = df[df['Métrica'] == 'Total (Cuota global)'].copy()
        df_share['Color'] = df_share['Equipo'].apply(lambda x: '#00BFFF' if x == mi_equipo else '#555555')
        
        df_share = df_share.sort_values(by='Valor', ascending=True)
        fig_share = px.bar(df_share, x='Valor', y='Equipo', orientation='h',
                           title="Cuota de Mercado Global (%)",
                           color='Color', color_discrete_map="identity", text='Valor')
        
        fig_share.update_layout(showlegend=False, xaxis_title="% de Mercado", yaxis_title="")
        st.plotly_chart(fig_share, use_container_width=True)
