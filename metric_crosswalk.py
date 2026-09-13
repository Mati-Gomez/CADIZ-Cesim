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
        "gap_favorable": None,
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

CROSSWALK_MERCADO = {
    "demanda_estimada_eeuu": {
        "label": "Demanda estimada — EE.UU.",
        "proyeccion": {"metric": "Demanda estimada CADIZ (unidades)", "region": "EE.UU."},
        "real": {"estado": "Informe de mercado, EE.UU.", "metrica": "Demanda, miles unidades", "seccion": None},
        "tipo": "unidades", "gap_favorable": None,
    },
    "demanda_estimada_china": {
        "label": "Demanda estimada — China",
        "proyeccion": {"metric": "Demanda estimada CADIZ (unidades)", "region": "China"},
        "real": {"estado": "Informe de mercado, China", "metrica": "Demanda, miles unidades", "seccion": None},
        "tipo": "unidades", "gap_favorable": None,
    },
    "demanda_estimada_europa": {
        "label": "Demanda estimada — Europa",
        "proyeccion": {"metric": "Demanda estimada CADIZ (unidades)", "region": "Europa"},
        "real": {"estado": "Informe de mercado, Europa", "metrica": "Demanda, miles unidades", "seccion": None},
        "tipo": "unidades", "gap_favorable": None,
    },
}

CROSSWALK_OPERACIONES = {
    "utilizacion_capacidad_eeuu": {
        "label": "Utilización de capacidad — EE.UU.",
        "proyeccion": {"metric": "Utilización de capacidad", "region": "EE.UU."},
        "real": {"estado": "Detalles de fabricación", "metrica": "Capacidad empleada, %", "seccion": None},
        "real_calc": "utilizacion_capacidad", "real_calc_region": "EE.UU.",
        "tipo": "ratio", "gap_favorable": None,
    },
    "utilizacion_capacidad_china": {
        "label": "Utilización de capacidad — China",
        "proyeccion": {"metric": "Utilización de capacidad", "region": "China"},
        "real": {"estado": "Detalles de fabricación", "metrica": "Capacidad empleada, %", "seccion": None},
        "real_calc": "utilizacion_capacidad", "real_calc_region": "China",
        "tipo": "ratio", "gap_favorable": None,
    },
}

CROSSWALK_RESULTADOS = {
    "eps": {
        "label": "EPS",
        "proyeccion": {"metric": "EPS", "region": "Global"},
        "real": {"estado": "Ratios e indicadores financieros clave",
                 "metrica": "Ganancias por acción (EPS), USD", "seccion": None},
        "tipo": "usd_accion", "gap_favorable": "real_mayor",
    },
    "fcf": {
        "label": "FCF (flujo de caja libre)",
        "proyeccion": {"metric": "FCF", "region": "Global"},
        "real": {"estado": "NO PUBLICADO POR CESIM", "metrica": "NO PUBLICADO POR CESIM", "seccion": None},
        "tipo": "usd", "gap_favorable": "real_mayor",
        "real_no_publicado": True,
    },
    "retorno_accionista": {
        "label": "Retorno total acumulado del accionista [PROXY]",
        "proyeccion": {"metric": "Retorno total acumulado del accionista (PROXY)", "region": "Global"},
        "real": {"estado": "Ratios e indicadores financieros clave",
                 "metrica": "Retorno total acumulado del accionista (p.a.), %", "seccion": None},
        "tipo": "ratio", "gap_favorable": "real_mayor",
    },
}
