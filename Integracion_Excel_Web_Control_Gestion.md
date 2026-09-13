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

## Adenda 11 (2026-09-13) — Control de Gestión en toda la app + rediseño de Resultados

Amplía el Control de Gestión de "solo dentro de Finanzas, detrás de un toggle" a una pestaña
**"Control de Gestión"** dentro de cada sección relevante (Mercado, Operaciones, Finanzas,
Resultados — RRHH queda deliberadamente sin pestaña, a pedido del equipo). También se resolvió el
scope de qué comparar en Resultados (EPS, FCF, Retorno del accionista) y se corrigió un bug real de
mapeo de datos en Operaciones.

### Alcance temporal (confirmado con el equipo)

Ronda 0 y Ronda 1 se jugaron **antes** de que este modelo de Excel existiera — no hay "proyectado"
con el que compararlas, así que ahí nunca va a aparecer un gap real (el panel cae correctamente a
`sin_proyeccion`/evolución). El primer gap Proyectado vs. Real con sentido aparece en **Ronda 2**, en
cuanto CESIM publique su RDOS.

### Nuevos crosswalks (`metric_crosswalk.py`)

- **`CROSSWALK_MERCADO`**: Demanda estimada CADIZ por mercado (EE.UU./China/Europa) — tipo `unidades`
  (nuevo, ×1000 igual que `usd` para canonicalizar, se muestra con sufijo "u.").
- **`CROSSWALK_OPERACIONES`**: Utilización de capacidad por área (EE.UU./China) — ver "Bug encontrado
  y corregido" más abajo, no es un simple lookup de campo.
- **`CROSSWALK_RESULTADOS`**: EPS (tipo `usd_accion`, nuevo — ya viene absoluto del RDOS, sin
  conversión de unidad, se muestra "USD X,XX"), FCF (ver "real_no_publicado" abajo), y "Retorno total
  acumulado del accionista [PROXY]" (ver más abajo).
- **Cuota de mercado** se deja deliberadamente FUERA de todos estos crosswalks: ya se había detectado
  que la fórmula del Excel pondera por 12 casilleros (incluye Eléctrico/Hidrógeno, donde CADIZ no
  compite) en vez de ponderar por volumen como hace CESIM — reportado al equipo, que eligió omitirla
  del Control de Gestión hasta corregir el Excel en vez de forzar una comparación poco confiable.

### Mecanismo nuevo: `real_no_publicado` (FCF)

CESIM no publica una línea de FCF en el RDOS — nunca va a existir un "real" con el que comparar (no
es un "real pendiente" temporal como Utilización de capacidad en una ronda sin RDOS todavía). Se
marca con `"real_no_publicado": True` en el crosswalk; `panel_control_gestion()` separa estas
entradas del split normal `con_gap`/`sin_gap` y las renderiza con `chart_evolucion_proyeccion()`
(nueva función en `app.py`): un gráfico de la evolución de la PROYECCIÓN propia de CADIZ a través de
las rondas, con el caption "CESIM no publica este dato en el RDOS — evolución de la proyección
propia de CADIZ." — nunca se inventa un gap contra algo que no existe.

### "Retorno total acumulado del accionista [PROXY]" — nuevo motor en `03_RATIOS`

