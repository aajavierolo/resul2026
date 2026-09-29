import io
from pathlib import Path
import pandas as pd
import streamlit as st

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

DEFAULT_FILE = Path(__file__).parent / "Puntajes ICFES 2026 (1) con cursos.xls"
if not DEFAULT_FILE.exists():
    st.error(
        "No se encontró el Excel. Confirme que 'Puntajes ICFES 2026 (1) con cursos.xls' "
        "esté en la raíz del repositorio, junto al archivo de la app."
    )
    st.stop()
try:
    file_bytes = DEFAULT_FILE.read_bytes()
    df = load_data(file_bytes)
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

tab_global, tab_areas = st.tabs(["Puntaje global", "Resultados por áreas"])

with tab_global:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Cursos seleccionados", len(selected))
    k2.metric("Estudiantes incluidos", len(f))
    k3.metric("Promedio global del filtro", f["Puntaje global"].mean().round(1))
    k4.metric("Curso con mayor promedio", str(summary.loc[summary["Promedio global"].idxmax(), "Curso"]))

    left, right = st.columns([1.2, 1])
    with left:
        st.bar_chart(summary.set_index("Curso")[["Promedio global"]], y_label="Puntaje", x_label="Curso")
    with right:
        st.subheader("Distribución de puntajes globales")
        st.line_chart(f.pivot(columns="Curso", values="Puntaje global"), y_label="Puntaje global")

    st.subheader("Resumen por curso")
    st.dataframe(summary.style.format({"Promedio global":"{:.1f}","Mediana global":"{:.1f}"}), use_container_width=True, hide_index=True)
    csv = summary.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar resumen global (CSV)", csv, "resumen_icfes_global_por_curso.csv", "text/csv")

with tab_areas:
    if metrics:
        area_long = f.melt(id_vars="Curso", value_vars=metrics, var_name="Área", value_name="Puntaje")
        area_summary = area_long.groupby(["Curso", "Área"], as_index=False)["Puntaje"].mean()
        st.subheader("Promedio por área y curso")
        area_chart = area_summary.pivot(index="Área", columns="Curso", values="Puntaje")
        st.bar_chart(area_chart, y_label="Puntaje promedio", x_label="Área")
        st.subheader("Detalle por estudiante")
        if show_students:
            st.caption("Esta tabla contiene datos identificables. Compártala únicamente con personas autorizadas.")
            cols = ["Curso", "Registro", "Estudiante"] + metrics + ["Puntaje global"]
            st.dataframe(f[cols].sort_values(["Curso", "Puntaje global"], ascending=[True, False]), use_container_width=True, hide_index=True)
            st.download_button("Descargar detalle filtrado (CSV)", f[cols].to_csv(index=False).encode("utf-8-sig"), "detalle_icfes_filtrado.csv", "text/csv")
        else:
            st.info("Para ver nombres y resultados individuales, active ‘Mostrar detalle nominal de estudiantes’ en el panel lateral.")
    else:
        st.info("Seleccione una o más áreas en el panel lateral.")

st.caption("Nota: los promedios se calculan solo con estudiantes que tienen puntaje global y cumplen el rango seleccionado. Los puntajes por área se promedian sobre los valores disponibles.")
