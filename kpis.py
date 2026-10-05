import numpy as np
import pandas as pd

MESES = {1: "Enero", 2: "Febrero", 3: "Marzo"}
ORDEN_MES = list(MESES.values())

# Las metas y umbrales no vienen en la base. Nosotros las propusimos a partir del
# comportamiento observado del primer trimestre y las dejamos aquí para poder
# ajustarlas cuando las áreas de LogiAndes confirmen sus valores reales.
# En los cinco KPIs un valor más bajo es mejor.
METAS = {
    "tasa_reclamos": {"meta": 30.0, "umbral": 45.0},
    "mediana_entrega": {"meta": 130.0, "umbral": 150.0},
    "pct_tarde": {"meta": 2.0, "umbral": 5.0},
    "ventas_riesgo": {"meta": 3.0, "umbral": 5.0},
    "concentracion_top2": {"meta": 60.0, "umbral": 65.0},
}

UMBRAL_TARDE_MIN = 240   # definimos "entrega tardía" como más de 4 horas
MIN_PEDIDOS = 100        # por debajo de este tamaño de muestra advertimos al lector


def preparar(df):
    # Nosotros no limpiamos la base; solo tipamos la fecha y creamos columnas auxiliares.
    df = df.copy()
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"], errors="coerce")
    df["mes"] = pd.Categorical(df["fecha_pedido"].dt.month.map(MESES),
                               categories=ORDEN_MES, ordered=True)
    df["tarde"] = (df["tiempo_individual_entrega_min"] > UMBRAL_TARDE_MIN).astype(int)
    df["ventas_riesgo"] = df["ventas_asociadas_usd"] * df["reclamos_registrados"]
    return df


def wilson(k, n, z=1.96):
    # Intervalo de Wilson al 95% para la tasa de reclamos, expresado por 1.000 pedidos.
    # Lo usamos porque con pocos reclamos la tasa de un subgrupo es muy inestable.
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    p = k / n
    den = 1 + z ** 2 / n
    centro = (p + z ** 2 / (2 * n)) / den
    margen = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (centro - margen) * 1000, (centro + margen) * 1000


def agrupar(df, claves):
    g = (df.groupby(claves, observed=True)
           .agg(pedidos=("pedido_id", "count"),
                reclamos=("reclamos_registrados", "sum"),
                ventas=("ventas_asociadas_usd", "sum"),
                ventas_riesgo=("ventas_riesgo", "sum"),
                mediana_entrega=("tiempo_individual_entrega_min", "median"),
                pct_tarde=("tarde", "mean"))
           .reset_index())
    g["tasa_reclamos"] = g["reclamos"] / g["pedidos"] * 1000
    g["pct_tarde"] = g["pct_tarde"] * 100
    g["ic_bajo"], g["ic_alto"] = wilson(g["reclamos"], g["pedidos"])
    return g


def calcular_kpis(df):
    ventas_prov = df.groupby("provincia")["ventas_asociadas_usd"].sum().sort_values(ascending=False)
    total = df["ventas_asociadas_usd"].sum()
    return {
        "tasa_reclamos": df["reclamos_registrados"].mean() * 1000,
        "mediana_entrega": df["tiempo_individual_entrega_min"].median(),
        "pct_tarde": df["tarde"].mean() * 100,
        "ventas_riesgo": df["ventas_riesgo"].sum() / total * 100,
        "concentracion_top2": ventas_prov.head(2).sum() / total * 100,
    }


def estado(clave, valor):
    m = METAS[clave]
    if valor <= m["meta"]:
        return "Verde"
    if valor <= m["umbral"]:
        return "Amarillo"
    return "Rojo"


ICONO = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴"}

# Ficha técnica de cada KPI. Las metas se leen de METAS para que la ficha
# y el semáforo del dashboard siempre digan lo mismo.
FICHAS = [
    {
        "clave": "tasa_reclamos",
        "nombre": "Tasa de reclamos por 1.000 pedidos",
        "objetivo": "Medir la calidad percibida del servicio sin que el volumen distorsione la comparación.",
        "formula": "(Σ reclamos_registrados / nº de pedidos) × 1.000",
        "fuente": "logiandes.csv: reclamos_registrados, pedido_id",
        "frecuencia": "Mensual",
        "unidad": "reclamos por 1.000 pedidos",
        "interpretacion": "Menor es mejor. En subgrupos pequeños puede cambiar mucho con 1 o 2 casos, por eso mostramos el intervalo de confianza.",
        "audiencia": "Atención al cliente, gerencia general",
    },
    {
        "clave": "mediana_entrega",
        "nombre": "Mediana del tiempo de entrega",
        "objetivo": "Seguir la rapidez típica de la entrega sin que los valores extremos distorsionen el resultado.",
        "formula": "mediana(tiempo_individual_entrega_min)",
        "fuente": "logiandes.csv: tiempo_individual_entrega_min",
        "frecuencia": "Semanal",
        "unidad": "minutos",
        "interpretacion": "Menor es mejor. Depende del canal (Programado es lento a propósito) y de la distancia, así que se compara dentro de un mismo canal.",
        "audiencia": "Operaciones",
    },
    {
        "clave": "pct_tarde",
        "nombre": "% de entregas tardías (más de 240 min)",
        "objetivo": "Detectar la cola de entregas muy lentas que la mediana no muestra.",
        "formula": "(pedidos con tiempo_individual_entrega_min > 240 / nº de pedidos) × 100",
        "fuente": "logiandes.csv: tiempo_individual_entrega_min",
        "frecuencia": "Semanal",
        "unidad": "% de pedidos",
        "interpretacion": "Menor es mejor. El umbral de 240 min es una definición nuestra y Operaciones debería validarla.",
        "audiencia": "Operaciones, atención al cliente",
    },
    {
        "clave": "ventas_riesgo",
        "nombre": "% de ventas en riesgo por reclamo",
        "objetivo": "Dar a Finanzas una medida del dinero asociado a pedidos con reclamo, sin inventar rentabilidad.",
        "formula": "(Σ ventas_asociadas_usd de pedidos con reclamo / Σ ventas_asociadas_usd) × 100",
        "fuente": "logiandes.csv: ventas_asociadas_usd, reclamos_registrados",
        "frecuencia": "Mensual",
        "unidad": "% de las ventas",
        "interpretacion": "Menor es mejor. No es una pérdida real: es la venta de pedidos con reclamo. La base no trae costos ni devoluciones.",
        "audiencia": "Finanzas, gerencia general",
    },
    {
        "clave": "concentracion_top2",
        "nombre": "Concentración de ventas en las 2 provincias principales",
        "objetivo": "Medir cuánto depende el negocio de dos provincias.",
        "formula": "(ventas de las 2 provincias con más ventas / ventas totales) × 100",
        "fuente": "logiandes.csv: provincia, ventas_asociadas_usd",
        "frecuencia": "Trimestral",
        "unidad": "% de las ventas",
        "interpretacion": "Menor indica menos dependencia. Con una sola provincia filtrada vale 100% y no tiene sentido.",
        "audiencia": "Área comercial, gerencia general",
    },
]

for _f in FICHAS:
    _f["meta"] = f"≤ {METAS[_f['clave']]['meta']:g} {_f['unidad']}"
    _f["umbral"] = f"> {METAS[_f['clave']]['umbral']:g} {_f['unidad']} (rojo)"


def formatear(clave, valor):
    if clave == "tasa_reclamos":
        return f"{valor:.1f}"
    if clave == "mediana_entrega":
        return f"{valor:.0f} min"
    return f"{valor:.1f}%"
