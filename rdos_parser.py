"""
Parser único de RDOS de CESIM (cualquier ronda, .xls o .xlsx, path o file-like en memoria).

Reemplaza a parse_rdos.py (que solo devolvía valores crudos) agregando el rastreo JERÁRQUICO
de unidad: cada fila hereda la unidad del subtítulo más cercano arriba (ej. "Combustión, miles
unidades" dentro de una sección titulada "Capacidad empleada, %"), salvo que la fila misma
declare su propia unidad (ej. "Costo de producción interna por unidad, USD" dentro de una
sección sin unidad en el título) -- eso SIEMPRE gana sobre lo heredado.

Regla de escala (Regla CESIM verificada, verificada además bottom-up contra el propio RDOS:
precio de venta x volumen vendido x tipo de cambio, sumado en las 3 áreas y 2 tecnologías
activas, coincide con el total de "Ingresos por ventas" de la Cuenta de Resultados aplicando
este x1000, con 0,003% de diferencia -- ver checkpoint de escala del proyecto):
    "miles USD"      -> x1000, unidad resuelta "miles USD"
    "miles unidades" -> x1000, unidad resuelta "miles unidades"
    cualquier otra unidad explícita en la propia fila (USD, EUR, RMB, %, kWh, m3, kg, ton,
        u., unidades, acción/acciones) sin la palabra "miles"  -> x1, esa misma unidad
    sin ninguna unidad (ni propia ni heredada)                  -> x1, unidad "sin_unidad"

Cada fila devuelve tanto el valor CRUDO (tal como lo exporta CESIM) como la unidad resuelta
en texto (para consumidores que aplican su propia tabla de conversión, ej. 05_HISTORICO_EQUIPOS
-> DATA_EXPORT vía _UNIT_CANON_MAP) y el valor ya escalado (para consumidores que necesitan el
número final directo, ej. extract_hist_pais() -> _ENGINE_FINANCIERO).
"""
import re
import xlrd

TEAMS = ["CADIZ", "CEOS", "CHIEF", "CLAVE", "CUORE", "FOCUS", "TOKIO"]

_MILES_RE = re.compile(r"miles\s+(usd|de\s+usd|unidades|de\s+unidades)", re.IGNORECASE)
_UNIT_TOKEN_RE = re.compile(r"\b(USD|EUR|RMB|%|kWh|m3|kg|u\.|unidades|ton|acci[oó]n(?:es)?)\b", re.IGNORECASE)


def _resolve_unit(label, inherited):
    """Devuelve (unidad_texto, multiplicador) para 'label', dado el contexto (unidad_texto,
    multiplicador) heredado del subtítulo/sección más cercano. La unidad propia de la fila
    siempre gana sobre la heredada."""
    m = _MILES_RE.search(label)
    if m:
        return ("miles USD", 1000) if "usd" in m.group(1).lower() else ("miles unidades", 1000)
    m2 = _UNIT_TOKEN_RE.search(label)
    if m2:
        return (m2.group(1), 1)
    return inherited or ("sin_unidad", 1)


def parse_rdos_workbook(file_or_path, sheet_name="Results"):
    """Lee un RDOS (.xls binario -- formato nativo de exportación de CESIM) desde un path o un
    objeto tipo archivo (BytesIO / UploadedFile de Streamlit) y devuelve una lista de filas
    planas, en el mismo orden del archivo:
        {section, label, type: "data"|"subheader",
         values:  {team: valor_crudo},               # tal cual lo exporta CESIM
         scaled:  {team: valor_crudo * multiplicador},
         unit:    "miles USD" | "miles unidades" | "USD" | "%" | ... | "sin_unidad"}
    'section' y 'label' son exactamente el texto de sección/rubro del RDOS -- compatibles 1:1
    con lo que ya esperaba 24_HISTORICO_RONDAS (columnas Sección/Rubro), así que cualquier
    lógica de canonicalización ya escrita contra esos nombres sigue funcionando sin cambios.
    """
    # Nota (bug real, corregido): un mismo RDOS se parsea DOS VECES en generar_excel() (una vez desde
    # extract_hist_pais(), otra desde build_historico_equipos()) -- con un path a disco cada llamada
    # reabre el archivo sin problema, pero con un objeto tipo archivo EN MEMORIA (io.BytesIO / el
    # UploadedFile que entrega Streamlit) la 2ª llamada encontraba el cursor al final (ya consumido
    # por la 1ª lectura) y f.read() devolvía b"" -- xlrd.open_workbook(file_contents=b"") explota con
    # un TypeError confuso ("not NoneType") en vez de un error claro. Se reposiciona el cursor al
    # inicio antes de leer (no-op para un archivo recién abierto, corrige el caso de reuso).
    if hasattr(file_or_path, "read"):
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        data = file_or_path.read()
    else:
        data = None
    wb = xlrd.open_workbook(file_contents=data) if data is not None else xlrd.open_workbook(file_or_path)
    sh = wb.sheet_by_name(sheet_name)

    out = []
    current_section = None
    unit_ctx = None
    for r in range(sh.nrows):
        row = sh.row_values(r)
        label = str(row[0]).strip()
        rest = row[1:8]
        rest_str = [str(x).strip() for x in rest]
        if label == "" and all(x == "" for x in rest_str):
            continue
        if rest_str[:2] == ["CADIZ", "CEOS"]:
            continue
        if all(x == "" for x in rest_str):
            is_top = bool(re.search(r"miles USD|Informe de|Indicadores Financieros|Tasas de inter|Creaci[oó]n de valor|% *$", label))
            if is_top:
                current_section = label
                unit_ctx = _resolve_unit(label, None)
            else:
                unit_ctx = _resolve_unit(label, unit_ctx)
            out.append({"section": current_section, "label": label, "type": "subheader",
                        "values": {}, "scaled": {}, "unit": (unit_ctx or ("sin_unidad", 1))[0]})
            continue
        row_unit = _resolve_unit(label, unit_ctx)
        values, scaled = {}, {}
        for i, team in enumerate(TEAMS):
            v = rest[i]
            values[team] = v
            scaled[team] = (v * row_unit[1]) if isinstance(v, (int, float)) else v
        out.append({"section": current_section, "label": label, "type": "data",
                    "values": values, "scaled": scaled, "unit": row_unit[0]})
    return out
