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

## Adenda 12 — Rediseño "Comparativa Plan vs. Real" (panel analítico profundo)

Fecha: 2026-09-13. A pedido del equipo ("la sección de control de gestión quedó muy pobre"), se
renombra y rediseña el panel de cruce Proyectado/Real en las 4 secciones que lo tienen (Resultados,
Mercado, Operaciones, Finanzas), y se agregan gráficos nuevos en las vistas principales de Mercado y
Operaciones. Sigue el mismo principio de la Adenda 11: nunca inventar un dato Plan/Real que el modelo
o CESIM no publican — si falta, se muestra un `st.info()` explícito, nunca un gap fantasma.

### Renombre

"Control de Gestión" → **"Comparativa Plan vs. Real"** en toda la app: el nombre de la función
(`panel_control_gestion` → `panel_comparativa_plan_real`), el toggle, las 4 pestañas, los captions y
el título del panel. Cambio mecánico (verificado con `grep` línea por línea), sin tocar lógica.

### Estructura nueva del panel (Fila 1 / Fila 2 / Fila 3)

- **Fila 1** (sin cambios de fondo): hasta 4 tarjetas por fila con Proyectado/Real/Delta — ya existía.
- **Fila 2** (nueva): un bullet chart por KPI de Fila 1 que SÍ tiene ambos valores (`estado='ok'`) —
  barra gruesa apagada (Proyectado) con una barra fina superpuesta en `BRAND_ACCENT` (Real),
  `barmode='overlay'` (`chart_bullet()`, nuevo helper reutilizable). Los valores no van como texto
  "outside" de cada barra (dos barras de longitud parecida en la misma fila hacían que sus textos se
  superpusieran e quedaran ilegibles cuando Plan≈Real) sino como `st.caption()` simple debajo del
  gráfico. KPIs `tipo='texto'` (ej. Calificación crediticia) se excluyen de esta fila — ya se ven
  completos en la tarjeta de Fila 1, y una barra de una calificación como "A" no tiene sentido.
- **Fila 3** (nueva, específica por sección — ver abajo): gráficos de GAP/varianza, uno por sección,
  llamados desde la pestaña "Comparativa Plan vs. Real" de cada `seccion_*()` (no desde el panel
  genérico, que no conoce estas métricas de grano fino por mercado/tecnología/área).

### 6 campos nuevos en `CADIZ_Gestion_v2.xlsx!DATA_EXPORT` (status=PLAN, Ronda 2-12)

La Fila 3 de Resultados/Mercado/Operaciones necesita comparar contra un Plan a nivel (mercado,
tecnología) o (área, tecnología) que el Excel calculaba internamente pero no exportaba. Se agregaron
6 líneas nuevas a `build_gestion_v2.py` (una por combinación, dentro del loop PLAN existente R2-R12,
sin tocar ninguna fórmula de negocio):

| Métrica (`metric`) | Grano | Unidad | Fuente en el motor |
|---|---|---|---|
| `Precio de venta` | mercado × tecnología | moneda nativa del mercado (USD/RMB/EUR) | D5·MARKETING (decisión CADIZ) |
| `Cuota de mercado objetivo CADIZ` | mercado × tecnología | ratio (0-1) | D1·DEMANDA (decisión CADIZ) |
| `Presupuesto de promoción` | mercado × tecnología | USD | D5·MARKETING (decisión CADIZ) |
| `Ventas efectivas (mercado)` | mercado × tecnología | u. | `_ENGINE_MERCADO` (ya calculado) |
| `Costo unitario de producción propia` | área × tecnología | USD/u. | `_ENGINE_PRODUCCION` (ya calculado) |
| `Costo unitario de producción tercerizada` | área × tecnología | USD/u. | `_ENGINE_PRODUCCION` (ya calculado) |

Pipeline ejecutado dos veces (una al agregar las primeras 5 filas, otra al sumar "Cuota de mercado
objetivo CADIZ" — ver más abajo por qué): `build_gestion_v2.py` → `recalc.py` (una vez) →
`fix_digit_sheet_quoting()` (una vez) → verificación (0 errores de fórmula, 0 referencias de hoja sin
comillas). Estado final: 18.912 fórmulas, 0 errores, 128 filas PLAN/SIM CADIZ (R2-R12), 7.230 filas en
`DATA_EXPORT`.

`gap_analysis._valor_proyeccion()` necesitó un filtro opcional por `spec["tech"]`: sin él, una métrica
con varias filas por (región, tecnología) bajo el mismo nombre devolvía siempre `.iloc[0]` (la primera
fila que apareciera) — un error silencioso. Las métricas viejas (`technology="NA"`) no pasan `tech` y
siguen funcionando igual que antes.

### Funciones nuevas en `gap_analysis.py`

- `precio_volumen_mercado()` + `variacion_precio_volumen_mix()`: Análisis de Desvíos de Ingresos
  (Precio/Volumen/Mix, fórmulas estándar de Contabilidad Gerencial — Horngren et al.), por mercado,
  en la moneda nativa (sin inventar un tipo de cambio). La suma de los 3 componentes reconcilia EXACTO
  con `Ingresos Real − Ingresos Plan` (identidad algebraica, verificada con `reconciliacion_ok`).
  **Bug encontrado y corregido durante la construcción**: el volumen real de `Detalles de logística →
  Ventas en {mercado}` viene en signo NEGATIVO (es una salida en un ledger de inventario) — se
  verificó cruzando contra `Informe de mercado, {mercado} → Ventas, miles unidades` (mismo valor
  absoluto, signo correcto) y se usa esa segunda fuente en su lugar.
- `costo_unitario_area()` + `_costo_fabricacion_ponderado()` (esta última en `app.py`): costo unitario
  de fabricación (propia + contratada) Plan vs. Real, ponderado por producción REAL (mismos pesos en
  Plan y Real, así el desglose por tecnología reconcilia exacto con la diferencia total — no es una
  aproximación). **Alcance deliberadamente acotado**: solo fabricación. Transporte/aranceles y
  promoción se reportan por MERCADO de destino en el RDOS (no por ÁREA de origen), y repartirlos entre
  áreas de origen requeriría reconstruir la asignación de exportaciones del motor (Sección E) — fuera
  de este corte. Por eso el desvío de "Unit Economics" en la Comparativa Plan vs. Real de Operaciones
  NO reconcilia el 100% de la Contribución Marginal unitaria completa, y el caption de esa pestaña lo
  dice explícitamente.
- `cuota_mercado_objetivo_vs_real()`: cuota de mercado por tecnología, Objetivo (Plan) vs. Real. **Nota
  metodológica importante**: el campo que el RDOS publica directo (`Informe de mercado, {mercado} →
  Seccion='{mercado} cuotas de mercado, %' → Metrica=tecnología`) usa la convención "Ventas del equipo
  en esa tecnología / Σ Ventas de los 7 equipos EN ESA TECNOLOGÍA" (verificado exacto: Ronda 1
  Combustión EE.UU. = 667.398 / 4.146,85 = 16,09%). El input Plan "Cuota de mercado objetivo CADIZ"
  usa otra convención, declarada en el propio comentario del Excel: "% del mercado regional TOTAL (no
  se multiplica por mix tecnológico)". Compararlas directo mezclaría dos definiciones distintas de
  "cuota" — por eso el Real se RECONSTRUYE acá con la misma convención que el Objetivo (Ventas reales
  de CADIZ en esa tecnología / tamaño total del mercado, las 4 tecnologías), en vez de usar el campo
  publicado directo. Esto motivó agregar la 6ª fila nueva a `DATA_EXPORT` (no estaba en el plan
  original de 5 campos).
