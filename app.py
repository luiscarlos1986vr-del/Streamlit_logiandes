from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
import kpis as K

st.set_page_config(page_title="LogiAndes - Panel BI", layout="wide")

URL = (
    "https://docs.google.com/spreadsheets/d/1z68Fjbvpb-SiFSJK_fnaN4dmljm0Yv-yZ3gunGizvb8/"
    "export?format=csv&gid=45425025"
)
LOCAL = Path(__file__).parent / "logiandes.csv"

ORDEN_CANAL = ["Estándar urbano", "Express", "Programado"]
COLOR_CANAL = ["#2a7f8f", "#d1603d", "#8c8c8c"]
COLOR_REGION = {"Costa": "#d1603d", "Sierra": "#2a7f8f"}
FUENTE = "Fuente: LogiAndes S.A., logiandes.csv (enero-marzo 2026)"

@st.cache_data
def cargar():
    # Si el csv está junto a la app lo usamos; si no, bajamos la hoja de cálculo original.
    df = pd.read_csv(LOCAL if LOCAL.exists() else URL)
    return K.preparar(df)

df = cargar()

# ---------------------------------------------------------
# FILTROS GLOBALES Y EJECUTIVOS
# ---------------------------------------------------------
st.sidebar.header("🎯 Filtros del Panel")

# 1. Nivel Ejecutivo: Selección por Región
regiones_disponibles = ["Todas"] + list(sorted(df["region"].dropna().unique()))
region_sel = st.sidebar.selectbox("Región / Territorio", regiones_disponibles)

# 2. Nivel Ejecutivo: Selección por Meses
meses = st.sidebar.multiselect("Meses de Análisis", K.ORDEN_MES, default=K.ORDEN_MES)

with st.sidebar.expander("🛠️ Filtros Operativos Adicionales", expanded=False):
    # Filtrar provincias según la región seleccionada para mantener coherencia
    if region_sel != "Todas":
        provincias_base = sorted(df[df["region"] == region_sel]["provincia"].unique())
    else:
        provincias_base = sorted(df["provincia"].unique())
        
    provincias = st.multiselect("Provincia", provincias_base, default=provincias_base)
    canales = st.multiselect("Canal de entrega", ORDEN_CANAL, default=ORDEN_CANAL)
    tipos_all = sorted(df["tipo_cliente"].dropna().unique())
    tipos = st.multiselect("Tipo de cliente", tipos_all, default=tipos_all)

st.sidebar.caption("Los filtros afectan a todas las secciones. Las metas de los KPIs son supuestos del grupo (ver pestaña Documentación).")

# Aplicación de los filtros al DataFrame
condicion_region = df["region"] == region_sel if region_sel != "Todas" else True

f = df[
    condicion_region &
    df["mes"].isin(meses) &
    df["provincia"].isin(provincias) &
    df["canal_entrega"].isin(canales) &
    df["tipo_cliente"].isin(tipos)
]

st.title("LogiAndes: panel de servicio y ventas")
st.caption(FUENTE)

if f.empty:
    st.warning("No hay pedidos con los filtros seleccionados.")
    st.stop()

if len(f) < K.MIN_PEDIDOS:
    st.info(f"Los filtros dejan solo {len(f)} pedidos. Los indicadores pueden ser poco estables.")

tab1, tab2, tab3, tab4 = st.tabs(["Vista ejecutiva", "Análisis territorial", "Detalle operativo", "Documentación"])

# =====================================================================
# 1. Vista ejecutiva
# =====================================================================
with tab1:
    valores = K.calcular_kpis(f)
    st.subheader("¿Cómo estamos frente a las metas?")
    cols = st.columns(5)
    for col, ficha in zip(cols, K.FICHAS):
        clave = ficha["clave"]
        est = K.estado(clave, valores[clave])
        col.metric(f"{K.ICONO[est]} {ficha['nombre']}", K.formatear(clave, valores[clave]))
        col.caption(f"Meta {ficha['meta']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas (USD)", f"${f['ventas_asociadas_usd'].sum():,.0f}")
    c2.metric("Pedidos", f"{len(f):,}")
    c3.metric("Venta promedio por pedido (USD)", f"${f['ventas_asociadas_usd'].mean():,.2f}")

    # Evolución mensual: ventas en barras y tasa de reclamos en línea
    mensual = K.agrupar(f, ["mes"])
    fig_m = make_subplots(specs=[[{"secondary_y": True}]])
    fig_m.add_bar(x=mensual["mes"], y=mensual["ventas"], name="Ventas (USD)", marker_color="#9db8d3")
    fig_m.add_scatter(x=mensual["mes"], y=mensual["tasa_reclamos"], name="Reclamos por 1.000", mode="lines+markers", line_color="#d1603d", secondary_y=True)
    fig_m.update_yaxes(title_text="Ventas (USD)", rangemode="tozero", secondary_y=False)
    fig_m.update_yaxes(title_text="Reclamos por 1.000 pedidos", rangemode="tozero", secondary_y=True)
    fig_m.update_layout(title="Ventas y reclamos por mes", template="plotly_white", legend=dict(orientation="h", y=-0.2))

    # Cada provincia: cuánto vende contra qué tan mal le va en reclamos
    prov = K.agrupar(f, ["provincia", "region"])
    tasa_global = valores["tasa_reclamos"]
    fig_b = px.scatter(prov, x="ventas", y="tasa_reclamos", size="pedidos", color="region", text="provincia", color_discrete_map=COLOR_REGION, labels={"ventas": "Ventas (USD)", "tasa_reclamos": "Reclamos por 1.000 pedidos", "region": "Región"}, title="Peso de cada provincia en ventas frente a su tasa de reclamos", template="plotly_white", size_max=45)
    fig_b.update_traces(textposition="top center")
    fig_b.add_hline(y=tasa_global, line_dash="dash", line_color="gray", annotation_text=f"Promedio ({tasa_global:.1f})")
    fig_b.update_xaxes(rangemode="tozero")
    fig_b.update_yaxes(rangemode="tozero")

    g1, g2 = st.columns(2)
    g1.plotly_chart(fig_m, use_container_width=True)
    g2.plotly_chart(fig_b, use_container_width=True)
    st.caption("Tamaño del círculo: número de pedidos. " + FUENTE)

    peor = prov.sort_values("tasa_reclamos").iloc[-1]
    st.info(f"Lectura rápida: con los filtros actuales, {peor['provincia']} tiene la tasa de "
            f"reclamos más alta ({peor['tasa_reclamos']:.1f} por 1.000, sobre {int(
