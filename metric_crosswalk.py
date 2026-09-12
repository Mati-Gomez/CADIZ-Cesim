# -*- coding: utf-8 -*-
"""
metric_crosswalk.py -- Tabla de cruce entre las dos fuentes de datos del control de gestión:

  - PROYECTADO: CADIZ_Gestion_v2.xlsx!DATA_EXPORT, leído directamente por gap_analysis.load_proyeccion()
    (columnas: round/scenario/status/team/region/technology/metric/value/unit/...).
  - REAL: el DataFrame tidy que arma cesim_parser.build_historico() a partir de los .xls de RDOS
    (columnas: Ronda/Tipo_Ronda/Ronda_Numero/Ronda_Orden/Modulo/Estado/Seccion/Subgrupo/Metrica/
    Empresa/Valor).

Cada entrada fue VERIFICADA numéricamente contra Ronda 1 (dato real conocido en ambos lados) antes de
incorporarse acá -- no se listó ninguna combinación a ciegas. Ver Informe_V2.md / README de la
integración web para el detalle de la verificación.

Alcance de este primer corte (Adenda 8): los 8 KPIs de cabecera de la sección Finanzas del tablero
(seccion_finanzas() en app.py), Global (no desglosado por país/tecnología). Se amplía a otras
secciones en cortes siguientes, con la misma disciplina de verificación fila a fila.

Cada entrada:
    "clave_kpi": {
        "label": "Nombre para mostrar en el tablero",
        "proyeccion": {"metric": <valor de la columna 'metric' en cadiz_proyeccion.csv>,
                        "region": <valor de la columna 'region'>},
        "real": {"estado": <valor de 'Estado' en el df de cesim_parser>,
                  "metrica": <valor de 'Metrica'>,
                  "seccion": <valor de 'Seccion', o None si no aplica>},
        "tipo": "usd" | "ratio" | "texto",   # cómo formatear e interpretar el gap
        "gap_favorable": "real_mayor" | "real_menor" | None,  # para colorear el gap (None = texto)
    }
"""

CROSSWALK_FINANZAS = {
    "ebitda": {
        "label": "EBITDA",
        "proyeccion": {"metric": "EBITDA", "region": "Global"},
        "real": {"estado": "Cuenta de resultados, miles USD, Global",
                 "metrica": "Beneficio operativo antes de depreciación (EBITDA)", "seccion": None},
        "tipo": "usd",
        "gap_favorable": "real_mayor",
    },
    "margen_bruto": {
        "label": "Margen bruto",
        "proyeccion": {"metric": "Indicadores Financieros Claves — Margen bruto", "region": "Global"},
        "real": {"estado": "Ratios e indicadores financieros clave", "metrica": "Margen bruto", "seccion": None},
        "tipo": "ratio",
        "gap_favorable": "real_mayor",
    },
    "ros": {
        "label": "ROS",
        "proyeccion": {"metric": "ROS", "region": "Global"},
        "real": {"estado": "Ratios e indicadores financieros clave",
                 "metrica": "Rentabilidad de las ventas (ROS)", "seccion": None},
        "tipo": "ratio",
        "gap_favorable": "real_mayor",
    },
    "caja_final": {
        "label": "Caja final",
        "proyeccion": {"metric": "Efectivo y equivalentes", "region": "Global"},
        "real": {"estado": "Hoja de Balance, miles USD, Global",
                 "metrica": "Efectivo y equivalentes de efectivo", "seccion": None},
        "tipo": "usd",
        "gap_favorable": "real_mayor",
    },
    "deuda_cp_no_planificada": {
        "label": "Deuda CP no planificada",
        "proyeccion": {"metric": "Deudas a corto plazo (automática)", "region": "Global"},
        "real": {"estado": "Hoja de Balance, miles USD, Global",
                 "metrica": "Deudas a corto plazo (no planificadas)", "seccion": None},
        "tipo": "usd",
        "gap_favorable": "real_menor",
    },
    "deuda_lp": {
        "label": "Deuda LP",
        "proyeccion": {"metric": "Deudas a largo plazo", "region": "Global"},
        "real": {"estado": "Hoja de Balance, miles USD, Global",
                 "metrica": "Deudas a largo plazo", "seccion": None},
        "tipo": "usd",
        "gap_favorable": None,   # ni más ni menos deuda LP es "mejor" per se -- es una decisión, no un resultado a evaluar
    },
    "calificacion_crediticia": {
        "label": "Calificación crediticia",
        "proyeccion": {"metric": "Indicadores Financieros Claves — Calificación crediticia", "region": "Global"},
        "real": {"estado": "Ratios e indicadores financieros clave",
                 "metrica": "Calificación crediticia", "seccion": None},
        "tipo": "texto",
        "gap_favorable": None,
    },
    "ingresos_por_ventas": {
        "label": "Ingresos por ventas",
        "proyeccion": {"metric": "Ingresos por ventas", "region": "Global"},
        "real": {"estado": "Cuenta de resultados, miles USD, Global",
                 "metrica": "Ingresos por ventas", "seccion": None},
        "tipo": "usd",
        "gap_favorable": "real_mayor",
    },
}