- `flujo_caja_plan_real_global()`: Composición del Flujo de Caja (CFO/CFI/CFF) Plan vs. Real, a nivel
  Global. El Plan ya estaba en `DATA_EXPORT` (3 líneas Global: CFO/CFI/CFF). El Real NO existe como
  una sola línea Global en el RDOS — CESIM lo publica en 3 Estados separados ("Flujo de efectivo de
  casa matriz" + China + Europa). Se reconstruye sumando los tres (cada valor × 1.000, misma
  convención "miles USD" → USD que el resto del lado real agregado). Los movimientos INTERCOMPAÑÍA
  (préstamos internos entre casa matriz y filiales, dividendos que las filiales giran a casa matriz)
  se CANCELAN naturalmente al sumar — no hace falta identificarlos a mano. **Verificado exacto contra
  Ronda 1 real**: CFO+CFI+CFF sumados (−5.738.730.257) reconcilia con la suma de "Cambios en efectivo y
  equivalentes de efectivo" de los 3 Estados (−5.738.730.257, a redondeo de punto flotante); el CFF
  Global dio exactamente −2.000.000.000 USD, que es el dividendo real pagado a los accionistas
  EXTERNOS de CADIZ (todo lo intercompañía canceló a 0) — confirma que el método es correcto.

### Los 4 gráficos de Fila 3 (uno por sección)

- **Resultados**: `go.Waterfall` de Ingresos (Proyectados → Desvío por Precio → Desvío por Volumen →
  Desvío por Mix → Reales), con selector de mercado (moneda nativa).
- **Mercado**: barras agrupadas de Cuota de mercado Objetivo (Plan) vs. Real por tecnología.
- **Operaciones**: `go.Waterfall` de GAP en costo unitario de fabricación por tecnología (alcance
  fabricación-only, ver nota arriba), con selector de área.
- **Finanzas**: barras agrupadas de Composición del Flujo de Caja (CFO/CFI/CFF) Proyectado vs. Real,
  Global.

**Guard contra falso desvío cuando no hay Plan cargado** (encontrado probando en Ronda 1, que no
tiene Plan — el modelo proyecta recién desde Ronda 2): sin este guard, el waterfall tomaba Plan=0
como línea base y le atribuía el 100% de los Ingresos/Costos Reales a "Desvío por Precio" / al GAP de
la primera tecnología — un artefacto de la falta de dato, no un desvío real. Se agregó una detección
explícita (`all(precio_plan is None ...)`) que muestra `st.info()` en su lugar, tanto en Resultados
como en Operaciones. El gráfico de Mercado (barras agrupadas) y el de Finanzas (también agrupadas) no
necesitaron este guard porque cada barra es independiente — si falta un lado, simplemente no se
dibuja esa barra, sin baseline falso que inventar.

### 3 gráficos nuevos en las vistas PRINCIPALES (no en la Comparativa)

- **Mercado → Posicionamiento**: Share of Voice (SOV = Promoción del equipo / Promoción total de la
  tecnología, los 7 equipos) vs. Share of Market — se usa el mismo campo real por tecnología que
  documenta la nota metodológica de arriba (grano dentro-de-la-tecnología en ambos lados, para que la
  comparación sea de manzanas con manzanas), no el "% del mercado total". Dato 100% real — ninguna
  proyección involucrada.
- **Operaciones → Capacidad y Costos**: junto al waterfall de Unit Economics ya existente, dos
  métricas de texto nuevas — Contribución Marginal Unitaria (mismo valor que "= Margen Unitario" del
  waterfall, re-etiquetado) y Mark-up aplicado (%) = Contribución Marginal Unitaria / Costo unitario
  total.
- **Operaciones → Capacidad y Costos**: bullet chart de Punto de Equilibrio — Costos Fijos reales
  (Depreciación + I+D + Administración, de `Cuenta de resultados, miles USD, Global`, disponibles
  directo, sin reconstrucción) / Contribución Marginal Unitaria Ponderada real (Margen de contribución
  total / unidades totales vendidas, sumado en los 3 mercados donde el equipo compite), comparado
  contra el Volumen Real Vendido. 100% real — no depende de que haya Plan cargado, así que funciona
  igual en Ronda 1 que en rondas con proyección.

### Verificación de esta Adenda

- `py_compile` sobre `app.py` y `gap_analysis.py` — 0 errores de sintaxis.
- Streamlit + Playwright en vivo, Ronda 1 (real sin Plan) y Ronda 2 (Plan sin real — estado bypass):
  las 4 pestañas "Comparativa Plan vs. Real" (Resultados/Mercado/Operaciones/Finanzas) cargan sin
  errores de consola/JS, con los mensajes `st.info()` correctos donde falta un lado del dato.
- Los 3 gráficos de la vista principal (SOV vs. SOM, Contribución Marginal + Mark-up, Punto de
  Equilibrio) probados en vivo con datos reales de Ronda 1 — valores sensatos (ej. CADIZ: SOV 5,4% vs.
  SOM 16,1% en Combustión/EE.UU. — más eficiencia comercial que el promedio; Volumen de Equilibrio
  691k u. vs. Volumen Real Vendido 2,1M u.).
- Bug visual encontrado y corregido en el propio `chart_bullet()`: el texto "outside" de cada barra se
  clippeaba contra el borde del gráfico (faltaba `cliponaxis=False`) y, cuando Plan≈Real, los dos
  textos se superponían e quedaban ilegibles — se resolvió moviendo los valores a un `st.caption()`
  simple debajo del gráfico (ver arriba).
- **No probado con datos reales combinados Plan+Real** (los 4 waterfalls/barras de Fila 3, con ambos
  lados presentes a la vez): este entorno de prueba solo tiene RDOS real de Ronda 1 (sin Plan) — el
  modelo recién proyecta desde Ronda 2, y CESIM todavía no publicó el RDOS real de Ronda 2. La lógica
  de cómputo (`precio_volumen_mercado`, `variacion_precio_volumen_mix`, `costo_unitario_area`,
  `cuota_mercado_objetivo_vs_real`) sí se validó numéricamente contra un fixture sintético (Ronda 1
  real copiada y relabeleada "Ronda 2") en el corte anterior de este mismo trabajo. Verificar
  visualmente estos 4 gráficos con datos reales en cuanto CESIM publique el RDOS de Ronda 2.

## Pendiente para el próximo corte

- Ampliar el crosswalk a RRHH si el equipo decide agregarle una pestaña más adelante (por ahora,
  deliberadamente sin Comparativa Plan vs. Real, a pedido del equipo).
- Corregir el bug ya reportado en `cesim_parser.detect_round()`: no reconoce el título "Resultados,
  Ronda inicial 0" (regex busca "Ronda X", no matchea "Ronda inicial 0") — revisar antes de subir
  `RDOS RONDA 0.xls` al repo de la web.
- Corregir la fórmula de "Cuota de mercado CADIZ (promedio)" en el Excel (divide por 12 casilleros en
  vez de ponderar por volumen) antes de reincorporarla a la Comparativa Plan vs. Real — DEFERIDO a
  pedido explícito del equipo ("excel luego lo acomodamos"), no tocado en esta Adenda.
- Verificar visualmente los 4 gráficos de Fila 3 con datos Plan+Real combinados en cuanto CESIM
  publique el RDOS real de Ronda 2 (ver nota de verificación arriba).
- `metric_crosswalk.py` no se modificó en esta Adenda: los 4 gráficos de Fila 3 usan funciones
  dedicadas en `gap_analysis.py` (grano por mercado/tecnología/área) en vez del patrón simple de
  crosswalk de un solo KPI — se documentó la decisión acá en vez de forzar el crosswalk a un grano que
  no le corresponde.
- Cuando CESIM publique los RDOS reales de Ronda 2: agregar el archivo a `data/raw/practicas/
  oficial/`, y todos los paneles de Comparativa Plan vs. Real pasan solos de "real pendiente" a
  mostrar el gap real — no requiere ningún cambio de código.

## Adenda 13 — Feedback visual: barra de progreso, unificación de nombres, decimales, Resultados y GAP de Unit Economics

