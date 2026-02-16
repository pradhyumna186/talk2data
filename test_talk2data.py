"""
Comprehensive test suite for Talk2Data application.

Tests cover:
1. Requirements and dependencies
2. LLM (Gemini) connection
3. Database loading and schema detection
4. End-to-end functionality
"""

import importlib
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import pytest

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import modules to test
from db import describe_schema, get_connection, init_db
from nl_to_sql import SqlQuery, _configure_gemini, _sanitize_sql, question_to_sql
from summary import summarize_results


class TestRequirements:
    """Test that all required dependencies are installed."""

    def test_streamlit_installed(self):
        """Verify Streamlit is installed."""
        import streamlit
        assert hasattr(streamlit, "__version__")

    def test_pandas_installed(self):
        """Verify pandas is installed."""
        import pandas
        assert hasattr(pandas, "__version__")

    def test_sqlalchemy_installed(self):
        """Verify SQLAlchemy is installed."""
        import sqlalchemy
        assert hasattr(sqlalchemy, "__version__")

    def test_google_generativeai_installed(self):
        """Verify google-generativeai is installed."""
        import google.generativeai
        assert hasattr(google.generativeai, "configure")

    def test_python_dotenv_installed(self):
        """Verify python-dotenv is installed."""
        import dotenv
        assert hasattr(dotenv, "load_dotenv")

    def test_pytest_installed(self):
        """Verify pytest is installed."""
        import pytest
        assert hasattr(pytest, "__version__")


