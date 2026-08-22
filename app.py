import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

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
            keywords_seccion = ['cuenta de', 'hoja de', 'informe', 'clasificación', 'valuación', 'creación de', 'sostenibilidad', 'ratios', 'flujo de efectivo', 'detalles de', 'desglose de']
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

# --- 4. EXTRACCIÓN SEGURA DE KPIs (Versión Inteligente Regional) ---
def extraer_kpi(df_datos, equipo, metrica, seccion_clave):
    filtro = df_datos[
        (df_datos['Equipo'] == equipo) & 
        (df_datos['Métrica'] == metrica) & 
        (df_datos['Sección'].astype(str).str.contains(seccion_clave, case=False, na=False))
    ]
    return filtro['Valor'].values[0] if not filtro.empty else 0

# --- RENDERIZADO DEL DASHBOARD DEFINITIVO ---
st.title(f"📊 Tablero Directivo - Bull Automotive (Foco: Valor Accionista)")
st.markdown(f"**Equipo Activo:** {equipo_seleccionado} | **Métrica de Victoria:** Creación de Valor")
st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🎯 1. Creación de Valor", 
    "🚀 2. Resumen Ejecutivo", 
    "💰 3. Estados Financieros", 
    "📈 4. Ratios & Valuación", 
    "🌍 5. Mercado & Precios", 
    "⚙️ 6. Producción & Costos", 
    "👥 7. RRHH & ESG", 
    "🏆 8. Clasificación"
])

# --- RENDERIZADO DE LAS NUEVAS PESTAÑAS ---

with tab1:
    st.subheader("🏆 Centro de Creación de Valor (Core Strategy)")
    st.markdown("Desglose de la matriz de valor total creada por el equipo en la ronda.")
    
    # Extraemos la sección de Creación de valor
    df_valor = df[df['Sección'].str.contains('Creación de valor', case=False, na=False)].copy()
    
    if df_valor.empty:
        st.info("No se encontraron registros de la sección 'Creación de valor' en el reporte actual.")
    else:
        # Filtramos para el equipo activo
        df_valor_eq = df_valor[df_valor['Equipo'] == equipo_seleccionado].copy()
        
        col_v1, col_v2 = st.columns([2, 1])
        with col_v1:
            fig_val = px.bar(
                df_valor_eq, x='Valor', y='Métrica', orientation='h',
                title=f"Distribución de Valor Creado - {equipo_seleccionado}",
                text_auto='.2s'
            )
            fig_val.update_layout(xaxis_title="USD", yaxis_title="", showlegend=False)
            st.plotly_chart(fig_val, use_container_width=True)
            
        with col_v2:
            st.markdown("### 💡 Foco Directivo")
            st.write("Esta vista te muestra quién se está quedando con el valor generado. El objetivo principal de la simulación es maximizar la porción correspondiente a los accionistas.")

with tab3:
    st.subheader("💰 Estados Financieros")
    st.markdown("Cuenta de resultados resumida y flujos de caja operativos de la ronda.")
    
    df_fin = df[(df['Sección'].str.contains('Cuenta de resultados', case=False, na=False)) & 
                (df['Equipo'] == equipo_seleccionado)].copy()
                
    if not df_fin.empty:
        st.dataframe(df_fin[['Sección', 'Métrica', 'Valor']], use_container_width=True, hide_index=True)
    else:
        st.warning("Sin datos financieros disponibles.")

with tab4:
    st.subheader("📈 Ratios & Valuación de Mercado")
    st.markdown("Múltiplos de mercado, WACC, apalancamiento y calificación crediticia.")
    
    df_rat = df[(df['Sección'].str.contains('Ratios e indicadores|Valuación', case=False, na=False)) & 
                (df['Equipo'] == equipo_seleccionado)].copy()
                
    if not df_rat.empty:
        st.dataframe(df_rat[['Sección', 'Métrica', 'Valor']], use_container_width=True, hide_index=True)
    else:
        st.warning("Sin datos de ratios disponibles.")

with tab5:
    st.subheader("🌍 Informes de Mercado")
    st.markdown("Análisis detallado de volúmenes, demanda insatisfecha y mix tecnológico.")
    st.info("Utilice los gráficos de la pestaña 'Dinámica de Mercado' para el cruce de precios y características.")