Fecha: 2026-09-13. A pedido del equipo tras ver la Adenda 12 en vivo en producción (Streamlit Cloud):
seis cambios puntuales de diseño/legibilidad, ninguno toca la lógica de cálculo de `gap_analysis.py`
(solo `app.py` y `metric_crosswalk.py` — nombres, formato, colores y tipos de gráfico).

### 1. `chart_bullet()` — de barras superpuestas a barra de progreso con desborde apilado

Diseño anterior (Adenda 12): dos barras horizontales superpuestas (`barmode='overlay'`), una gruesa
apagada (Proyectado) y una fina en `BRAND_ACCENT` (Real), ambas en la escala nativa del dato. El
equipo lo encontró poco intuitivo y pidió explícitamente "una barra de progreso en donde el total sea
lo proyectado y si es mayor que se pase de largo tipo barra apilada".

Rediseño: el Proyectado se normaliza a 100% (`pct_real = real/plan*100`) y se dibuja como una pista de
referencia; el Real se dibuja como relleno DENTRO de esa pista (`min(pct_real, 100)`); si el Real
supera el Proyectado, el excedente (`max(0, pct_real-100)`) se apila como un segmento aparte con
`base=100`, que sobresale visualmente del final de la pista — barra apilada real (mismo eje, mismo
trace type, distinto `base`), no un efecto visual. Una línea vertical punteada en x=100 marca el borde
del Proyectado. Normalizar a % (en vez de mantener la escala nativa) tiene una ventaja adicional: los
bullet charts de columnas contiguas (EBITDA en USD, Demanda en unidades, Margen en %) quedan
visualmente comparables en la misma fila, cosa que antes no pasaba.

**Color del excedente = favorabilidad, no un color fijo.** Se agregó un parámetro opcional
`color_excedente` y un mapeo `_COLOR_EXCEDENTE_CG` que reutiliza el mismo criterio que ya colorea la
flecha del delta de la tarjeta de arriba (`_DELTA_COLOR_CG`, de la Adenda 12): si más Real es mejor
(`real_mayor`, ej. Ingresos), pasarse del plan es favorable → verde (`COLOR_POSITIVE`); si no hay
dirección favorable definida (`None`) o si menos Real es mejor (`real_menor`, ej. Deuda CP no
planificada), ámbar neutro (`COLOR_METRICA['riesgo']`). **Nota de auditoría**: se probó primero con
`BRAND_ACCENT` (rojo de marca) para `real_menor`, pero es el MISMO rojo que ya usa el relleno "Real"
del propio bullet — el segmento de excedente quedaba invisible, fundido con la barra (encontrado con
una prueba visual dedicada, ver Verificación). Se resolvió unificando `real_menor` y `None` al mismo
ámbar — sigue leyéndose "atención, se pasó de la referencia" sin necesidad de un tercer color.

El llamador de Operaciones (Punto de Equilibrio) pasa `color_excedente=COLOR_POSITIVE` explícito
(vender por encima del equilibrio siempre es favorable, sin ambigüedad).

**Caso borde nuevo**: si el Proyectado es ≤ 0, expresar el Real como % de un Plan de referencia no
tiene sentido matemático (división por ~0) — se cae a una barra simple en valor absoluto, sin pista de
referencia, y el caption lo aclara ("Proyectado ≤ 0, no expresable como % de avance").

### 2. Unificación de nombres entre la Comparativa y las vistas nativas

Antes había 3 términos distintos para "el valor planificado" en distintas partes del tablero: "Plan"
(Operaciones, Fila 3), "Objetivo (Plan)" (Mercado, Fila 3), "Proyectado" (todo lo demás). Se unificó
TODO a **"Proyectado"** — término que ya usaba `chart_bullet()`, la Fila 1 de KPIs y el resto de la
Comparativa:

- `fila3_mercado_cuota_objetivo()`: "Objetivo (Plan)" → "Proyectado" (título del gráfico, columna
  `Tipo` del DataFrame, `color_discrete_map`).
- `fila3_operaciones_gap_fabricacion()`: "Costo Plan" → "Costo Proyectado"; "GAP {tecnología}" →
  "Desvío {tecnología}" (ver punto 6 — "GAP" en inglés era parte de la confusión reportada).
- `fila3_resultados_ingresos()`: título "Ingresos — Plan vs. Real" → "Ingresos — Proyectado vs. Real".

KPI nativo de Resultados renombrado para compartir raíz con el crosswalk: "Retorno acumulado" →
**"Retorno acum. del accionista"** (mismo término base que "Retorno acumulado del accionista (Proxy)"
del crosswalk — antes decían cosas distintas para el mismo concepto).

### 3. Nombres en español (sin anglicismos sueltos)

- KPI "Market Cap (USD)" → **"Capitalización de mercado (USD)"** (mismo nombre que el propio campo de
  CESIM, `'Capitalización de mercado, miles USD'`); "Evolución Market Cap (USD)" →
  "Evolución de la Capitalización de Mercado (USD)".
- Waterfall de Operaciones "Unit Economics — {tecnología} {país}" → **"Margen Unitario — {tecnología},
  {país}"**; selectores "País Unit Econ" / "Tech Unit Econ" → "País — Margen Unitario" /
  "Tecnología — Margen Unitario"; "Tech Inventario" → "Tecnología — Inventario".
- `metric_crosswalk.py`: "EPS" → **"Ganancias por Acción (EPS)"** (mismo nombre que el campo real,
  `'Ganancias por acción (EPS), USD'`); "Retorno total acumulado del accionista [PROXY]" →
  "Retorno acumulado del accionista (Proxy)" (más corto, sin mayúsculas de énfasis); "Utilización de
  capacidad — EE.UU./China" → **"Capacidad empleada — EE.UU. (total)/China (total)"** (mismo término
  que ya usa la tarjeta nativa de Operaciones → Capacidad y Costos, desglosada por tecnología — el
  "(total)" aclara que el KPI del crosswalk es el agregado de planta, no el desglose).

### 4. `format_num()` — al menos un decimal siempre

Antes: el corte de "miles" (`>= 1_000`) truncaba a entero (`638k` en vez de `638,2k`) mientras el corte
de "millones" ya usaba 1 decimal — inconsistente, y justo en el rango donde más se usa (la mayoría de
los montos del tablero caen en miles). Se cambió `f"{val/1_000:,.0f}k"` → `f"{val/1_000:,.1f}k"`, el
default de `dec` de 0 a 1 (con `dec = max(dec, 1)` para que ningún llamador pueda pedir menos de 1
decimal por accidente). Sin llamadores que pasaran `dec=` explícito (verificado con `grep`), el cambio
es transparente en todos los ~15 puntos de uso.

### 5. Resultados → Resumen: menos gráficos de barra, más variedad

El equipo reportó "muchos gráficos de barra" en esta pestaña. Auditoría: la sub-sección "Cuota de
mercado" tenía 5 `px.bar` casi idénticos (global, por valor, EE.UU., China, Europa) — más el ranking
horizontal y el waterfall de arriba, ~7 gráficos de la familia "barra" sobre 9 gráficos totales en la
pestaña. Se reemplazaron esos 5 por dos formas elegidas por el trabajo que hacen mejor (criterio de la
skill de dataviz — la forma la elige el trabajo del dato, no la costumbre):

- **Dumbbell chart** (2 puntos + línea por equipo): Cuota por unidades vs. Cuota por valor ($) en un
  solo gráfico — la distancia entre los dos puntos de cada equipo ES el dato interesante (vender una
  porción de unidades distinta a la de ingresos implica un mix de precio propio; antes esto vivía en
  dos barras separadas, sin conexión visual entre ambas). Fila de CADIZ resaltada con línea más gruesa
  y en `BRAND_ACCENT`.