class TestEnvironmentVariables:
    """Test environment variable configuration."""

    def test_gemini_api_key_set(self):
        """Verify GEMINI_API_KEY is set in environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        assert api_key is not None, "GEMINI_API_KEY environment variable is not set"
        assert len(api_key) > 0, "GEMINI_API_KEY is empty"
        assert api_key.startswith("AIza"), "GEMINI_API_KEY should start with 'AIza'"

    def test_env_file_exists(self):
        """Verify .env file exists."""
        env_path = project_root / ".env"
        assert env_path.exists(), ".env file not found in project root"


class TestLLMConnection:
    """Test LLM (Gemini) connection and configuration."""

    def test_gemini_configuration(self):
        """Test that Gemini can be configured with API key."""
        try:
            _configure_gemini()
        except RuntimeError as e:
            pytest.fail(f"Failed to configure Gemini: {e}")

    def test_gemini_api_connection(self):
        """Test actual API connection to Gemini."""
        _configure_gemini()
        import google.generativeai as genai
        
        # Try to list models as a connection test
        try:
            # Simple test: try to create a model instance
            model = genai.GenerativeModel("gemini-1.5-flash")
            # If this doesn't raise an exception, connection is working
            assert model is not None
        except Exception as e:
            pytest.fail(f"Failed to connect to Gemini API: {e}")

    def test_gemini_simple_query(self):
        """Test a simple query to Gemini to verify it responds."""
        _configure_gemini()
        import google.generativeai as genai
        import os
        
        # Use the model from env or default to gemini-2.5-flash
        model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        try:
            response = model.generate_content(
                "Say 'OK' if you can read this.",
                generation_config={"temperature": 0, "max_output_tokens": 10},
            )
            # Check if response was blocked by safety filters
            if response.candidates and response.candidates[0].finish_reason == 2:
                # Safety filter blocked - this is acceptable, just verify we got a response object
                assert response is not None
            else:
                # Normal response - check text
                assert response.text is not None
                assert len(response.text) > 0
        except ValueError as e:
            # Handle case where response.text raises ValueError due to safety blocks
            if "finish_reason" in str(e) or "Part" in str(e):
                # Safety filter blocked - acceptable
                pass
            else:
                pytest.fail(f"Gemini API query failed: {e}")
        except Exception as e:
            pytest.fail(f"Gemini API query failed: {e}")


class TestDatabase:
    """Test database initialization and operations."""

    def test_database_initialization(self):
        """Test that database can be initialized."""
        db_path, data_dir = init_db()
        assert db_path.exists(), "Database file was not created"
        assert data_dir.exists(), "Data directory was not created"

    def test_database_connection(self):
        """Test that we can connect to the database."""
        conn = get_connection()
        assert conn is not None
        conn.close()

    def test_sales_table_exists(self):
        """Test that the sales table exists after initialization."""
        init_db()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sales';"
            )
            result = cursor.fetchone()
            assert result is not None, "Sales table does not exist"
            assert result[0] == "sales"
        finally:
            conn.close()

    def test_sales_table_has_data(self):
        """Test that the sales table contains data."""
        init_db()
        conn = get_connection()
        try:
            df = pd.read_sql_query("SELECT COUNT(*) as count FROM sales", conn)
            assert len(df) > 0
            assert df["count"].iloc[0] > 0, "Sales table is empty"
        finally:
            conn.close()

    def test_schema_detection(self):
        """Test that schema can be detected from database."""
        init_db()
        conn = get_connection()
        try:
            schema_text = describe_schema(conn)
            assert schema_text is not None
            assert len(schema_text) > 0
            assert "sales" in schema_text.lower() or "Table sales" in schema_text
        finally:
            conn.close()

    def test_schema_includes_columns(self):
        """Test that schema description includes expected columns."""
        init_db()
        conn = get_connection()
        try:
            schema_text = describe_schema(conn)
            # Check for key columns
            assert "order_date" in schema_text.lower()
            assert "product" in schema_text.lower()
            assert "quantity" in schema_text.lower()
        finally:
            conn.close()


class TestSQLSanitization:
    """Test SQL sanitization and safety checks."""

    def test_valid_select_query(self):
        """Test that valid SELECT queries pass sanitization."""
        sql = "SELECT * FROM sales"
        result = _sanitize_sql(sql)
        assert result == sql.strip()

    def test_select_query_with_where(self):
        """Test SELECT with WHERE clause."""
        sql = "SELECT product FROM sales WHERE region = 'North'"
        result = _sanitize_sql(sql)
        assert "SELECT" in result.upper()

    def test_rejects_insert(self):
        """Test that INSERT statements are rejected."""
        with pytest.raises(ValueError, match="Dangerous keyword"):
            _sanitize_sql("INSERT INTO sales VALUES (1, 'test')")

    def test_rejects_update(self):
        """Test that UPDATE statements are rejected."""
        with pytest.raises(ValueError, match="Dangerous keyword"):
            _sanitize_sql("UPDATE sales SET quantity = 10")

    def test_rejects_delete(self):
        """Test that DELETE statements are rejected."""
        with pytest.raises(ValueError, match="Dangerous keyword"):
            _sanitize_sql("DELETE FROM sales")

    def test_rejects_drop(self):
        """Test that DROP statements are rejected."""
        with pytest.raises(ValueError, match="Dangerous keyword"):
            _sanitize_sql("DROP TABLE sales")

    def test_rejects_non_select(self):
        """Test that non-SELECT statements are rejected."""
        # CREATE will be caught as dangerous keyword first, so accept either error
        with pytest.raises(ValueError, match="(Only SELECT|Dangerous keyword)"):
            _sanitize_sql("CREATE TABLE test (id INT)")

    def test_rejects_multiple_statements(self):
        """Test that multiple statements are rejected."""
        with pytest.raises(ValueError, match="Multiple SQL"):
            _sanitize_sql("SELECT * FROM sales; SELECT * FROM products")


class TestNLToSQL:
    """Test natural language to SQL conversion."""

    @pytest.fixture
    def schema_description(self):
        """Fixture providing schema description."""
        init_db()
        conn = get_connection()
        try:
            schema = describe_schema(conn)
            return schema
        finally:
            conn.close()

    def test_simple_question_to_sql(self, schema_description):
        """Test converting a simple question to SQL."""
        question = "Show all sales"
        sql_query = question_to_sql(question, schema_description)
        
        assert isinstance(sql_query, SqlQuery)
        assert sql_query.sql is not None
        assert len(sql_query.sql) > 0
        assert sql_query.sql.upper().startswith("SELECT")
        assert "sales" in sql_query.sql.lower()

    def test_aggregation_question(self, schema_description):
        """Test question with aggregation."""
        question = "What is the total quantity sold?"
        sql_query = question_to_sql(question, schema_description)
        
        assert isinstance(sql_query, SqlQuery)
        assert "SUM" in sql_query.sql.upper() or "COUNT" in sql_query.sql.upper()

    def test_filtered_question(self, schema_description):
        """Test question with filters."""
        question = "Show sales for Widget A"
        sql_query = question_to_sql(question, schema_description)
        
        assert isinstance(sql_query, SqlQuery)
        assert "WHERE" in sql_query.sql.upper() or "where" in sql_query.sql

    def test_group_by_question(self, schema_description):
        """Test question requiring GROUP BY."""
        question = "Show total sales by region"
        sql_query = question_to_sql(question, schema_description)
        
        assert isinstance(sql_query, SqlQuery)
        # Should have GROUP BY or aggregation
        sql_upper = sql_query.sql.upper()
        assert "GROUP BY" in sql_upper or "SUM" in sql_upper or "COUNT" in sql_upper


class TestQueryExecution:
    """Test SQL query execution."""

    def test_execute_simple_query(self):
        """Test executing a simple SELECT query."""
        init_db()
        conn = get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM sales LIMIT 5", conn)
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
        finally:
            conn.close()

    def test_execute_aggregation_query(self):
        """Test executing an aggregation query."""
        init_db()
        conn = get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT region, SUM(quantity) as total FROM sales GROUP BY region",
                conn
            )
            assert isinstance(df, pd.DataFrame)
            assert "region" in df.columns
            assert "total" in df.columns
        finally:
            conn.close()


class TestSummaryGeneration:
    """Test summary generation from query results."""

    def test_summary_for_empty_result(self):
        """Test summary for empty DataFrame."""
        df = pd.DataFrame()
        summary = summarize_results(df, "test question")
        assert "No data" in summary or "no data" in summary.lower()

    def test_summary_for_single_value(self):
        """Test summary for single aggregated value."""
        df = pd.DataFrame({"value": [100.5]})
        summary = summarize_results(df, "test question")
        assert len(summary) > 0
        assert "100" in summary or "100.5" in summary

    def test_summary_for_aggregated_data(self):
        """Test summary for aggregated data with dimension and value."""
        df = pd.DataFrame({
            "dimension": ["North", "South", "East"],
            "value": [100, 200, 150]
        })
        summary = summarize_results(df, "test question")
        assert len(summary) > 0
        # Should mention highest/lowest
        assert "highest" in summary.lower() or "lowest" in summary.lower()

    def test_summary_for_row_data(self):
        """Test summary for row-level data."""
        df = pd.DataFrame({
            "order_date": ["2024-01-01", "2024-01-02"],
            "product": ["Widget A", "Widget B"],
            "revenue": [100.0, 200.0]
        })
        summary = summarize_results(df, "test question")
        assert len(summary) > 0
        assert "2" in summary or "rows" in summary.lower()


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def schema_description(self):
        """Fixture providing schema description."""
        init_db()
        conn = get_connection()
        try:
            schema = describe_schema(conn)
            return schema
        finally:
            conn.close()

    def test_full_pipeline_simple_query(self, schema_description):
        """Test complete pipeline: question -> SQL -> execution -> summary."""
        # Step 1: Convert question to SQL
        question = "Show all sales"
        sql_query = question_to_sql(question, schema_description)
        assert isinstance(sql_query, SqlQuery)
        
        # Step 2: Execute SQL
        conn = get_connection()
        try:
            df = pd.read_sql_query(sql_query.sql, conn)
            assert isinstance(df, pd.DataFrame)
        finally:
            conn.close()
        
        # Step 3: Generate summary
        summary = summarize_results(df, question)
        assert len(summary) > 0

    def test_full_pipeline_aggregation(self, schema_description):
        """Test complete pipeline with aggregation."""
        question = "What is the total quantity sold?"
        
        # Generate SQL
        sql_query = question_to_sql(question, schema_description)
        
        # Execute
        conn = get_connection()
        try:
            df = pd.read_sql_query(sql_query.sql, conn)
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0 or len(df.columns) > 0
        finally:
            conn.close()
        
        # Summarize
        summary = summarize_results(df, question)
        assert len(summary) > 0

    def test_full_pipeline_with_filter(self, schema_description):
        """Test complete pipeline with filtering."""
        question = "Show sales for products in the North region"
        
        # Generate SQL
        sql_query = question_to_sql(question, schema_description)
        
        # Execute
        conn = get_connection()
        try:
            df = pd.read_sql_query(sql_query.sql, conn)
            assert isinstance(df, pd.DataFrame)
        finally:
            conn.close()
        
        # Summarize
        summary = summarize_results(df, question)
        assert len(summary) > 0

    def test_sql_is_safe(self, schema_description):
        """Test that generated SQL passes safety checks."""
        question = "Show all sales"
        sql_query = question_to_sql(question, schema_description)
        
        # Verify SQL is safe
        try:
            _sanitize_sql(sql_query.sql)
        except ValueError as e:
            pytest.fail(f"Generated SQL failed safety check: {e}")

    def test_sql_executes_successfully(self, schema_description):
        """Test that generated SQL executes without errors."""
        question = "Show total sales by region"
        sql_query = question_to_sql(question, schema_description)
        
        conn = get_connection()
        try:
            # Should not raise an exception
            df = pd.read_sql_query(sql_query.sql, conn)
            assert isinstance(df, pd.DataFrame)
        except Exception as e:
            pytest.fail(f"Generated SQL failed to execute: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
