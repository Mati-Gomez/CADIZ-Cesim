# Integración Excel → Web: Control de Gestión (Proyectado vs. Real)

Fecha: 2026-09-12. Conecta `CADIZ_Gestion_v2.xlsx` (el modelo de proyección de CADIZ) con el tablero
web `CADIZ-Cesim-main` (Streamlit), agregando un panel de Control de Gestión dentro de la sección
Finanzas que compara lo que CADIZ proyectó contra lo que CESIM efectivamente publicó, ronda a ronda.

## Diseño (confirmado con el usuario antes de construir)

- **Dirección de la integración:** Excel → Web (se lee la proyección de CADIZ hacia el repo de la
  web; la web no escribe nada de vuelta al Excel).
- **Un solo archivo, siempre el más reciente — SIN CSV intermedio (Adenda 10):** el usuario sube
  `CADIZ_Gestion_v2.xlsx` directamente a la **raíz del repo**, siempre con ese mismo nombre. La app
  (`gap_analysis.load_proyeccion()`) lee la hoja `DATA_EXPORT` de ese archivo DIRECTAMENTE en cada
  carga — no hay CSV que exportar ni mantener sincronizado a mano, ni versión por ronda. La hoja
  `DATA_EXPORT` ya trae todas las rondas (históricas y proyectadas) en una sola tabla larga, así que
  con reemplazar el `.xlsx` alcanza. (Diseño anterior: un `export_proyeccion.py` corrido a mano
  generaba un CSV intermedio — se simplificó porque el usuario prefiere subir directamente el Excel
  que ya recibe, sin un paso manual de exportación de por medio.)
- **Estructura del panel:** se mantienen las 5 secciones existentes del tablero tal cual están; el
  control de gestión vive DENTRO de cada sección relevante, detrás de un botón/toggle
  "📊 Control de Gestión: Proyectado vs. Real" — no es una pestaña nueva. Para un indicador que no
  se puede proyectar (no forma parte del modelo, o es una ronda de Práctica), el panel no lo omite:
  muestra en cambio la evolución de esa variable.
- **Alcance de este primer corte:** los 8 KPIs de cabecera de Finanzas (EBITDA, Margen bruto, ROS,
  Caja final, Deuda CP no planificada, Deuda LP, Calificación crediticia, Ingresos por ventas),
  Global. Se amplía a otras secciones (Mercado, Operaciones, RRHH) en cortes siguientes, con la
  misma disciplina de verificación fila a fila que se siguió acá.

## Archivos nuevos

- **`export_proyeccion.py`** — `read_dataframe(excel_path, team)` lee `DATA_EXPORT` de
  `CADIZ_Gestion_v2.xlsx` y devuelve un DataFrame filtrado a `team=CADIZ`; es la función que usa
  `gap_analysis.load_proyeccion()` en producción. `export()` (y el CLI del módulo) siguen
  existiendo solo como utilidad OPCIONAL para volcar un CSV de respaldo/diagnóstico manual — ya no
  son parte del flujo normal de actualización de la web (Adenda 10). Valida que el encabezado de
  `DATA_EXPORT` no haya cambiado antes de leer, para no desalinear el crosswalk en silencio.
- **`metric_crosswalk.py`** — la tabla de cruce entre el nombre de métrica canónico de
  `DATA_EXPORT` (columnas `metric`/`region`) y el nombre nativo del RDOS tal como lo deja
  `cesim_parser.py` (columnas `Estado`/`Metrica`/`Seccion`). Cada una de las 8 entradas actuales fue
  verificada numéricamente contra Ronda 1 (dato real conocido en ambos lados) antes de incorporarse
  — no se listó ninguna combinación a ciegas.
- **`gap_analysis.py`** — `load_proyeccion(path=DEFAULT_PROYECCION_EXCEL)` lee `CADIZ_Gestion_v2.xlsx`
  directamente (vía `export_proyeccion.read_dataframe()`); devuelve `None` si el archivo no está
  subido todavía o si algo falla al leerlo, sin romper la app. `calcular_gaps(df_real, df_proy,
  ronda_nombre, ronda_num)` devuelve, para cada KPI del crosswalk, un estado explícito: `ok` (hay
  proyección y real, gap calculado), `sin_real` (CADIZ ya proyectó esta ronda pero CESIM no publicó
  el RDOS todavía), `sin_proyeccion` (hay RDOS real pero el modelo no proyecta esta ronda/KPI —
  p.ej. Práctica), o `sin_datos` (ninguna de las dos). `ronda_a_num()` traduce `'Ronda N'` al entero
  que usa `DATA_EXPORT`, y devuelve `None` para rondas de Práctica a propósito (el modelo de CADIZ
  no las proyecta).