- **Heatmap** (empresa × país): reemplaza las 3 barras de desglose regional (EE.UU./China/Europa) por
  una sola grilla, con expander "Ver como tabla" debajo (accesibilidad — la skill de dataviz pide que
  siempre exista una vista de tabla). Escala de color secuencial de un solo matiz (transparente →
  `BRAND_ACCENT`), sin arcoíris.
- Se mantiene: 5 sparklines de KPI, el waterfall "Puente de Beneficio Neto" (decomposición — la forma
  correcta para eso), el ranking horizontal (comparación de magnitud entre 7 equipos — bar sigue siendo
  la forma correcta ahí, no se cambió), y la evolución de línea de Market Cap al final.

### 6. Aclaración del waterfall "Desvío en Costo Unitario de Fabricación" (antes "Unit Economics")

El equipo reportó explícitamente no entender este gráfico (`fila3_operaciones_gap_fabricacion()`).
Auditoría de causa: el waterfall coloreaba "sube el costo" (`increasing`) con `MUTED_PALETTE[2]` (un
verde grisáceo) y "baja el costo" (`decreasing`) con `COLOR_POSITIVE` (verde pleno) — **dos verdes del
mismo matiz para significados opuestos**, imposible de distinguir de un vistazo (y el waterfall de
Ingresos de al lado usaba el mismo par invertido — incoherencia extra entre ambos gráficos). Se
corrigió a un criterio único en los dos waterfalls de desvío (Ingresos y Costo unitario): **verde =
favorable para CADIZ, ámbar (`COLOR_METRICA['riesgo']`) = desfavorable**, sin importar si la barra
individual "sube" o "baja" — un costo que SUBE es desfavorable → ámbar; un ingreso que SUBE es
favorable → verde. Se agregó además: (a) el nombre "GAP {tecnología}" → "Desvío {tecnología}" (en
inglés y sin explicar qué significaba); (b) un caption nuevo explicando literalmente qué es cada barra
("cuánto empujó esa tecnología el costo unitario ponderado total, de Proyectado a Real — no el costo
de esa tecnología en sí") y la identidad de reconciliación (Costo Proyectado + todos los desvíos =
Costo Real, exacto); (c) el título de la sección, sin el anglicismo "Unit Economics". No se cambió la
estructura de waterfall en sí (se decidió no reemplazarla por un gráfico más simple): la decomposición
por tecnología es información real y verificada (reconcilia exacto por construcción, Adenda 12), y el
problema diagnosticado fue de color/nombre, no de tipo de gráfico — si el equipo confirma que la
confusión era otra cosa, hay que revisar de nuevo con ese detalle puntual.

### Verificación de esta Adenda

- `py_compile` sobre `app.py` y `metric_crosswalk.py` — 0 errores de sintaxis.
- `chart_bullet()` probado de forma aislada (script standalone con Streamlit + Playwright, sin
  depender de datos CESIM) en 6 casos: Real < Plan, Real ≈ Plan, Real > Plan favorable, Real > Plan
  desfavorable, Real > Plan sin favorabilidad definida, Plan ≤ 0 — los 6 renderizan correctamente
  (fue en este proceso donde se encontró y corrigió la colisión de color rojo-sobre-rojo del punto 1).
  Verificado también en vivo dentro de la app: Operaciones → Punto de Equilibrio, Ronda Práctica 1,
  Volumen Real Vendido muy por encima del Volumen de Equilibrio (519,3% del plan) — el segmento de
  excedente en verde se ve correctamente por encima de la pista de 100%.
- Los dos waterfalls de desvío (Costo unitario de fabricación e Ingresos) probados de forma aislada con
  datos sintéticos — verde/ámbar se distingue con claridad en ambos, mismo criterio en los dos.
- Dumbbell y heatmap de "Cuota de mercado" probados en vivo con datos reales de Ronda Práctica 1 —
  ambos renderizan correctamente, incluida la tabla del expander.
- **No probado con datos Plan+Real reales combinados** (mismo motivo que la Adenda 12: este entorno de
  prueba solo tiene RDOS de rondas de Práctica y Ronda 1 oficial, sin Plan cargado desde Ronda 2) — los
  cambios de nombre/color de la Fila 3 (puntos 2 y 6) no se vieron con datos reales de ambos lados a la
  vez, solo con datos sintéticos. Verificar visualmente en cuanto CESIM publique el RDOS de Ronda 2.

## Pendiente para el próximo corte (actualizado)

- Todo lo pendiente de la Adenda 12 sigue pendiente (ver arriba) — nada de esta Adenda lo resuelve.
- Verificar con el equipo si la aclaración del punto 6 (color + nombres + caption) resolvió la
  confusión reportada sobre el waterfall de Costo Unitario de Fabricación, o si el problema era otro
  (ej. el concepto de "desvío ponderado por tecnología" en sí, no la forma en que se mostraba) — en ese
  caso, considerar reemplazar el waterfall por una comparación directa de 2 barras (Proyectado vs.
  Real) con el desglose por tecnología movido a una tabla secundaria.
- Verificar visualmente los gráficos de Fila 3 (nombres/colores de esta Adenda) con datos Plan+Real
  reales combinados en cuanto CESIM publique el RDOS de Ronda 2 (mismo pendiente que la Adenda 12).

## Adenda 14 — Dos alertas nuevas: I+D fuera de lo común y Entrada a tecnología nueva de la competencia

