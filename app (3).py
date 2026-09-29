import io
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="ICFES · Comparativo por curso", page_icon="📊", layout="wide")

AREAS = {
    "Lectura crítica": 3,
    "Matemáticas": 6,
    "Sociales y ciudadanas": 9,
    "Ciencias naturales": 12,
    "Inglés": 15,
}

@st.cache_data
def load_data(file_bytes):
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    rows = raw.iloc[17:].copy()
    rows = rows[rows[0].notna() & rows[1].notna()]
    data = pd.DataFrame({
        "Curso": rows[0].astype(int).astype(str),
        "Registro": rows[1].astype(str),
        "Estudiante": rows[2].astype(str).str.strip(),
        "Puntaje global": pd.to_numeric(rows[23], errors="coerce"),
    })
    for area, col in AREAS.items():
        data[area] = pd.to_numeric(rows[col], errors="coerce").values
    data = data.dropna(subset=["Puntaje global"])
    return data

st.title("Resultados ICFES · Comparativo por curso")
st.caption("Analice cursos por separado o en conjunto. Los indicadores y gráficos se actualizan al cambiar los filtros.")

# El Excel está versionado en la raíz del repositorio de GitHub, junto a esta app.
EXCEL_PATH = Path(__file__).resolve().parent / "Puntajes ICFES 2026 (1) con cursos.xls"
if not EXCEL_PATH.exists():
    st.error(
        "No se encontró 'Puntajes ICFES 2026 (1) con cursos.xls'. "
        "Verifique que el Excel esté en la misma carpeta de GitHub que esta app."
    )
    st.stop()
try:
    df = load_data(EXCEL_PATH.read_bytes())
except Exception as e:
    st.error(f"No se pudo leer el Excel del repositorio: {e}")
    st.stop()

courses = sorted(df["Curso"].unique())
with st.sidebar:
    st.header("Filtros")
    selected = st.multiselect("Cursos a comparar", courses, default=courses)
    metrics = st.multiselect("Áreas para analizar", list(AREAS), default=list(AREAS))
    min_score, max_score = int(df["Puntaje global"].min()), int(df["Puntaje global"].max())
    score_range = st.slider("Rango de puntaje global", min_score, max_score, (min_score, max_score))
    show_students = st.checkbox("Mostrar detalle nominal de estudiantes", value=False)

if not selected:
    st.warning("Seleccione por lo menos un curso.")
    st.stop()

f = df[df["Curso"].isin(selected) & df["Puntaje global"].between(*score_range)].copy()
if f.empty:
    st.warning("No hay estudiantes con los filtros seleccionados.")
    st.stop()

summary = f.groupby("Curso").agg(
    Estudiantes=("Registro", "count"),
    **{"Promedio global": ("Puntaje global", "mean"), "Mediana global": ("Puntaje global", "median"), "Máximo global": ("Puntaje global", "max"), "Mínimo global": ("Puntaje global", "min")}
).reset_index()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Cursos seleccionados", len(selected))
k2.metric("Estudiantes incluidos", len(f))
k3.metric("Promedio global del filtro", f["Puntaje global"].mean().round(1))
k4.metric("Curso con mayor promedio", str(summary.loc[summary["Promedio global"].idxmax(), "Curso"]))

st.subheader("1. Comparativo de puntaje global")
left, right = st.columns([1.2, 1])
with left:
    fig = px.bar(summary, x="Curso", y="Promedio global", color="Curso", text_auto=".1f", hover_data=["Estudiantes", "Mediana global", "Máximo global", "Mínimo global"], title="Promedio global por curso")
    fig.update_layout(showlegend=False, yaxis_title="Puntaje", xaxis_title="Curso")
    st.plotly_chart(fig, use_container_width=True)
with right:
    fig = px.box(f, x="Curso", y="Puntaje global", color="Curso", points="all", title="Distribución de puntajes globales")
    fig.update_layout(showlegend=False, yaxis_title="Puntaje global", xaxis_title="Curso")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("2. Desempeño promedio por área")
if metrics:
    area_long = f.melt(id_vars="Curso", value_vars=metrics, var_name="Área", value_name="Puntaje")
    area_summary = area_long.groupby(["Curso", "Área"], as_index=False)["Puntaje"].mean()
    fig = px.bar(area_summary, x="Área", y="Puntaje", color="Curso", barmode="group", text_auto=".1f", title="Promedio por área y curso")
    fig.update_layout(yaxis_title="Puntaje promedio", xaxis_title="Área")
    st.plotly_chart(fig, use_container_width=True)
    radar = area_summary.pivot(index="Área", columns="Curso", values="Puntaje").reset_index()
    rfig = go.Figure()
    for course in selected:
        if course in radar.columns:
            vals = radar[course].tolist()
            rfig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=radar["Área"].tolist() + radar["Área"].tolist()[:1], fill="toself", name=course))
    rfig.update_layout(title="Perfil comparativo por áreas", polar=dict(radialaxis=dict(visible=True)), height=500)
    st.plotly_chart(rfig, use_container_width=True)
else:
    st.info("Seleccione una o más áreas en el panel lateral.")

st.subheader("3. Tabla resumen")
st.dataframe(summary.style.format({"Promedio global":"{:.1f}","Mediana global":"{:.1f}"}), use_container_width=True, hide_index=True)

csv = summary.to_csv(index=False).encode("utf-8-sig")
st.download_button("Descargar resumen de cursos (CSV)", csv, "resumen_icfes_por_curso.csv", "text/csv")

if show_students:
    st.subheader("Detalle por estudiante")
    st.caption("Esta tabla contiene datos identificables. Compártala únicamente con personas autorizadas.")
    cols = ["Curso", "Registro", "Estudiante"] + metrics + ["Puntaje global"]
    st.dataframe(f[cols].sort_values(["Curso", "Puntaje global"], ascending=[True, False]), use_container_width=True, hide_index=True)
    st.download_button("Descargar detalle filtrado (CSV)", f[cols].to_csv(index=False).encode("utf-8-sig"), "detalle_icfes_filtrado.csv", "text/csv")

st.caption("Nota: los promedios se calculan solo con estudiantes que tienen puntaje global y cumplen el rango seleccionado. Los puntajes por área se promedian sobre los valores disponibles.")