with tab6:
    st.subheader("⚙️ Producción, Logística y Costos")
    st.markdown("Control de capacidad instalada en plantas (EE.UU. y China), inventarios y aranceles de transporte.")
    
    df_prod = df[(df['Sección'].str.contains('Detalles de fabricación|Informe de costos|Detalles de logística', case=False, na=False)) & 
                 (df['Equipo'] == equipo_seleccionado)].copy()
                 
    if not df_prod.empty:
        # Mostramos una tabla resumen limpia con las métricas clave de costos y producción
        st.dataframe(df_prod[['Sección', 'Métrica', 'Valor']].head(15), use_container_width=True, hide_index=True)
    else:
        st.warning("Sin datos operativos detallados en esta ronda.")

with tab7:
    st.subheader("👥 RRHH & Sostenibilidad (ESG)")
    st.markdown("Métricas de dotación de personal, capacitaciones e impacto ambiental.")
    st.info("Módulo en integración con los reportes de huella de carbono y personal.")

with tab8:
    st.subheader("🏆 Clasificación General de la Industria")
    st.markdown("Ranking global de los equipos en función de su desempeño acumulado.")
    
    # Tabla comparativa general de Beneficio de la ronda para toda la industria
    df_rank = df[df['Métrica'] == 'Beneficio de la ronda'].copy()
    if not df_rank.empty:
        df_rank = df_rank.sort_values(by='Valor', ascending=False).reset_index(drop=True)
        st.dataframe(df_rank[['Equipo', 'Valor']].rename(columns={'Valor': 'Beneficio Neto'}), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Resumen Ejecutivo Global y Regional")
    # Aquí va tu selector regional y las tarjetas de KPIs principales (Beneficio, Ingresos, Share, Margen)

with tab3:
    st.subheader("Estados Financieros")
    st.write("Cuenta de resultados, Balance General y Flujo de Efectivo desglosados.")

with tab4:
    st.subheader("Ratios y Valuación de Mercado")
    st.write("WACC, múltiplos EV/EBITDA, apalancamiento y calificación crediticia.")

with tab5:
    st.subheader("Informes de Mercado")
    st.write("Demanda, precios, características y gasto en promoción por región (EE.UU., Europa, China).")

with tab6:
    st.subheader("Producción, Logística y Costos")
    st.write("Capacidad de plantas, inventarios, aranceles y costos unitarios.")

with tab7:
    st.subheader("RRHH y Sostenibilidad (ESG)")
    st.write("Dotación, salarios, capacitación y huella ambiental.")

with tab8:
    st.subheader("Clasificación General de la Industria")
    st.write("Ranking oficial de la ronda actual frente a toda la competencia.")
    
    # Selector Regional
    region = st.radio(
        "Filtro de Análisis Regional:",
        ["Global", "EE.UU.", "Europa", "China"],
        horizontal=True
    )
    
    # Mapeo de sufijos para buscar en el Excel
    sufijo_finanzas = "Global" if region == "Global" else region
    sufijo_mercado = "global" if region == "Global" else region

    # --- LÓGICA DE INGRESO REGIONAL ---
    if region in ["EE.UU.", "China"]:
        nombre_metrica_ventas = 'Beneficio de Ventas Totales'
    else:
        nombre_metrica_ventas = 'Ingresos por ventas'

    ben_val = extraer_kpi(df, equipo_seleccionado, 'Beneficio de la ronda', f'Cuenta de resultados, miles USD, {sufijo_finanzas}')
    ven_val = extraer_kpi(df, equipo_seleccionado, nombre_metrica_ventas, f'Cuenta de resultados, miles USD, {sufijo_finanzas}')
    
    share_val = extraer_kpi(df, equipo_seleccionado, 'Total', f'Informe de mercado, {sufijo_mercado}')
    share_val = round(share_val, 1) if share_val != 0 else 0
    
    if region == "Global":
        margen_val = extraer_kpi(df, equipo_seleccionado, 'Rentabilidad de las ventas (ROS)', 'Ratios')
        titulo_margen = "Margen ROS"
    else:
        margen_val = extraer_kpi(df, equipo_seleccionado, 'Margen de contribución', f'Desglose de margen por tec, miles USD, {region}')
        margen_val = (margen_val / ven_val) * 100 if ven_val > 0 else 0
        titulo_margen = "Margen Contrib. (Combustión)"
        
    margen_val = round(margen_val, 1) if margen_val != 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(f"Beneficio Neto ({region})", f"${ben_val / 1000000:.2f}M")
    col2.metric(f"Ingresos ({region})", f"${ven_val / 1000000:.2f}M")
    col3.metric(f"Cuota de Mercado ({region})", f"{share_val}%")
    col4.metric(titulo_margen, f"{margen_val}%")
    
    st.markdown("---")
    st.info("Espacio reservado para Gráficos de barra apiladas comparativos.")

import plotly.express as px

with tab2:
    st.subheader("Elasticidad y Posicionamiento Estratégico")
    
    col_ctrl1, col_ctrl2 = st.columns(2)
    region_merc = col_ctrl1.selectbox("Región a analizar", ["EE.UU.", "Europa", "China"], key="reg_merc")
    tec_merc = col_ctrl2.selectbox("Tecnología", ["Combustión", "Híbrido", "Eléctrico", "Hidrógeno"], key="tec_merc")
    
    st.markdown("---")
    
    df_precio = df[(df['Sección'].str.contains(f'Informe de mercado, {region_merc}', case=False, na=False)) & 
                   (df['Métrica'].str.contains('Precio de venta', case=False, na=False)) &
                   (df['Grupo'] == tec_merc)].copy()
    df_precio = df_precio.rename(columns={'Valor': 'Precio'})
    
    df_caract = df[(df['Sección'].str.contains(f'Informe de mercado, {region_merc}', case=False, na=False)) & 
                   (df['Métrica'].str.contains('Cantidad de características', case=False, na=False)) &
                   (df['Grupo'] == tec_merc)].copy()
    df_caract = df_caract.rename(columns={'Valor': 'Características'})
    
    df_share_tec = df[(df['Sección'].str.contains(f'Informe de mercado, {region_merc}', case=False, na=False)) & 
                      (df['Métrica'] == tec_merc) &
                      (df['Grupo'].str.contains('cuotas de mercado', case=False, na=False))].copy()
    df_share_tec = df_share_tec.rename(columns={'Valor': 'Cuota de Mercado (%)'})
    
    if df_precio.empty or df_share_tec.empty:
        st.warning(f"No hay datos registrados para {tec_merc} en {region_merc} durante esta ronda.")
    else:
        df_plot = pd.merge(df_precio[['Equipo', 'Precio']], df_share_tec[['Equipo', 'Cuota de Mercado (%)']], on='Equipo')
        df_plot = pd.merge(df_plot, df_caract[['Equipo', 'Características']], on='Equipo')
        
        # Color: Verde para CADIZ, Gris visible ("#94A3B8") para la competencia
        df_plot['Color'] = df_plot['Equipo'].apply(lambda x: '#00E676' if x == equipo_seleccionado else '#94A3B8')
        
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            fig_precio = px.scatter(
                df_plot, x='Precio', y='Cuota de Mercado (%)', text='Equipo',
                color='Color', color_discrete_map="identity",
                title=f"Elasticidad Precio ({tec_merc} - {region_merc})"
            )
            # Etiquetas visibles y marcadores con buen tamaño
            fig_precio.update_traces(textposition='top center', marker=dict(size=14))
            
            # ESCALAS FIJAS: Eje Y siempre de 0 a 35% para estandarizar la lectura
            fig_precio.update_layout(
                xaxis_title="Precio de Venta", 
                yaxis_title="Cuota de Mercado (%)",
                yaxis=dict(range=[0, 35])
            )
            fig_precio.update_xaxes(autorange="reversed")
            st.plotly_chart(fig_precio, use_container_width=True)
            
        with col_graf2:
            fig_caract = px.scatter(
                df_plot, x='Características', y='Cuota de Mercado (%)', text='Equipo',
                color='Color', color_discrete_map="identity",
                title=f"Impacto de Características ({tec_merc} - {region_merc})"
            )
            fig_caract.update_traces(textposition='top center', marker=dict(size=14))
            
            # ESCALAS FIJAS en ambos ejes (Características de 0 a 6, Cuota de 0 a 35%)
            fig_caract.update_layout(
                xaxis_title="Nivel de Características", 
                yaxis_title="",
                xaxis=dict(range=[0, 6]),
                yaxis=dict(range=[0, 35])
            )
            st.plotly_chart(fig_caract, use_container_width=True)