El manual CESIM (cap. 2.1) confirma **cualitativamente** que el criterio de victoria del juego
combina la evolución del precio de la acción + los dividendos pagados ("el ganador del juego se
determina por el retorno total de los accionistas"), pero **no publica la fórmula exacta de
combinación** ni el algoritmo de valuación. A pedido explícito del equipo ("todas las decisiones son
para aumentar eso"), se construyó un PROXY explícito en `build_gestion_v2.py!03_RATIOS`:

```
Retorno del período (PROXY) = (Precio_ref(t)/Precio_ref(t-1) − 1 + 1) × (1 + Dividend yield proxy(t)) − 1
Índice acumulado(t) = Índice acumulado(t-1) × (1 + Retorno del período(t))       [base Ronda 0 = 1,00]
Retorno acumulado (PROXY, anualizado) = Índice acumulado(t) ^ (1/t) − 1
```

Verificado EXACTO contra el único dato real disponible (Ronda 1: RDOS "Retorno total acumulado del
accionista (p.a.), %" = 18,725103%, reproducido a 18,7251035% con Precio_R0=33,59236,
Precio_R1=38,65179 y Rendimiento de dividendos real R1=3,184249%). De Ronda 2 en adelante depende del
"Valor de referencia de la acción" (una Condición dada por ronda en `01_INPUTS`, no una predicción de
mercado propia) y del dividendo efectivamente decidido por CADIZ — es la mejor aproximación posible
sin el algoritmo real de CESIM (no público), y se etiqueta como **[PROXY]** en el propio nombre de la
fila y de la métrica en todo el sistema (Excel y web) para no confundirlo nunca con una regla CESIM
verificada. Exportado a `DATA_EXPORT` como métrica PLAN "Retorno total acumulado del accionista
(PROXY)", región Global.

### Bug encontrado y corregido: "Utilización de capacidad" (Operaciones)

El primer crosswalk armado para esta métrica apuntaba a un campo que no existe tal cual en el RDOS:
`Estado='Detalles de fabricación', Metrica='Capacidad empleada, %'`. El RDOS real **no publica un
único % de utilización por área** — lo publica desglosado por (área, tecnología): `Seccion='Capacidad
empleada, %', Subgrupo=área (EE.UU./China), Metrica=tecnología` (ej. Ronda 1 real CADIZ:
EE.UU./Combustión=30%, EE.UU./Híbrido=55%). Con el mapeo original, la comparación salía siempre
vacía ("Sin datos para evolución"), silenciosamente — no era un dato pendiente, era un bug de
mapeo de columnas.

**Corrección** (consultada y aprobada con el equipo antes de implementarla, igual que se hizo con
Cuota de mercado): se reconstruye el agregado real con la MISMA lógica que ya usa el propio motor
Excel para su lado Plan — `(Producción interna real, sumada todas las tecnologías del área) /
Capacidad operativa (cierre de ronda)` — en vez de asumir una constante fija a mano en la web. Para
esto:

1. **Nueva fila exportada en `DATA_EXPORT`** (`build_gestion_v2.py`): métrica PLAN "Capacidad
   operativa", región EE.UU./China, valor en unidades absolutas, linkeada directamente a
   `_ENGINE_PRODUCCION` (`prod_out["cap"][área]`). Si CADIZ invierte/desinvierte capacidad (decisión
   D2) en una ronda futura, este número se actualiza solo — no hay que tocar nada en la web ni
   hardcodear una constante que se volvería incorrecta.
2. **`gap_analysis._valor_real_utilizacion_capacidad()`** (nueva función): suma
   `Producción interna, miles unidades` real (todas las tecnologías del área, ×1000 para pasar a
   unidades absolutas) y la divide por la "Capacidad operativa" PLAN de esa misma ronda/área leída de
   `DATA_EXPORT` — devuelve el resultado en escala 0-100 para reusar `_to_absoluto()` sin casos
   especiales. `calcular_gaps()` usa esta función en vez de `_valor_real()` cuando el crosswalk trae
   `"real_calc": "utilizacion_capacidad"`.
3. **Verificado EXACTO contra Ronda 1 real**: `(336.000 Combustión + 616.000 Híbrido) / 1.400.000 =
   68,0%` en EE.UU.; `(240.000 + 100.000) / 500.000 = 68,0%` en China — coincide con el 68% ya
   confirmado por el equipo (no con el 85% calculado incorrectamente en un intento previo que asumía
   una capacidad base distinta por tecnología).
4. **Probado con un fixture sintético** (Ronda 2 real = copia de Ronda 1, solo para probar el código
   — no es un dato real): `calcular_gaps()` devuelve `estado='ok'`, `real=68,0%` vs. `proyectado=90,0%`
   (gap −22 p.p.), confirmando que el cálculo funciona de punta a punta antes de que CESIM publique
   el RDOS real de Ronda 2.

### Cuota de mercado (Resultados → pestaña "Resumen")

Dos gráficos nuevos, sin pasar por el crosswalk de Control de Gestión (son dato real global/regional,
no hay nada que proyectar):

- **Cuota de mercado global/regional (unidades)**: dato REAL directo de CESIM, ya ponderado por
  volumen — `Informe de mercado, {global|país} → Seccion='Cuotas de mercado {...}, %' → Metrica=
  'Total'`. Sin cómputo propio.
- **Cuota de mercado por valor ($)**: CESIM no publica esta cifra. Se calcula como `Ingresos por
  ventas (empresa, Global, ronda) / Σ Ingresos por ventas (los 7 equipos, misma ronda)`, usando el
  campo real ya convertido a USD por CESIM para los 7 equipos — evita tener que convertir divisas
  (China en RMB, Europa en EUR) a mano. Es un supuesto propio (Categoría 3) construido sobre dato real
  (Categoría 2); a pedido del equipo no lleva ninguna etiqueta de advertencia en la interfaz.

### Resultados → pestañas "Resumen" / "Control de Gestión"

`seccion_resultado()` pasa de una sola vista a dos pestañas: "Resumen" (todo lo que ya existía, más
los dos gráficos de cuota de mercado de arriba, reemplazando el viejo bloque de "Evolución de
Posición ACUMULADA" + "Evolución Market Cap") y "Control de Gestión" (`CROSSWALK_RESULTADOS`, con el
mismo gate de "Equipo en foco = CADIZ" que el resto).

### Mercado → "Demanda vs. Ventas por tecnología"

El gráfico de Demanda total vs. Ventas totales de la industria (Evolución) pasa de un solo total
mezclando las 4 tecnologías a un panel por tecnología (Combustión/Híbrido/Eléctrico/Hidrógeno), en
grilla de a 2. Se omite automáticamente la tecnología que no tiene ningún dato distinto de cero en
ese mercado (ej. Eléctrico/Hidrógeno en EE.UU., donde CADIZ y la mayoría de los equipos todavía no
compiten) — así no se ocupa espacio con un panel vacío.

### Verificación de esta Adenda

- Los 6 KPIs nuevos del crosswalk (3 Demanda, 2 Utilización de capacidad, y los 3 de Resultados:
  EPS/FCF/Retorno) se probaron en vivo (Streamlit + Playwright) en Ronda 1 (sin proyección → cae a
  evolución/"sin datos", correcto) y Ronda 2 (bypass "RDOS todavía no publicado" → muestra el
  Proyectado de CADIZ con el caption correcto).
- Retorno accionista PROXY: 11,5% en Ronda 2 (self-consistente con la fórmula, ya que el precio de
  referencia no cambió entre R1 y R2 en las condiciones cargadas — el retorno del período pasa a
  depender solo del dividend yield proxy).
- Utilización de capacidad: bug de mapeo encontrado, corregido y reverificado como se detalla arriba.

## Pendiente para el próximo corte

- Ampliar el crosswalk a RRHH si el equipo decide agregarle una pestaña más adelante (por ahora,
  deliberadamente sin Control de Gestión, a pedido del equipo).
- Corregir el bug ya reportado en `cesim_parser.detect_round()`: no reconoce el título "Resultados,
  Ronda inicial 0" (regex busca "Ronda X", no matchea "Ronda inicial 0") — revisar antes de subir
  `RDOS RONDA 0.xls` al repo de la web.
- Corregir la fórmula de "Cuota de mercado CADIZ (promedio)" en el Excel (divide por 12 casilleros en
  vez de ponderar por volumen) antes de reincorporarla al Control de Gestión.
- Cuando CESIM publique los RDOS reales de Ronda 2: agregar el archivo a `data/raw/practicas/
  oficial/`, y todos los paneles de Control de Gestión pasan solos de "real pendiente" a mostrar el
  gap real — no requiere ningún cambio de código.