- **`app.py`** — agrega `get_proyeccion()` (wrapper cacheado con `@st.cache_data`, clave = ruta +
  `mtime` del Excel, así que reemplazar `CADIZ_Gestion_v2.xlsx` invalida el caché automáticamente en
  la próxima carga sin necesidad de reiniciar la app) y `panel_control_gestion()` (usa las funciones
  de `gap_analysis`), llamado dentro de `seccion_finanzas()`, gateado a que "Equipo en foco" sea
  CADIZ (el control de gestión es siempre sobre CADIZ, no sobre el equipo que se esté mirando).
  También se relajó el guard superior ("Faltan datos: no se encontraron archivos para esta ronda")
  para el caso específico de una ronda oficial donde CADIZ ya cargó su proyección pero CESIM
  todavía no publicó el RDOS: en vez de un callejón sin salida, se muestra directamente el panel de
  Control de Gestión (con `mostrar_directo=True`, sin el toggle) porque es lo único que hay para
  ofrecer en esa pantalla. Fuera de la sección Finanzas, o sin proyección cargada, el aviso original
  queda sin cambios.

## Verificación

- Los 8 cruces del crosswalk se verificaron uno por uno contra Ronda 1 (real en ambos lados):
  EBITDA, Margen bruto, ROS, Efectivo y equivalentes, Deudas a largo plazo, Deudas a corto plazo (no
  planificadas), Ingresos por ventas y Calificación crediticia coinciden exactamente (después de la
  conversión de unidades ya documentada: USD ×1000, ratio ÷100) entre `DATA_EXPORT` y el RDOS
  parseado en vivo por `cesim_parser`.
- Probado en vivo (Streamlit + captura de pantalla): Ronda 1 Oficial/CADIZ muestra los 8 KPIs con
  gap ≈ 0 (proyección y real son el mismo dato migrado); Ronda 2 Oficial/CADIZ muestra los 6 KPIs
  cubiertos por el modelo con "Proyectado (CADIZ) — real de CESIM pendiente", y Margen bruto /
  Calificación crediticia (no cubiertos por el modelo de proyección) caen al gráfico de evolución;
  otras secciones (Resultados, Mercado, etc.) en Ronda 2 conservan el aviso original sin cambios.

## Cómo se actualiza en la práctica (flujo final, Adenda 10)

1. El usuario reemplaza `CADIZ_Gestion_v2.xlsx` en la raíz del repo (mismo nombre siempre) —
   drag & drop en github.com sobre el archivo existente, o `git add`/commit/push.
2. `git push` redeploya la app en Streamlit Cloud en 1-2 min (igual que al subir una ronda de RDOS).
3. La próxima carga de la app lee `DATA_EXPORT` de ese Excel — el caché (`get_proyeccion()` en
   `app.py`) está atado a la ruta + `mtime` del archivo, así que un archivo nuevo con el mismo
   nombre invalida automáticamente cualquier versión vieja en caché.

No hace falta correr ningún script a mano, ni generar ni subir ningún CSV. `export_proyeccion.py`
sigue en el repo únicamente como utilidad opcional de diagnóstico (volcar un CSV de respaldo si
alguna vez hace falta inspeccionar `DATA_EXPORT` fuera de la app).

## Pendiente para el próximo corte

- Ampliar el crosswalk a Mercado, Operaciones y RRHH (misma disciplina: verificar cada cruce contra
  Ronda 1 antes de incorporarlo).
- Corregir el bug ya reportado en `cesim_parser.detect_round()`: no reconoce el título "Resultados,
  Ronda inicial 0" (regex busca "Ronda X", no matchea "Ronda inicial 0") — revisar antes de subir
  `RDOS RONDA 0.xls` al repo de la web.
- Cuando CESIM publique los RDOS reales de Ronda 2: agregar el archivo a `data/raw/practicas/
  oficial/`, y el panel de Control de Gestión pasa solo de "real pendiente" a mostrar el gap real —
  no requiere ningún cambio de código.
