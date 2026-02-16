import textwrap

import pandas as pd
import streamlit as st

from db import describe_schema, get_connection, init_db
from nl_to_sql import SqlQuery, question_to_sql
from summary import summarize_results


def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def app() -> None:
    st.set_page_config(page_title="Talk2Data · SQL Assistant", layout="wide")

    st.title("💬 Talk2Data – SQL Data Analyst Assistant")
    st.caption(
        "Ask questions in natural language. The app will generate SQL with Google Gemini, "
        "run it on the active SQLite database (sample DB by default), visualize the results, "
        "and summarize key insights."
    )

    # Ensure the sample database exists (you can replace talk2data.db with your own).
    init_db()

    # Inspect the current database schema for display and for the NL→SQL model.
    conn = get_connection()
    try:
        schema_text = describe_schema(conn)
    finally:
        conn.close()

    with st.expander("Detected database schema", expanded=False):
        st.text(schema_text or "No schema detected.")

    st.markdown(
        textwrap.dedent(
            """
            **Tip:** You can swap out `talk2data.db` with any other SQLite database file
            that lives next to `main.py`. The app will re-detect its schema automatically.
            """
        )
    )

    question = st.text_input(
        "Ask a question about your data",
        placeholder="e.g. Show total sales by month for 2024",
    )

    col_run, col_clear = st.columns([1, 1])
    run_clicked = col_run.button("Run analysis", type="primary")
    if col_clear.button("Clear"):
        st.rerun()

    if not question:
        st.info("Enter a question and click **Run analysis** to get started.")
        return

    if not run_clicked:
        return

    with st.spinner("Translating your question into SQL with Gemini and running analysis..."):
        try:
            sql_query: SqlQuery = question_to_sql(question, schema_text)
            df = run_query(sql_query.sql)
        except Exception as e:
            st.error(f"Failed to generate or run SQL: {e}")
            return

    st.subheader("1. Generated SQL")
    st.code(sql_query.sql, language="sql")
    st.caption(sql_query.description)

    st.subheader("2. Results")
    if df.empty:
        st.warning("No data matched your query.")
    else:
        st.dataframe(df, use_container_width=True)

        # Try to visualize some common shapes.
        if set(df.columns) >= {"dimension", "value"}:
            st.markdown("**Chart:**")
            st.bar_chart(df.set_index("dimension")["value"])
        elif "order_date" in df.columns and "revenue" in df.columns:
            st.markdown("**Revenue over time:**")
            df_sorted = df.sort_values("order_date")
            st.line_chart(df_sorted.set_index("order_date")["revenue"])

    st.subheader("3. Summary")
    summary_text = summarize_results(df, question)
    st.markdown(summary_text)


if __name__ == "__main__":
    app()

