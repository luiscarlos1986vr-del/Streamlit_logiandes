# LogiAndes – Panel BI (Taller Práctico 2)

Dashboard en Streamlit con tres secciones (vista ejecutiva, análisis territorial, detalle operativo) y una pestaña de documentación con las fichas de los KPIs.

- `app.py`: dashboard.
- `kpis.py`: cálculo de KPIs, metas y fichas (el mismo código está copiado en el notebook).
- Datos: usa `logiandes.csv` si está junto a `app.py`; si no, descarga la hoja de cálculo de la fuente.

```
pip install -r requirements.txt
streamlit run app.py
```

Despliegue: Streamlit Community Cloud, archivo principal `app.py`.