Fecha: 2026-09-13. A pedido del equipo ("estaría bueno saber si un equipo metió muchas jornadas de
I+D para meter una tecnología nueva"), se agregan 2 alertas nuevas a `evaluar_alertas()` — ambas
vigilan a LOS RIVALES siempre (igual que "Movimientos de capacidad de la competencia", ya existente),
sin depender de a quién tengamos seleccionado en "Equipo en foco".

### 1. "{rival}: I+D fuera de lo común" (aviso, TEMPRANO, Categoría 3 — supuesto propio)

CESIM publica el I+D de cada equipo como un ÚNICO número GLOBAL en la Cuenta de Resultados (dato real
para los 7 equipos) — no desglosado por tecnología. Se dispara cuando el I+D de esta ronda de un rival
es (a) su propio máximo histórico Y (b) está por encima del promedio de I+D de sus 6 rivales en la
misma ronda.

**Por qué esas dos condiciones y no un % fijo de suba**: se probó primero un umbral de suba ronda a
ronda, pero el I+D salta muchísimo incluso sin nada raro pasando — verificado con los 3 datos de
Práctica disponibles (TOKIO pasó de +432,7% a −77,6% en rondas consecutivas). Un % fijo hubiera dado
falsos positivos todo el tiempo. "Récord propio + por encima de sus rivales" filtra ese ruido sin
inventar un número mágico de corte — el manual (cap. 7) dice explícitamente que "es difícil aplicar
algún método para el cálculo exacto de la inversión" y no da ningún umbral, así que cualquier número
fijo hubiera sido un invento sin respaldo.

**Por qué es estimativo, no una cuenta regresiva** (aclaración pedida explícitamente por el equipo
al revisar el diseño): el manual (cap. 7) dice que "la cantidad requerida de jornadas de trabajo por
persona para el desarrollo interno varía según el nivel de eficiencia de sus empleados" — cuántas
jornadas (y cuánto I+D) necesita CADA equipo para sacar una tecnología nueva depende de su propia
dotación/eficiencia de RRHH, que no es pública. El texto de la alerta lo dice explícitamente: es un
indicio de que "puede estar preparando algo", nunca una certeza ni un plazo.

**Qué NO cubre**: el manual describe DOS caminos para sumar tecnología — I+D propio (con una ronda de
retraso) o comprar una licencia (disponible de inmediato). Un rival puede entrar a una tecnología
nueva vía licencia sin ningún salto de I+D previo, y esta alerta no lo vería venir. Para eso está la
alerta #2, que confirma la entrada sin importar por qué vía la consiguió.

### 2. "Entrada a tecnología nueva de la competencia" (aviso, CONFIRMADO, Categoría 2 — dato real)

A diferencia de la alerta de I+D, esto es un HECHO, no una estimación: usa la cuota de mercado real
que CESIM publica por (país, tecnología) para los 7 equipos (`Informe de mercado, {país} →
Seccion='{país} cuotas de mercado, %' → Metrica=tecnología` — el mismo campo que ya usa
`cuota_mercado_objetivo_vs_real()` en `gap_analysis.py`). Se dispara cuando un rival pasa de 0% en la
ronda anterior a >0% en esta, en una combinación (tecnología, país) donde antes no vendía nada — no le
importa si la consiguió con I+D propio o comprando una licencia, cubre las dos vías del manual por
igual.

**Consolidación en un solo aviso**: cuando una tecnología se habilita para toda la industria a la vez
(verificado con datos reales: en Práctica 2, seis de los siete equipos entraron a Híbrido en los 3
países en la misma ronda), disparar una tarjeta por cada combinación saturaba el panel sin agregar
información nueva en cada una — se consolidó en un solo aviso con todas las entradas de la ronda
separadas por "·", mismo patrón que ya usaba "Movimientos de capacidad de la competencia".

### Verificación de esta Adenda

- `py_compile` sobre `app.py` — 0 errores de sintaxis.
- Probado en vivo (Streamlit + Playwright) recorriendo Práctica 1 → 2 → 3 con datos reales:
  - Práctica 1 (primera ronda, sin historia previa): ninguna de las dos alertas nuevas dispara —
    correcto, no hay "récord histórico" ni "ronda anterior" con la cual comparar todavía.
  - Práctica 2: dispara "CHIEF: I+D fuera de lo común" (5,5M USD, máximo propio y por encima del
    promedio de sus rivales de 1,3M) y "FOCUS: I+D fuera de lo común" (2,5M vs. promedio 1,8M), más
    un aviso consolidado de "Entrada a tecnología nueva" con 12 combinaciones (Híbrido, los 3 países,
    6 equipos).
  - Práctica 3: TOKIO dispara AMBAS alertas en la misma ronda — "I+D fuera de lo común" (7,5M USD,
    muy por encima del promedio de 1,8M) y aparece en el aviso consolidado de entrada con TRES
    combinaciones nuevas (Hidrógeno EE.UU. 0%→100%, Eléctrico China 0%→30,5%, Eléctrico Europa
    0%→100%) — exactamente el patrón que el equipo pidió poder ver ("un equipo metió muchas jornadas
    de I+D para meter una tecnología nueva").
  - Ronda 1 Oficial (primera ronda de ese ecosistema): tampoco dispara ninguna de las dos — correcto,
    mismo motivo que Práctica 1.
- **Nota de alcance**: todo lo probado en este entorno son rondas de Práctica (mucho más volátiles
  que una competencia oficial real, según el propio caption que agregan las alertas) más una única
  Ronda Oficial sin ronda previa — no se pudo probar el comportamiento en una secuencia de Rondas
  Oficiales reales (2, 3, ...) porque CESIM todavía no las publicó. La lógica no depende de si es
  Práctica u Oficial (mismos campos, mismas reglas), así que no se espera que cambie, pero queda
  pendiente confirmarlo visualmente en cuanto haya más de una Ronda Oficial jugada.

## Adenda 15 — Revisión estética integral y corrección de bugs de UI

Después de cerrar las alertas (Adenda 14), el equipo pidió una opinión honesta sobre el estado
estético del tablero completo ("¿te parece hacer algún cambio estético o lo ves bien así?"). Se
recorrieron sistemáticamente las 9 secciones/sub-tabs de la app con Streamlit + Playwright (3
capturas por vista, con scroll) y se armó una lista de hallazgos, ordenados por impacto. El equipo
aprobó avanzar primero con los ítems 1 a 4 (bugs concretos y de bajo riesgo); los ítems 5 y 6
(etiquetas superpuestas en 2 gráficos, redundancia de gráficos de tecnología cuando solo hay una
tecnología activa) quedan pendientes para una próxima iteración.

### 1. Truncamiento de títulos en las tarjetas KPI de Resultados/Resumen

**Causa raíz encontrada, no solo el síntoma**: `assets/style.css` ya tenía una regla pensada
específicamente para evitar este truncamiento (`div[data-testid="stMetricLabel"] { white-space:
normal !important; ... }`), agregada en un corte anterior — pero el selector apuntaba a un
`<div>`, y Streamlit 1.63 renderiza ese elemento como `<label data-testid="stMetricLabel">`. El
selector nunca matcheaba nada, por eso el truncamiento seguía pasando pese a que "ya estaba
arreglado" en apariencia. Se confirmó inspeccionando el DOM real servido (no adivinando por CSS).
Corregido a `[data-testid="stMetricLabel"]` (sin tag fijo), que matchea el elemento real.

Aparte, el valor (no el label) de la tarjeta "Retorno de la acción" mostraba el texto largo "Sin
ronda previa" cuando no hay ronda anterior con la cual comparar (primera ronda del ecosistema) — el
valor de `st.metric` no wrappea como el label, así que ese texto también se cortaba. Se reemplazó
por "—", consistente con cómo se muestra la ausencia de dato en el resto del tablero; el caption
debajo de las tarjetas ya explica por qué no hay dato en la primera ronda.

### 2. Título duplicado en el gráfico de Capitalización de Mercado

`chart_evolucion()` antepone "Evolución — " al título que recibe; se la estaba llamando con
"Evolución de la Capitalización de Mercado (USD)", resultando en "Evolución — Evolución de...".
Se revisaron los otros 4 usos de `chart_evolucion()` en el archivo — ninguno tenía el mismo problema.

### 3. Números sin redondear en el Funnel de "Estructura Macro de Costos"

El funnel (Operaciones → Capacidad y Costos) usaba `textinfo='value+percent initial'`, que aplica el
formateo automático de Plotly (sufijo M/k pero SIN redondear decimales: "45.91583M"), inconsistente
con `format_num()` (1 decimal) usado en el resto del tablero — incluida la waterfall de "Puente de
Beneficio Neto" unas filas más abajo, con los mismos datos. Se armó el texto a mano con
`format_num()` vía `text=[...] , textinfo='text+percent initial'`.

### 4. Gráficos de doble eje Y (violan la regla de "un solo eje" de buenas prácticas de dataviz)

Se encontraron 5 gráficos con dos escalas Y superpuestas en el mismo plano — un anti-patrón que
puede sugerir correlaciones que no están probadas y dificulta leer cada serie por separado:

- RRHH y Sostenibilidad → Personal y Talento: los 4 gráficos de esa pestaña (Evolución: Salario vs
  Rotación; Rotación vs. Contrataciones netas; Inversión en I+D: costo vs. dotación; Capacitación
  vs. eficiencia de RRHH). Esta pestaña nunca había sido tocada en los rediseños anteriores.
- Finanzas → Largo Plazo: "Beneficio Neto vs. Nivel de Deuda" (Beneficio en USD contra Apalancamiento
  en un eje secundario que llegaba a valores negativos).

**Solución**: se creó `chart_dos_metricas_apiladas()` (helper nuevo, cerca de `chart_evolucion`), que
arma dos paneles apilados con `plotly.subplots.make_subplots(rows=2, cols=1, shared_xaxes=True)` —
comparten el eje X (misma Ronda, para poder seguir la evolución de ambas a la vez) pero cada métrica
tiene su propio eje Y, con el nombre de la métrica como título de su panel (sin `subplot_titles`,
que hubiera consumido alto extra en una tarjeta de 370px). Se reemplazaron los 5 gráficos por
llamadas a este helper, conservando los mismos colores y tipos de traza (barra o línea) que tenían
antes.

### Verificación de esta Adenda

- `py_compile` sobre `app.py`, `metric_crosswalk.py`, `gap_analysis.py`, `cesim_parser.py` — 0
  errores.
- Se inspeccionó el DOM real vía Playwright para confirmar la causa exacta del bug de truncamiento
  (no se asumió qué elemento HTML generaba el problema).
- Se volvió a correr el recorrido completo de capturas después de cada fix y se confirmó
  visualmente: los 5 títulos de las tarjetas KPI se ven completos y sin "…"; el título de
  Capitalización de Mercado ya no repite "Evolución"; el funnel muestra "45.9M / 31.0M / 25.6M /
  17.1M / 14.9M / 11.8M" (antes "45.91583M..."); los 5 gráficos de doble eje pasaron a dos paneles
  apilados de un solo eje cada uno, verificado en las 4 vistas de RRHH y en Finanzas/Largo Plazo.
- **No incluido en este corte** (quedó fuera del alcance que aprobó el equipo, documentado para más
  adelante): etiquetas de equipos superpuestas e ilegibles en "Precio Promedio vs Volumen"
  (Mercado/Posicionamiento) y en "Matriz Riesgo/Retorno" (Finanzas/Largo Plazo); labels apretados e
  ilegibles en segmentos chicos del stacked bar de "Estructura del Balance"; redundancia entre el
  donut y la barra de "Mix tecnológico" (Mercado/Panorama Competitivo) mientras solo hay una
  tecnología activa en el mercado.

## Adenda 16 — Piloto de identidad visual (Resultados/Resumen + sidebar global)

El equipo pidió explícitamente una opinión sobre si valía la pena un cambio estético más de fondo
("¿te parece hacer algún cambio estético o lo ves bien así?"), y compartió como referencia un
dashboard propio hecho en React (Grupo Randazzo / Geodefender — sistema de infracciones) con un
look más "producto" (sidebar oscuro, tarjetas con barra de composición, banda oscura para las
métricas más importantes). Antes de tocar nada se preguntó explícitamente por escrito si migrar
CADIZ de Streamlit/Python a React (con deploy en Vercel) era conveniente — la respuesta, alineada
con la prioridad que fijó el equipo ("si perdemos capacidad de analizar datos no, prima eso por
sobre la estética"), fue que NO: toda la lógica de análisis (`cesim_parser.py`, `gap_analysis.py`,
el crosswalk, las 8 reglas de `evaluar_alertas()`, las waterfalls financieras) está en pandas y ya
fue auditada contra el manual y R0/R1 — reescribirla en JavaScript para una app React sería el
escenario con más riesgo de introducir un error silencioso justo antes de la Ronda 2, y Vercel de
por sí no está pensado para correr ese tipo de backend con estado (terminaría siendo dos proyectos
en vez de uno). Se decidió seguir en Streamlit y usar el margen real que da el CSS, que resultó ser
más amplio de lo que parecía.

Con el equipo se acordó (1) qué patrones visuales de la referencia adoptar — sidebar oscuro con
indicador de estado, tarjetas con barra de composición, banda oscura para los KPIs más críticos — y
(2) probarlo primero en una sola sección (Resultados/Resumen) antes de extenderlo a toda la app.
El equipo también autorizó cambiar la tipografía por una más parecida a la de la referencia.

### Cambios de este corte

- **Tipografía**: Inter → **Plus Jakarta Sans** en toda la app (`assets/style.css` y los gráficos de
  Plotly en `mostrar()`, para que los títulos de gráfico usen la misma fuente que el resto de la
  página).
- **Sidebar oscuro** (afecta a las 5 secciones, porque el sidebar es chrome compartido, no algo que
  se pueda "pilotear" por sección): fondo grafito (`--brand-dark`, la misma variable de marca que ya
  existía, no un color nuevo), texto claro, cajas de selectbox/slider con su propio fondo traslúcido
  para no perder contraste. **Decisión de diseño explícita**: NO se intentó oscurecer el menú
  desplegable (popover) de los selects del sidebar, porque ese popover se porta fuera del `<section>`
  del sidebar (a nivel `<body>`) y un selector que lo alcance oscurecería TODOS los selects de la
  app, incluidos los de las secciones con fondo claro — quedaría peor que dejarlo como está.
- **Indicador de estado** bajo el logo ("● Práctica 1"), estilo el "● Conectado" de la referencia,
  pero mostrando algo real (ronda + ecosistema en foco) en vez de ser puramente decorativo.
- **Barra segmentada de "Estado de Alertas"** arriba del listado de alertas: composición por
  severidad (crítica / aviso / mejora) de las alertas ACTIVAS ahora mismo. Nota de rigor: a
  diferencia de las tarjetas "Estado de Asignación" de la referencia (que son un % sobre un universo
  FIJO, ej. actas totales), acá no hay un universo fijo de "reglas evaluadas" — una sola regla (ej.
  "I+D fuera de lo común") puede dispararse entre 0 y 6 veces según cuántos rivales califiquen. Por
  eso el rótulo dice explícitamente "N activas en {ronda}", nunca un porcentaje de un total que no
  existe como tal — se adoptó el patrón visual, no una proporción inventada.
- **Banda oscura de KPIs críticos**: los 3 números que más le importan a un accionista (Retorno
  acum. del accionista, Beneficio del accionista, Capitalización de mercado) se separaron en un
  bloque oscuro destacado, estilo "Monto Pendiente / A vencer / Ya pagado" de la referencia.
  "Posición en el ranking" y "Retorno de la acción" (más de contexto que de creación de valor)
  quedaron como tarjetas claras con sparkline, como antes.

### Bug encontrado y corregido durante la verificación

El color del delta en la banda oscura (verde si favorable, salmón si no) no se aplicaba en los
casos negativos — quedaba en el gris por defecto. Causa: `favorable` se arma comparando floats de
pandas/numpy (`delta > 0`), lo que da `numpy.bool_`, no un `bool` de Python -- el código usaba `is
False` para diferenciar "desfavorable" de "sin dato", y `numpy.bool_(False) is False` da `False` en
Python (fallo de identidad, no de valor). Se encontró inspeccionando el color computado real vía
Playwright (`getComputedStyle`), no asumiendo por qué se veía mal. Corregido reescribiendo la
condición sin comparar identidad (`if fav is None / elif fav / else`).

### Verificación de esta Adenda

- `py_compile` sobre `app.py` — 0 errores.
- Se verificó visualmente el sidebar oscuro en las 5 secciones (no solo en el piloto), confirmando
  que radios, slider, selectbox y sus estados hover se ven legibles con el nuevo fondo.
- Se verificó con `getComputedStyle` vía Playwright que los 3 deltas de la banda oscura renderizan
  el color correcto (`rgb(230,138,114)` salmón para desfavorable, `rgb(134,217,146)` verde para
  favorable) después del fix.
- **Alcance**: por acuerdo explícito con el equipo, este corte es un PILOTO en Resultados/Resumen
  (más el sidebar, que es global por naturaleza). El resto de las secciones sigue con el estilo de
  tarjetas claras anterior hasta que el equipo confirme si quiere extender el patrón.

## Pendiente para el próximo corte (actualizado)

- Todo lo pendiente de las Adendas 12 y 13 sigue pendiente (ver arriba).
- Corregir la fórmula de "Cuota de mercado CADIZ (promedio)" en el Excel (divide por 12 casilleros en
  vez de ponderar por volumen) — próximo en la cola de trabajo, a pedido explícito del equipo.
- Si en una Ronda Oficial real la alerta de "I+D fuera de lo común" resulta demasiado sensible o
  demasiado laxa (mucho más estable que Práctica, al no ser rondas de ensayo), reconsiderar el
  criterio de disparo — quedó documentado como Categoría 3 (supuesto propio) explícitamente para que
  se pueda ajustar sin que nadie lo confunda con una regla de CESIM.
- Ítems estéticos 5 y 6 de la Adenda 15 (etiquetas superpuestas, redundancia de "Mix tecnológico"):
  pendientes de aprobación del equipo para una próxima iteración.
- Decidir si el piloto de la Adenda 16 (banda oscura + barra segmentada) se extiende al resto de las
  secciones, y a qué otras métricas (ej. Capacidad empleada en Operaciones podría ser una barra
  segmentada, en vez de la tarjeta simple actual).

## Adenda 17 — Verificación de la banda oscura en modo oscuro nativo de Streamlit

Antes de extender el piloto de la Adenda 16 al resto de la app, el equipo preguntó específicamente
cómo se ve la nueva "banda oscura de KPIs críticos" cuando el usuario tiene activado el modo oscuro
nativo de Streamlit (no confundir con el modo oscuro de los gráficos Plotly, que ya se manejaba
correctamente desde antes vía `es_modo_oscuro()`).

### Problema encontrado

Al probar con Playwright, se detectó que la banda oscura (fondo `--brand-dark`, el mismo grafito
que el sidebar) quedaba visualmente indistinguible de las tarjetas circundantes en modo oscuro:
ambas terminan siendo prácticamente el mismo gris oscuro, perdiendo el efecto de "destacar los 3
KPIs más importantes" que es la razón de ser del componente. Se confirmó con captura de pantalla
antes de tocar el código (no se asumió el problema, se lo vio).

### Causa y corrección

`es_modo_oscuro()` (`app.py`, ya existente) usa `st.context.theme.type == 'dark'`. Se agregó:

- En `assets/style.css`: una variante `.kpi-band-oscura.tema-oscuro` con fondo en degradé rojo
  translúcido (`linear-gradient` sobre `rgba(179, 38, 30, ...)`, el rojo de marca) en vez del
  grafito plano, para que la banda se distinga tanto del fondo oscuro de Streamlit como de las
  tarjetas comunes.
- En `app.py`, función `kpi_banda_oscura()`: se agrega la clase `tema-oscuro` al contenedor cuando
  `es_modo_oscuro()` es verdadero.

### Limitación de la plataforma encontrada durante la verificación (no un bug de nuestro código)

Al verificar con Playwright alternando Claro→Oscuro desde el menú de Streamlit dentro de una misma
sesión (sin recargar la página), la clase `tema-oscuro` NO se actualizaba — quedaba con el fondo
grafito plano aunque el resto de la página (fondos, textos nativos de Streamlit) sí había cambiado
a oscuro correctamente. Se investigó la causa antes de intentar "arreglarlo":

- `st.context.theme.type` sólo refleja el tema vigente al momento en que se abrió/conectó la
  sesión del navegador — no se actualiza con un `rerun` de script disparado dentro de la misma
  conexión, sólo con una recarga completa de la página (confirmado forzando un rerun sin recargar:
  la clase seguía sin actualizarse; y confirmado que sí se actualiza correctamente tras
  `page.reload()`).
- Se buscó una alternativa puramente CSS (variables CSS custom properties, atributos en
  `<html>`/`<body>`/`.stApp`) para detectar el tema sin depender de Python, para que no dependiera de
  un rerun. No existe: Streamlit resuelve los colores de tema generando clases CSS-in-JS (Emotion)
  con colores literales en cada carga, no expone el tema vía variables CSS consultables. Se decidió
  no compensar esto con JavaScript inyectado (leer el DOM y togglear la clase a mano), porque sería
  un parche fragil y difícil de mantener para un caso de uso angosto.
- **Se verificó el escenario real más común** — el que efectivamente van a tener los evaluadores o
  el equipo si su sistema operativo/navegador está en oscuro y Streamlit está en su configuración
  por defecto ("Usar configuración del sistema") — con una carga de página fresca simulando
  preferencia de oscuro del sistema operativo (`prefers-color-scheme: dark`): en ese caso
  `es_modo_oscuro()` sí detecta correctamente el tema oscuro desde el primer render, y la banda
  aparece con el degradé rojo tal como se diseñó. También se confirmó que una recarga manual de
  página después de cambiar el tema desde el menú de Streamlit soluciona el caso restante.

**Conclusión, clasificada explícitamente:**

1. *Regla/limitación verificada de la plataforma Streamlit* (no una regla CESIM, aclarado para no
   confundir capas): el color de la banda oscura sigue el tema correctamente (a) en toda carga
   fresca de página, con el tema que sea (sistema u oscuro/claro explícito), y (b) después de
   recargar manualmente la página tras cambiar el tema desde el menú de Streamlit.
2. *Limitación conocida, documentada, no corregida*: si alguien cambia de Claro a Oscuro desde el
   menú de Streamlit y sigue navegando SIN recargar la página, la banda queda con el fondo plano
   (no el degradé rojo) hasta la próxima recarga — el resto de la interfaz sí cambia de tema con
   normalidad. Se documenta como limitación aceptada en vez de forzar un workaround con JavaScript.

### Verificación de esta Adenda

- Playwright, carga fresca con `prefers-color-scheme: dark` emulado: clase confirmada
  `kpi-band-oscura tema-oscuro`, captura de pantalla adjunta al equipo.
- Playwright, carga fresca + toggle a Oscuro + `page.reload()`: clase y `background-image`
  (degradé) confirmados por `getComputedStyle`.
- Playwright, toggle a Oscuro sin recargar + rerun forzado (click en radio ya seleccionado): clase
  NO se actualiza — limitación confirmada y documentada, no un supuesto.

## Adenda 18 — Extensión del piloto de estilo al resto de la app

Con el modo oscuro ya verificado (Adenda 17), se extendió el patrón de "banda oscura para los
KPIs más críticos" y "barra segmentada" a las demás secciones, con el mismo criterio de la
Adenda 16: sólo donde el patrón representa algo real, nunca fabricando una composición o un
"top 3" que la sección no tiene.

### Dónde se aplicó

- **Finanzas**: los 7 KPIs fijos de la sección se separaron en dos niveles. Los 3 que resumen
  mejor la foto de la ronda — **EBITDA (USD)**, **Caja final (USD)** y **Deuda CP no planificada
  (USD)** — pasan a la banda oscura, con la misma lógica de favorable/desfavorable que ya usa
  Resultados (para Deuda CP no planificada el sentido se invierte: menos es favorable). Margen
  bruto, ROS, Deuda LP y Calificación crediticia quedan como tarjetas claras debajo, igual que
  antes.
- **Operaciones**: las tarjetas de "Capacidad empleada" (por país) pasan al lenguaje visual de
  barra segmentada (`stat-segment-card`), con dos segmentos: **Usado** y **Libre**. A diferencia
  de "Estado de Alertas" (Adenda 16), acá el 100% SÍ es un universo fijo real — la capacidad
  instalada de la planta — así que mostrar "Libre" como el complemento no es una proporción
  inventada, es literalmente lo que dice el reporte de Cesim. Se agregaron las clases CSS
  `.seg.uso` / `.seg.libre` (mismo componente, paleta propia, para no confundir "capacidad libre"
  con los colores de severidad de alertas).

### Dónde NO se aplicó, y por qué

- **Mercado** y **RRHH y Sostenibilidad** no tienen una fila de "3 KPIs fijos de la sección" ni una
  métrica de composición con universo fijo — son mayormente gráficos comparativos y de evolución.
  Forzar una banda oscura o una barra segmentada ahí habría significado inventar un KPI resumen que
  la sección no tiene, algo que va en contra del principio de no fabricar métricas del proyecto.
  Ambas secciones sí heredan los cambios globales (sidebar oscuro, tipografía Plus Jakarta Sans).
- Nota aparte, no vinculada al piloto de estilo: durante esta revisión se notó un gráfico de doble
  eje en Mercado → Evolución → "Trayectoria de precio y características" (`fig_traj`, con
  `yaxis`/`yaxis2`) que no estaba en la lista de 5 gráficos corregidos en la Adenda 15. Queda
  anotado como pendiente para una próxima pasada de auditoría visual, no se tocó en este corte para
  no mezclar el trabajo de estilo con más correcciones de gráficos sin que el equipo lo pida
  explícitamente.

### Verificación de esta Adenda

- `py_compile` sobre `app.py` — 0 errores.
- Smoke test con Playwright sobre las 5 secciones (Resultados, Mercado, Operaciones, Finanzas,
  RRHH y Sostenibilidad): ninguna muestra traceback ni error de Streamlit.
- Capturas de pantalla de Finanzas y Operaciones, en claro y en oscuro nativo de Streamlit:
  banda oscura y barra segmentada legibles y con contraste correcto en ambos modos.

## Adenda 19 — Fix de despliegue, limpieza de alertas, fin de Práctica, contraste del selectbox

Después de entregar la Adenda 18, el equipo reportó que la web desplegada se veía "sin estilo"
(banda oscura y barra segmentada como texto plano, sidebar claro). Diagnóstico confirmado con el
propio equipo: el `assets/style.css` desplegado estaba desactualizado respecto del `app.py`
desplegado (le faltaban los bloques de la Adenda 16 en adelante) — no fue un bug de este repo, fue
un problema de sincronización en el despliegue. Se aprovechó para blindar el `except
FileNotFoundError: pass` de la carga de CSS (línea ~932 de `app.py`): ahora si el archivo no
aparece, muestra un `st.warning` explícito en vez de degradar en silencio a una web sin estilo sin
ninguna pista de por qué.

Con el estilo ya confirmado andando bien en el despliegue, el equipo pidió tres cambios más:

### 1. Se sacó la alerta "I+D fuera de lo común"

A pedido explícito del equipo ("ensucian mucho y no siento que sirvan"). Era la única alerta de
Categoría 3 (supuesto propio de CADIZ, documentada como tal desde que se creó) — se removió el
bloque completo de `evaluar_alertas()`, dejando una nota en el código que explica qué había y por
qué se sacó. La alerta de "Entrada a tecnología nueva de la competencia" (Categoría 2, un hecho
confirmado por CESIM, no una estimación) sigue activa sin cambios — es la que de verdad importa.

### 2. Se eliminaron las rondas de Práctica de la navegación

A pedido explícito del equipo ("eliminemos las rondas de prueba también, no suman"): ya arrancó la
competencia Oficial (Ronda 0 y Ronda 1 jugadas), así que el ensayo previo dejó de aportar. Se sacó
el radio "Ecosistema" (Práctica/Oficial) del sidebar — `filtro_tipo` queda fijo en `'Oficial'` — y
`ronda_snapshot` ahora ofrece directamente Ronda 1 a 12. Los 3 archivos de Práctica
(`data/raw/practicas/*.xls`) NO se borraron del repo, solo dejaron de ser navegables desde la app,
por si hace falta revisarlos más adelante. Se limpiaron también los 3 condicionales muertos
`if filtro_tipo == 'Práctica':` que quedaban en las alertas de competencia (ya no podían dispararse).

### 3. Bug de contraste en "Equipo en foco" (sidebar oscuro)

El equipo mandó una captura: el selectbox "Equipo en foco" se veía como una caja blanca casi vacía,
con "CADIZ" apenas legible. Se verificó en vivo con Playwright (inspección de DOM y
`getComputedStyle`, no se asumió la causa) — mismo tipo de gotcha que ya había aparecido antes con
`stMetricLabel` (Adenda 15): la versión de Streamlit del repo ya no arma el selectbox con
`data-baseweb="select"` como asumía nuestro CSS (Adenda 16) — ahora usa un `react-aria-ComboBox`, y
la caja con fondo blanco es el DIV HIJO DIRECTO de esa clase. El selector viejo nunca matcheaba: el
texto salía en el color claro forzado por el `*` del sidebar, pero sobre el fondo blanco nativo sin
tocar — de ahí lo ilegible. Se agregó el selector `.react-aria-ComboBox > div` (se dejaron los
selectores viejos por si conviven versiones), verificado con `getComputedStyle` mostrando el fondo
translúcido correcto después del fix.

### 4. Bug de datos reportado — investigado, NO es un bug

El equipo marcó como posible error que, en Europa, la cuota de mercado Real salga por encima de la
Objetivo (12.1% vs. 10.0% en Combustión) mientras el gráfico de "Demanda estimada — Europa" muestra
que la demanda Real vino MÁS CHICA que la proyectada (74.7% del plan). Se auditó el código
(`gap_analysis.cuota_mercado_objetivo_vs_real`, ya documentado y verificado en adendas anteriores):
la Cuota Real divide por el tamaño de mercado REAL (Σ ventas reales, 7 equipos, 4 tecnologías); la
Cuota Objetivo viene de la celda del Excel de CADIZ, calculada contra el tamaño de mercado que el
modelo había ASUMIDO al planificar. Son dos denominadores distintos por diseño (cada cuota se
calcula contra el total de SU propio escenario, que es la forma correcta de medir participación de
mercado). Consecuencia matemática, no contradicción: si la demanda real vino más chica que la
proyectada, CADIZ puede terminar con una cuota más alta que el objetivo aunque haya vendido MENOS
unidades en términos absolutos de lo que había planeado — está repartiéndose una torta más chica.
Con los propios números que mandó el equipo, la cuenta cierra (aprox.): Objetivo ≈ 10,0% × 1,0M u.
≈ 100k u. planeadas; Real ≈ 12,1% × 751,4k u. ≈ 90,9k u. reales — CADIZ vendió menos de lo
planeado en unidades, pero el mercado entero se achicó todavía más. Se agregó una aclaración en el
`st.caption()` del propio gráfico de Cuota para que esta lectura no se preste a confusión de nuevo.
**Clasificación**: mecanismo verificado contra el código y consistente con los números que mostró
el equipo — no se pudo reconciliar al centavo por no tener acceso a los archivos de Ronda 2 en este
entorno de verificación, así que se presenta como razonamiento verificado, no como cifra exacta
recalculada desde cero.

### Pendiente de esta Adenda — pedido abierto, no resuelto todavía

El equipo preguntó si convendría otra forma de navegar entre Ronda y Equipo en el sidebar, ahora que
quedó más simple (sin el toggle de Ecosistema). Se le devolvieron opciones concretas para elegir en
vez de decidir unilateralmente — ver la respuesta en el chat. Ronda 2 en adelante.

### Verificación de esta Adenda

- `py_compile` sobre `app.py` — 0 errores.
- Smoke test con Playwright sobre las 5 secciones — sin traceback ni error de Streamlit.
- Captura del sidebar completo confirmando: sin toggle de Ecosistema, selector de Ronda 1-12,
  "Equipo en foco" con contraste correcto (fondo translúcido oscuro, texto legible).

## Pendiente para el próximo corte (actualizado)

- Definir con el equipo la forma de navegación Ronda/Equipo en el sidebar (pregunta abierta de esta
  Adenda).
- Corregir la fórmula de "Cuota de mercado CADIZ (promedio)" en el Excel (divide por 12 casilleros
  en vez de ponderar por volumen) — sigue siendo el próximo paso de fondo, pospuesto varias veces
  por la iteración de estilo.
- Ítems estéticos 5 y 6 de la Adenda 15 (etiquetas superpuestas en "Precio Promedio vs Volumen" y
  "Matriz Riesgo/Retorno", "Mix tecnológico" redundante) — pendientes de aprobación del equipo.
- Revisar el gráfico de doble eje "Trayectoria de precio y características" en Mercado → Evolución
  (hallazgo de la Adenda 18, no estaba en el relevamiento original de la Adenda 15).
- Resto de los pendientes de Adendas 12 y 13 sin cambios (ver arriba).
