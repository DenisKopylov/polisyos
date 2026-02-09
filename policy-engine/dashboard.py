import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import duckdb
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Policy Engine AI", layout="wide")

st.title("🏛️ Policy Engine: Decision Control Plane")


# 1. Подключение к БД
@st.cache_resource
def get_connection():
    db_path = REPO_ROOT / "data" / "databases" / "simulation.duckdb"
    return duckdb.connect(str(db_path), read_only=True)


try:
    conn = get_connection()
except Exception as e:
    st.error(f"DB Connection failed: {e}")
    st.stop()

# 2. Сайдбар: Выбор эксперимента
runs_df = conn.execute(
    """
    SELECT run_id, count(*) as steps, max(timestamp) as last_run
    FROM macro_history
    GROUP BY run_id
    ORDER BY last_run DESC
"""
).fetchdf()

if runs_df.empty:
    st.warning("No simulation data found. Run a Scientist experiment first.")
    st.stop()

selected_run_id = st.sidebar.selectbox("Select Simulation Run", runs_df["run_id"].tolist(), index=0)

# 3. Загрузка данных выбранного запуска
macro_df = conn.execute(
    "SELECT * FROM macro_history WHERE run_id = ? ORDER BY step", [selected_run_id]
).fetchdf()

# 4. KPI Метрики (последний шаг)
latest = macro_df.iloc[-1]
col1, col2, col3, col4 = st.columns(4)
col1.metric("GDP", f"{latest['gdp']/1e6:.2f}M", delta=None)
col2.metric("Unemployment", f"{latest['unemployment_rate']:.2%}", delta_color="inverse")
col3.metric(
    "Avg Income",
    f"{latest['avg_income']:.1f}",
    delta=f"{latest['avg_income'] - macro_df.iloc[0]['avg_income']:.1f}",
)
col4.metric(
    "Gov Budget",
    f"{latest['government_balance']/1e6:.2f}M",
    delta=f"{latest['government_balance'] - macro_df.iloc[0]['government_balance']:.2f}M",
)

# 5. Графики
st.subheader("📈 Macroeconomic Trajectory")

tab1, tab2, tab3 = st.tabs(["Income & GDP", "Employment", "Government Budget"])

with tab1:
    fig_inc = px.line(
        macro_df, x="step", y="avg_income", title="Average Income Growth", markers=True
    )
    st.plotly_chart(fig_inc, use_container_width=True)

with tab2:
    fig_emp = px.line(
        macro_df,
        x="step",
        y="unemployment_rate",
        title="Unemployment Rate",
        markers=True,
        color_discrete_sequence=["red"],
    )
    st.plotly_chart(fig_emp, use_container_width=True)

with tab3:
    fig_budget = px.line(
        macro_df,
        x="step",
        y="government_balance",
        title="Government Budget",
        markers=True,
        color_discrete_sequence=["green"],
    )
    fig_budget.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Balanced Budget")
    st.plotly_chart(fig_budget, use_container_width=True)

# 6. Микро-данные (Агенты)
st.subheader("🔬 Agent Population Micro-View")
step_slider = st.slider(
    "Select Simulation Step",
    min_value=int(macro_df["step"].min()),
    max_value=int(macro_df["step"].max()),
)

# Загружаем снапшот (если есть)
agents_df = conn.execute(
    """
    SELECT income, savings, is_employed
    FROM agents_snapshot
    WHERE run_id = ? AND step = ?
    LIMIT 1000
""",
    [selected_run_id, step_slider],
).fetchdf()

if not agents_df.empty:
    fig_hist = px.histogram(
        agents_df,
        x="income",
        color="is_employed",
        nbins=50,
        title=f"Income Distribution at Step {step_slider}",
    )
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info(f"No agent snapshot data for step {step_slider} (Snapshots are saved periodically).")
