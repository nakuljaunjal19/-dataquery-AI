"""
DataQuery AI — Natural Language to SQL Analytics Platform
Ask questions in plain English. Get instant insights from your data.
"""

import hashlib
import json
import os
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import re
from pathlib import Path
from typing import Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent


def _is_streamlit_cloud() -> bool:
    """True when running on Streamlit Community Cloud (hide dev-only UI)."""
    sm = os.environ.get("STREAMLIT_SHARING_MODE", "").lower()
    if sm in ("true", "1"):
        return True
    if os.environ.get("STREAMLIT_CLOUD", "").lower() in ("true", "1", "yes"):
        return True
    if os.environ.get("DEPLOYMENT_PLATFORM", "").lower() == "streamlit_cloud":
        return True
    return False


# Bump when you ship — shown in footer if git hash unavailable (e.g. on Cloud)
APP_BUILD_ID = "2026.02.18-3"


def _footer_build_label() -> str:
    """Git short SHA locally; fallback helps verify Cloud deploys picked up latest push."""
    try:
        import subprocess

        h = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR),
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode().strip()
        return h
    except Exception:
        return APP_BUILD_ID


# --- Page config ---
st.set_page_config(
    page_title="DataQuery AI | Natural Language Analytics",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS: Portfolio-ready design ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(165deg, #0c0f1a 0%, #151b2d 40%, #0f1419 100%);
    }
    
    footer {visibility: hidden;}
    
    .hero-compact {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 40%, #a855f7 100%);
        padding: 0.65rem 1rem;
        border-radius: 12px;
        margin-bottom: 0.75rem;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .hero-compact h1 {
        color: white !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.2rem !important;
        margin: 0 !important;
        letter-spacing: -0.02em !important;
    }
    .hero-compact .tagline {
        color: rgba(255,255,255,0.88) !important;
        font-size: 0.82rem !important;
        margin: 0.2rem 0 0 !important;
    }
    
    .search-card {
        background: rgba(30, 35, 50, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(99, 102, 241, 0.2);
        padding: 1.1rem 1.25rem 1.25rem;
        border-radius: 14px;
        margin-bottom: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    }
    .stTextInput > div > div > input {
        background: rgba(15, 18, 28, 0.8) !important;
        color: #f1f5f9 !important;
        border: 2px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        font-size: 1.05rem !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: rgba(148, 163, 184, 0.6) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
    }
    
    .chip-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 1rem; }
    .chip {
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc !important;
        padding: 8px 16px;
        border-radius: 24px;
        font-size: 0.88rem;
        border: 1px solid rgba(99, 102, 241, 0.35);
    }
    .chip:hover { background: rgba(99, 102, 241, 0.25); }
    
    /* Result cards */
    .result-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #e2e8f0 !important;
    }
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    
    /* Success message */
    .stSuccess {
        background: rgba(34, 197, 94, 0.15) !important;
        border: 1px solid rgba(34, 197, 94, 0.4) !important;
        border-radius: 8px !important;
    }
    
    /* Code block */
    code {
        background: rgba(15, 23, 42, 0.8) !important;
        border-radius: 8px !important;
        padding: 0.3em 0.5em !important;
    }
    /* Rounded buttons */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)


def _sanitize_table_name(filename: str) -> str:
    """Convert filename to valid SQLite table name."""
    name = Path(filename).stem.lower().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^a-z0-9_]", "", name) or "table"


# Pre-validated SQL for suggestion buttons — matches demo `inventory` table (data.csv columns).
# Used for SQLite + inventory so recruiters always get working results without LLM mistakes.
DEMO_INVENTORY_SQL = {
    "Top 10 brands by revenue": """
SELECT brand, SUM(revenue_usd) AS total_revenue_usd
FROM inventory
GROUP BY brand
ORDER BY total_revenue_usd DESC
LIMIT 10
""".strip(),
    "Total sales by country": """
SELECT country, SUM(revenue_usd) AS total_revenue_usd
FROM inventory
GROUP BY country
ORDER BY total_revenue_usd DESC
""".strip(),
    "Average price by category": """
SELECT category, AVG(final_price_usd) AS avg_price_usd
FROM inventory
GROUP BY category
ORDER BY avg_price_usd DESC
""".strip(),
    "Units sold by payment method": """
SELECT payment_method, SUM(units_sold) AS total_units_sold
FROM inventory
GROUP BY payment_method
ORDER BY total_units_sold DESC
""".strip(),
    "Revenue by sales channel": """
SELECT sales_channel, SUM(revenue_usd) AS total_revenue_usd
FROM inventory
GROUP BY sales_channel
ORDER BY total_revenue_usd DESC
""".strip(),
}

# Default hints for bundled demo CSV (users can override in Data Dictionary)
DEFAULT_COLUMN_DESCRIPTIONS = {
    "order_id": "Unique order identifier",
    "order_date": "Date of order (YYYY-MM-DD)",
    "brand": "Product brand name",
    "model_name": "Product model",
    "category": "Product category",
    "revenue_usd": "Revenue in US dollars",
    "units_sold": "Number of units sold",
}


def get_canned_demo_sql(query: str, schema: dict, dialect: str) -> Optional[str]:
    """Return exact SQL for known demo questions when inventory table exists (SQLite)."""
    if dialect != "sqlite" or "inventory" not in schema:
        return None
    q = (query or "").strip()
    if q not in DEMO_INVENTORY_SQL:
        return None
    cols = set(schema["inventory"])
    need = {
        "Top 10 brands by revenue": {"brand", "revenue_usd"},
        "Total sales by country": {"country", "revenue_usd"},
        "Average price by category": {"category", "final_price_usd"},
        "Units sold by payment method": {"payment_method", "units_sold"},
        "Revenue by sales channel": {"sales_channel", "revenue_usd"},
    }
    if not need[q].issubset(cols):
        return None
    return DEMO_INVENTORY_SQL[q]


def build_schema_prompt_with_samples(schema: dict, conn) -> str:
    """Schema plus sample values per column (helps LLMs with filters and categories)."""
    parts = []
    for table, cols in schema.items():
        if not re.match(r"^[a-zA-Z0-9_]+$", table):
            continue
        parts.append(f"Table: {table}")
        parts.append(f"Columns: {', '.join(cols)}")
        try:
            df_s = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
            for col in cols[:20]:
                if col not in df_s.columns:
                    continue
                ser = df_s[col].dropna()
                if ser.empty:
                    continue
                uniq = ser.unique()[:3]
                samples = [str(x)[:50] for x in uniq]
                parts.append(f"  Sample values for {col}: {', '.join(samples)}")
        except Exception:
            pass
        parts.append("")
    return "\n".join(parts).strip()


def merge_column_descriptions_into_schema_text(
    base: str, schema: dict, descriptions: Optional[dict]
) -> str:
    """Append user-provided column meanings so the LLM can disambiguate joins and filters."""
    if not descriptions:
        return base
    lines = []
    for table, cols in schema.items():
        for col in cols:
            key_full = f"{table}.{col}"
            text = descriptions.get(key_full) or descriptions.get(col)
            if text and str(text).strip():
                lines.append(f"  {key_full}: {str(text).strip()}")
    if not lines:
        return base
    return (
        base
        + "\n\nColumn descriptions (from user data dictionary — use for filters and joins):\n"
        + "\n".join(lines)
    )


def validate_readonly_sql(sql: str) -> Tuple[bool, str]:
    """Reject non-SELECT and dangerous keywords before execution."""
    if not sql or not str(sql).strip():
        return False, "Empty query."
    s = str(sql).strip()
    if ";" in s:
        s = s.split(";")[0].strip()
    upper = s.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return False, "Only read-only SELECT queries are allowed."
    if re.search(
        r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|ATTACH|EXEC|EXECUTE|PRAGMA|REPLACE|GRANT|REVOKE)\b",
        upper,
    ):
        return False, "Blocked unsafe SQL keyword."
    return True, ""


def sql_cache_key(question: str, schema: dict, dialect: str, extra: str = "") -> str:
    h = hashlib.sha256(
        f"{question.strip().lower()}|{dialect}|{json.dumps(schema, sort_keys=True)}|{extra}".encode()
    ).hexdigest()[:32]
    return h


_SQL_CACHE_MAX = 40


def sql_cache_set(cache: dict, key: str, sql: str) -> None:
    if key in cache:
        del cache[key]
    cache[key] = sql
    while len(cache) > _SQL_CACHE_MAX:
        cache.pop(next(iter(cache)))


def build_database(uploaded_files: list, default_csv_path: Path, load_default_csv: bool = True) -> tuple:
    """
    Build SQLite DB from default CSV + uploaded files.
    Returns (conn, schema_dict, dialect) where schema_dict = {table_name: [columns]}.
    dialect = "sqlite" for prompt tuning.
    If load_default_csv is False, bundled demo data.csv is skipped (user chose uploads only).
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    schema = {}
    
    # 1. Load demo data.csv if present (labeled as demo in UI; table name stays "inventory" for queries)
    if load_default_csv and default_csv_path.exists():
        try:
            df = pd.read_csv(default_csv_path)
            df.to_sql("inventory", conn, if_exists="replace", index=False)
            schema["inventory"] = df.columns.tolist()
        except Exception as e:
            st.warning(f"Could not load data.csv: {e}")
    
    # 2. Load each uploaded file as a table
    for f in uploaded_files or []:
        try:
            df = pd.read_csv(f)
            table_name = _sanitize_table_name(f.name)
            if not table_name:
                table_name = "table_" + str(len(schema))
            base_name = table_name
            idx = 1
            while table_name in schema:
                table_name = f"{base_name}_{idx}"
                idx += 1
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            schema[table_name] = df.columns.tolist()
        except Exception as e:
            st.warning(f"Could not load {f.name}: {e}")
    
    return conn, schema, "sqlite"


def connect_to_database(db_type: str, host: str, port: str, database: str, user: str, password: str, extra: str = "") -> tuple:
    """
    Connect to external database and introspect schema.
    Returns (conn, schema_dict, dialect).
    db_type: postgresql, mysql, mssql
    """
    try:
        from sqlalchemy import create_engine, inspect
    except ImportError:
        st.error("Install SQLAlchemy: pip install sqlalchemy")
        return None, {}, "sqlite"

    from urllib.parse import quote_plus
    safe_pwd = quote_plus(password) if password else ""

    port = port or ""
    if db_type == "postgresql":
        try:
            import psycopg2
        except ImportError:
            st.error("Install psycopg2 for PostgreSQL: pip install psycopg2-binary")
            return None, {}, "sqlite"
        port = port or "5432"
        url = f"postgresql://{user}:{safe_pwd}@{host}:{port}/{database}"
        dialect = "postgresql"
    elif db_type == "mysql":
        try:
            import pymysql
        except ImportError:
            st.error("Install pymysql for MySQL: pip install pymysql")
            return None, {}, "sqlite"
        port = port or "3306"
        url = f"mysql+pymysql://{user}:{safe_pwd}@{host}:{port}/{database}"
        dialect = "mysql"
    elif db_type == "mssql":
        try:
            import pyodbc
        except ImportError:
            st.error("Install pyodbc for SQL Server: pip install pyodbc")
            return None, {}, "sqlite"
        port = port or "1433"
        driver = extra or "ODBC Driver 17 for SQL Server"
        url = f"mssql+pyodbc://{user}:{safe_pwd}@{host}:{port}/{database}?driver={quote_plus(driver)}"
        dialect = "mssql"
    else:
        return None, {}, "sqlite"

    try:
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        inspector = inspect(engine)
        schema = {}
        for table in inspector.get_table_names():
            cols = [c["name"] for c in inspector.get_columns(table)]
            schema[table] = cols
        return engine, schema, dialect
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return None, {}, "sqlite"


def _dialect_hints(dialect: str, today: str) -> str:
    """Return dialect-specific SQL hints for the prompt."""
    if dialect == "postgresql":
        return f"- Dialect: PostgreSQL. Use :: for casting. Today is {today}. Use CURRENT_DATE or date_trunc."
    if dialect == "mysql":
        return f"- Dialect: MySQL. Use CURDATE() for today ({today}). Use DATE_FORMAT for dates."
    if dialect == "mssql":
        return f"- Dialect: SQL Server. Use TOP N instead of LIMIT. Use GETDATE() for today ({today})."
    return f"- Dialect: SQLite. Date columns: YYYY-MM-DD text. Today is {today}. For last 30 days: date(column) >= date('now', '-30 days')"


def get_ollama_sql(
    question: str,
    schema: dict,
    model: str = "llama3.2",
    base_url: str = "http://localhost:11434",
    chat_history: list = None,
    dialect: str = "sqlite",
    schema_text: Optional[str] = None,
) -> Optional[str]:
    """Use local Ollama to translate natural language to SQL."""
    from datetime import date
    today = date.today().isoformat()
    schema_str = schema_text or "\n".join(f"Table: {t}\nColumns: {cols}" for t, cols in schema.items())
    context = ""
    if chat_history:
        context = "Previous Q&A:\n" + "\n".join(f"Q: {q}\nA: {s}" for q, s in chat_history[-6:]) + "\n\n"
    hints = _dialect_hints(dialect, today)
    prompt = f"""You are an expert SQL assistant.
Schema:
{schema_str}
{hints}

{context}Generate ONLY a valid {dialect.upper()} SELECT query. No markdown, no explanations.

Question: {question}"""
    try:
        import urllib.request
        import json
        url = f"{base_url.rstrip('/')}/api/generate"
        data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        sql = result.get("response", "").strip()
        sql = re.sub(r"^```(?:sql)?\s*", "", sql)
        sql = re.sub(r"\s*```$", "", sql)
        return sql.strip() if sql else None
    except Exception as e:
        err = str(e).lower()
        if "refused" in err or "10061" in err or "timed out" in err or "failed to establish" in err:
            st.error(
                "**Ollama not detected** (expected at **localhost:11434**). Start it with `ollama serve`, "
                "then `ollama pull llama3.2`. Or switch to **Gemini (cloud)** in the sidebar and add your API key."
            )
        else:
            st.error(
                f"Ollama error on {base_url}: {e}. If Ollama is not running, start `ollama serve` or use Gemini."
            )
        return None


def get_gemini_sql(
    question: str,
    schema: dict,
    api_key: str,
    chat_history: list = None,
    dialect: str = "sqlite",
    schema_text: Optional[str] = None,
) -> Optional[str]:
    """Use Gemini to translate natural language to SQL."""
    from datetime import date
    today = date.today().isoformat()  # YYYY-MM-DD
    schema_str = schema_text or "\n".join(f"Table: {t}\nColumns: {cols}" for t, cols in schema.items())
    context = ""
    if chat_history:
        context = "Previous Q&A:\n" + "\n".join(f"Q: {q}\nA: {s}" for q, s in chat_history[-6:]) + "\n\n"
    hints = _dialect_hints(dialect, today)
    prompt = f"""You are an expert SQL assistant.
Schema:
{schema_str}
{hints}

{context}Generate ONLY a valid {dialect.upper()} SELECT query. No markdown, no explanations, no backticks.

Question: {question}"""
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        sql = response.text.strip()
    except ImportError:
        # Fallback: REST API for Python 3.7 or when SDK not installed
        try:
            import urllib.request
            import urllib.error
            import json
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            if "candidates" not in result or not result["candidates"]:
                st.error("Gemini API returned no response. Check your API key.")
                return None
            sql = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else str(e)
            st.error(f"Gemini API error ({e.code}): {err_body[:200]}")
            return None
        except Exception as e:
            st.error(
                "Gemini could not translate that into SQL. Check your API key and network, "
                "or ask about your loaded tables (e.g. revenue, top products)."
            )
            with st.expander("Technical details"):
                st.caption(str(e))
            return None
    except Exception as e:
        st.error(
            "Gemini could not translate that into SQL. Check your API key and network, "
            "or ask a question about your loaded tables (e.g. revenue, top products)."
        )
        with st.expander("Technical details"):
            st.caption(str(e))
        return None
    
    # Clean common AI wrap-around
    sql = re.sub(r"^```(?:sql)?\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip()


def get_ollama_explanation(question: str, sql: str, model: str = "llama3.2", base_url: str = "http://localhost:11434") -> Optional[str]:
    """Use Ollama to explain the SQL query."""
    prompt = f"""The user asked: "{question}"
This SQL was written to answer it: {sql}
Explain in 2-4 simple sentences how this query works. Plain language, no jargon."""
    try:
        import urllib.request
        import json
        url = f"{base_url.rstrip('/')}/api/generate"
        data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        return result.get("response", "").strip() or None
    except Exception:
        return None


def get_gemini_explanation(question: str, sql: str, df_sample: pd.DataFrame, api_key: str) -> Optional[str]:
    """Ask Gemini to explain how the SQL query was written to solve the question."""
    prompt = f"""The user asked: "{question}"
This SQL query was written to answer it:

{sql}

Explain in 2-4 simple sentences how this query works—what steps it takes to solve the question. 
Use plain language, no jargon. Explain the logic: what it selects, groups, filters, or sorts, and why.
Example: "The query groups sales by brand, sums the revenue for each, sorts from highest to lowest, and returns the top 10."

Reply with ONLY the explanation, nothing else."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except ImportError:
        try:
            import urllib.request
            import urllib.error
            import json
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
            if result.get("candidates"):
                return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
        return None
    except Exception:
        return None


def _get_categorical_col(df: pd.DataFrame):
    for c in df.columns:
        if df[c].dtype in ["object", "string"] or (hasattr(df[c].dtype, "name") and df[c].dtype.name == "category"):
            return c
    return None


def _get_numeric_col(df: pd.DataFrame):
    for c in df.columns:
        if str(df[c].dtype) in ["int64", "float64", "int32", "float32"]:
            return c
    return None


def _get_date_col(df: pd.DataFrame):
    for c in df.columns:
        if "date" in c.lower() or "time" in c.lower():
            return c
    return None


def create_chart(df: pd.DataFrame, query_text: str, chart_type: str = "auto"):
    """Create Plotly chart - bar, line, scatter, or donut based on data and selection."""
    if df.empty or len(df) < 1:
        return None

    cat_col = _get_categorical_col(df)
    num_col = _get_numeric_col(df)
    date_col = _get_date_col(df)
    plot_df = df.head(20)
    title = f"Results: {query_text[:50]}{'...' if len(query_text) > 50 else ''}"

    layout = dict(
        paper_bgcolor="rgba(15, 23, 42, 0.8)",
        plot_bgcolor="rgba(30, 41, 59, 0.6)",
        font=dict(color="#e2e8f0", size=12),
        title_font=dict(size=16),
        margin=dict(b=100),
    )

    # Auto: line for date, donut for categories, else bar
    if chart_type == "auto":
        if date_col and num_col:
            chart_type = "line"
        elif cat_col and num_col and len(plot_df) <= 10:
            chart_type = "donut"
        else:
            chart_type = "bar"

    try:
        if chart_type == "line" and (date_col or cat_col) and num_col:
            x_col = date_col if date_col else cat_col
            fig = px.line(plot_df, x=x_col, y=num_col, title=title, template="plotly_dark", markers=True)
            fig.update_layout(**layout, xaxis_tickangle=-45,
                             colorway=["#6366f1", "#8b5cf6", "#a855f7", "#c084fc"])

        elif chart_type == "scatter" and cat_col and num_col:
            fig = px.scatter(plot_df, x=cat_col, y=num_col, title=title, template="plotly_dark")
            fig.update_layout(**layout, xaxis_tickangle=-45,
                             color_discrete_sequence=["#6366f1", "#8b5cf6", "#a855f7"])

        elif chart_type == "donut" and cat_col and num_col:
            fig = px.pie(plot_df, names=cat_col, values=num_col, title=title, template="plotly_dark", hole=0.5)
            fig.update_layout(**layout, colorway=px.colors.qualitative.Set3)

        elif chart_type == "pie" and cat_col and num_col:
            fig = px.pie(plot_df, names=cat_col, values=num_col, title=title, template="plotly_dark", hole=0)
            fig.update_layout(**layout, colorway=px.colors.qualitative.Set3)

        else:
            if not cat_col or not num_col:
                return None
            fig = px.bar(plot_df, x=cat_col, y=num_col, title=title, template="plotly_dark",
                        color=num_col, color_continuous_scale="purples")
            fig.update_layout(**layout, xaxis_tickangle=-45, showlegend=False)

        return fig
    except Exception:
        return None


def export_to_pdf(df: pd.DataFrame, query: str, fig=None) -> bytes:
    """Export results and optional chart to PDF."""
    from fpdf import FPDF
    from io import BytesIO
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DataQuery AI - Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Query: {query[:80]}{'...' if len(query) > 80 else ''}", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Results", ln=True)
    pdf.set_font("Helvetica", "", 8)
    cols = df.columns.tolist()
    col_w = 190 / len(cols) if cols else 40
    for col in cols:
        pdf.cell(col_w, 7, str(col)[:15], border=1)
    pdf.ln()
    for _, row in df.head(50).iterrows():
        for col in cols:
            pdf.cell(col_w, 6, str(row[col])[:12] if pd.notna(row[col]) else "", border=1)
        pdf.ln()
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def main():
    # --- Sidebar: AI backend selector ---
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        ai_backend = st.radio("AI Backend", ["Gemini (cloud)", "Ollama (local)"], horizontal=True, help="Ollama = unlimited, no API key")
    
    try:
        api_key_from_secrets = (st.secrets.get("GEMINI_API_KEY", "") or "").strip()
    except Exception:
        api_key_from_secrets = ""
    
    use_ollama = ai_backend == "Ollama (local)"
    on_cloud = _is_streamlit_cloud()
    
    if not use_ollama:
        st.sidebar.markdown(
            "**Bring your own Gemini API key** — each visitor uses their own quota "
            "(free tier at [Google AI Studio](https://aistudio.google.com/apikey))."
        )
        if on_cloud:
            st.sidebar.caption(
                "Public link: your key is not stored server-side for visitors. "
                "Paste your key below to run queries — the app owner’s quota is not used."
            )
        manual_key = st.sidebar.text_input(
            "🔑 Gemini API Key",
            value="",
            type="password",
            placeholder="Paste your API key (starts with AIza...)",
            help="Free key: aistudio.google.com/apikey — only used in your browser session.",
            key="gemini_manual_key",
        )
        manual_key = (manual_key or "").strip()
        # Pasted key wins; otherwise use Streamlit secrets (local .streamlit/secrets.toml or Cloud dashboard).
        api_key = manual_key or api_key_from_secrets
        if manual_key:
            pass  # visitor / you pasted a key — uses that quota only for this session
        elif api_key_from_secrets:
            if on_cloud:
                st.sidebar.caption(
                    "Using **GEMINI_API_KEY** from this app’s Streamlit secrets (your Cloud quota). "
                    "Paste a key above to use your own instead."
                )
            elif (BASE_DIR / ".streamlit" / "secrets.toml").is_file():
                st.sidebar.caption("Using **GEMINI_API_KEY** from `.streamlit/secrets.toml` (local dev).")
    else:
        api_key = ""
    
    if not use_ollama and not api_key:
        st.markdown("""
        <div class="hero">
            <h1>🔮 DataQuery AI</h1>
            <p class="tagline">Natural Language to SQL Analytics</p>
            <p class="sub">Connect your API key to get started</p>
        </div>
        """, unsafe_allow_html=True)
        st.warning(
            "⚠️ **Add your free Gemini API key** in the sidebar to get started. "
            "Keys are not saved on the server — each session uses what you paste."
        )
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("**Don't have a key?**")
            st.markdown("1. Open Google AI Studio (free)")
            st.markdown("2. Create an API key")
            st.markdown("3. Paste it in the sidebar under **Gemini API Key**")
        with col2:
            st.link_button("👉 Get API key (free)", "https://aistudio.google.com/apikey", type="primary")
        st.markdown("---")
        return
    
    # --- Initialize query history (before sidebar reads it) ---
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "column_descriptions" not in st.session_state:
        st.session_state.column_descriptions = dict(DEFAULT_COLUMN_DESCRIPTIONS)

    # --- Sidebar: File upload & schema ---
    with st.sidebar:
        st.success("Ollama ✓ Unlimited" if use_ollama else "Gemini API ready ✓")
        if not use_ollama:
            st.caption("Powered by Gemini — heavy usage? Use your own key above (free tier limits apply).")
        st.markdown("##### ✨ Why this SQL?")
        include_explanation = st.checkbox(
            "Include AI explanation (how the query works — uses one extra API call)",
            value=False,
            help="Useful for analysts; turn off to save Gemini quota.",
        )
        st.markdown("---")
        
        data_source = st.radio(
            "Data source",
            ["Upload CSV files", "Database connection"],
            help="Upload files or connect to PostgreSQL, MySQL, or SQL Server"
        )
        
        conn = None
        schema = {}
        dialect = "sqlite"
        
        if data_source == "Upload CSV files":
            st.markdown("#### 📁 Upload datasets")
            demo_path = BASE_DIR / "data.csv"
            has_demo = demo_path.exists()
            if has_demo:
                st.caption(
                    "**Demo dataset:** `data.csv` is a sample so anyone can try the app. "
                    "Upload your own CSV below to add tables or analyze your data."
                )
                use_demo = st.checkbox(
                    "Include demo dataset (sample sales data)",
                    value=True,
                    key="use_demo_data",
                    help="Uncheck to use only your uploaded files (no bundled sample).",
                )
            else:
                use_demo = False
                st.caption("Upload one or more CSV files. Each file becomes a queryable table.")
            uploaded = st.file_uploader(
                "Add CSV files",
                type=["csv"],
                accept_multiple_files=True,
                help="Upload CSVs. Each becomes a table. Matching columns enable JOINs.",
                label_visibility="collapsed"
            )
            conn, schema, dialect = build_database(
                list(uploaded) if uploaded else [],
                demo_path,
                load_default_csv=use_demo if has_demo else False,
            )
        else:
            st.markdown("#### 🔌 Database connection")
            db_type = st.selectbox("Database", ["postgresql", "mysql", "mssql"], format_func=lambda x: {"postgresql": "PostgreSQL", "mysql": "MySQL", "mssql": "SQL Server"}[x])
            db_host = st.text_input("Host", value=st.session_state.get("db_host", ""), placeholder="localhost", key="db_host")
            db_port = st.text_input("Port", value=st.session_state.get("db_port", ""), placeholder={"postgresql": "5432", "mysql": "3306", "mssql": "1433"}[db_type], key="db_port")
            db_name = st.text_input("Database name", value=st.session_state.get("db_name", ""), key="db_name")
            db_user = st.text_input("Username", value=st.session_state.get("db_user", ""), key="db_user")
            db_pass = st.text_input("Password", type="password", key="db_pass", help="Leave blank to use saved password")
            db_extra = st.session_state.get("db_extra", "ODBC Driver 17 for SQL Server")
            if db_type == "mssql":
                st.caption("ODBC driver name (e.g. ODBC Driver 17 for SQL Server)")
                db_extra = st.text_input("Driver", value=db_extra, key="db_extra")
            if st.button("Connect", key="db_connect") and db_host and db_name and db_user:
                conn, schema, dialect = connect_to_database(db_type, db_host, db_port, db_name, db_user, db_pass or st.session_state.get("db_pass", ""), db_extra)
                if conn and schema:
                    st.session_state.db_params = {"type": db_type, "host": db_host, "port": db_port, "name": db_name, "user": db_user, "pass": db_pass or st.session_state.get("db_pass", ""), "extra": db_extra}
                    st.session_state.db_host, st.session_state.db_port = db_host, db_port
                    st.session_state.db_name, st.session_state.db_user = db_name, db_user
                    if db_pass:
                        st.session_state.db_pass = db_pass
                    st.session_state.db_extra = db_extra
                    st.success("Connected!")
            if st.session_state.get("db_params"):
                p = st.session_state.db_params
                conn, schema, dialect = connect_to_database(p["type"], p["host"], p["port"], p["name"], p["user"], p["pass"], p["extra"])
                if conn and schema:
                    st.caption("Using saved connection. Re-enter credentials and Connect to change.")
                    if st.button("Disconnect", key="db_disconnect"):
                        for k in ["db_params", "db_host", "db_port", "db_name", "db_user", "db_pass", "db_extra"]:
                            st.session_state.pop(k, None)
                        st.rerun()
                elif not schema:
                    st.warning("Saved connection failed. Re-enter credentials and Connect.")
        
        if not schema:
            if data_source == "Upload CSV files":
                err = (
                    "❌ No data: enable **Include demo dataset** or upload at least one CSV."
                    if demo_path.exists()
                    else "❌ No data loaded. Upload at least one CSV file."
                )
            else:
                err = "❌ Connect to a database first (enter credentials and click Connect)."
            st.error(err)
            st.stop()
        
        st.markdown("---")
        st.markdown("#### 📋 Loaded tables")
        for table, cols in schema.items():
            with st.expander(f"**{table}** ({len(cols)} columns)", expanded=False):
                st.caption(", ".join(cols[:10]) + ("..." if len(cols) > 10 else ""))
        st.markdown("---")
        st.markdown("#### 📖 Data Dictionary")
        st.caption("Descriptions are sent to the AI with your schema — improves filters and JOINs.")
        desc_rows = []
        for table, cols in schema.items():
            for col in cols:
                k = f"{table}.{col}"
                default = DEFAULT_COLUMN_DESCRIPTIONS.get(col, "")
                desc_rows.append(
                    {
                        "table": table,
                        "column": col,
                        "description": st.session_state.column_descriptions.get(k, default),
                    }
                )
        with st.expander("Column meanings (editable)", expanded=False):
            if desc_rows:
                df_cd = pd.DataFrame(desc_rows)
                edited_cd = st.data_editor(
                    df_cd,
                    column_config={
                        "table": st.column_config.Column("Table", disabled=True, width="small"),
                        "column": st.column_config.Column("Column", disabled=True, width="small"),
                        "description": st.column_config.TextColumn(
                            "Plain English meaning", width="large"
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    num_rows="fixed",
                    key="column_desc_editor",
                )
                for _, row in edited_cd.iterrows():
                    kk = f"{row['table']}.{row['column']}"
                    st.session_state.column_descriptions[kk] = str(row.get("description") or "").strip()
            else:
                st.caption("No columns loaded.")
        st.markdown("---")
        if "query_history" in st.session_state and st.session_state.query_history:
            st.markdown("#### 📜 Recent queries")
            for q in st.session_state.query_history[-10:][::-1]:
                st.caption(f"• {q[:48]}{'...' if len(q) > 48 else ''}")
        st.markdown("---")
        st.caption("💡 Ask in plain English. Use JOIN for related tables.")
    
    table_count = len(schema)
    total_rows = 0
    try:
        for t in schema:
            r = pd.read_sql_query(f"SELECT COUNT(*) as c FROM {t}", conn)
            total_rows += int(r["c"].iloc[0])
    except Exception:
        pass

    schema_prompt_str = merge_column_descriptions_into_schema_text(
        build_schema_prompt_with_samples(schema, conn),
        schema,
        st.session_state.column_descriptions,
    )
    if "sql_cache" not in st.session_state:
        st.session_state.sql_cache = {}

    # --- Tabbed interface ---
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 AI Search", "💬 Chat", "✏️ SQL Editor", "📈 Data Trends"])

    # --- Voice/suggestion input: check URL for ?voice= or ?suggestion= ---
    try:
        qp = st.query_params
        voice_text = qp.get("voice", "") or ""
        suggestion_text = qp.get("suggestion", "") or ""
    except AttributeError:
        qp = st.experimental_get_query_params()
        voice_text = (qp.get("voice") or [""])[0]
        suggestion_text = (qp.get("suggestion") or [""])[0]
    if voice_text:
        st.session_state.search_query = voice_text
        try:
            st.query_params.clear()
        except AttributeError:
            st.experimental_set_query_params()
    elif suggestion_text:
        st.session_state.search_query = suggestion_text
        try:
            st.query_params.clear()
        except AttributeError:
            st.experimental_set_query_params()

    # Apply pending suggestion from chip click (set by on_click callback)
    if "pending_suggestion" in st.session_state and st.session_state.pending_suggestion:
        st.session_state.search_query = st.session_state.pending_suggestion
        del st.session_state.pending_suggestion

    with tab1:
        st.markdown(f"""
        <div class="hero-compact">
            <h1>🔮 DataQuery AI</h1>
            <p class="tagline">Natural Language to SQL • {table_count} table(s) • {total_rows:,} rows</p>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Upload your own CSV or use the sample dataset — then type a question below.")
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        st.caption("**Search** — ask in plain English. **Voice** — click 🎤 to speak your question (Chrome / Edge).")
        cq, cv = st.columns([5, 1])
        with cq:
            query = st.text_input(
                "Ask a question",
                placeholder="e.g., Top brands by revenue, or sales by country",
                label_visibility="collapsed",
                key="search_query"
            )
        with cv:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("🎤 Voice input"):
                st.caption("Speak your question — it fills the search box")
                st.components.v1.html("""
                <button id="vbtn" style="padding:8px 16px;border-radius:8px;background:#6366f1;color:white;border:none;cursor:pointer;">
                    Start speaking
                </button>
                <p id="vout" style="margin-top:8px;font-size:12px;color:#64748b;"></p>
                <script>
                const btn=document.getElementById('vbtn');
                const out=document.getElementById('vout');
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) { out.textContent='Voice not supported in this browser'; }
                else {
                    btn.onclick=function(){
                        out.textContent='Listening...';
                        const r=new SpeechRecognition();
                        r.continuous=false;
                        r.onresult=function(e){
                            const t=e.results[0][0].transcript;
                            out.textContent='Heard: '+t;
                            window.parent.location.href=window.location.pathname+'?voice='+encodeURIComponent(t);
                        };
                        r.onerror=function(){ out.textContent='Error. Try again.'; };
                        r.start();
                    };
                }
                </script>
                """, height=100)
        examples = [
            "Top 10 brands by revenue",
            "Total sales by country",
            "Average price by category",
            "Units sold by payment method",
            "Revenue by sales channel"
        ]
        if len(schema) > 1:
            examples.append("Combine data from multiple tables")
        st.caption("**Popular questions:** (tap to run)")

        def _set_query(q):
            st.session_state.pending_suggestion = q

        n_ex = len(examples)
        n_cols = 3
        for row_start in range(0, n_ex, n_cols):
            cols = st.columns(n_cols)
            for j in range(n_cols):
                i = row_start + j
                if i < n_ex:
                    with cols[j]:
                        st.button(examples[i], key=f"chip_{i}", on_click=_set_query, args=(examples[i],), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
        if not query:
            st.session_state.pop("search_result_bundle", None)
            st.markdown("""
            <div class="search-card" style="text-align: center; padding: 3rem;">
                <p style="font-size: 1.1rem; color: #94a3b8;">👆 Enter a question above to search your data</p>
                <p style="font-size: 0.95rem; color: #64748b;">Try asking about revenue, sales by country, top brands, and more</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            bundle_ck = sql_cache_key(query, schema, dialect)
            br = st.session_state.get("search_result_bundle")
            use_bundle = (
                br is not None
                and br.get("key") == bundle_ck
                and isinstance(br.get("df"), pd.DataFrame)
                and br.get("sql")
            )
            if use_bundle:
                sql = br["sql"]
                df_result = br["df"]
                canned = bool(br.get("canned", False))
            else:
                canned = get_canned_demo_sql(query, schema, dialect)
                with st.spinner("Running query..." if canned else "Translating to SQL..."):
                    if canned:
                        sql = canned
                    else:
                        sql = st.session_state.sql_cache.get(bundle_ck)
                        if sql is None:
                            sql = (
                                get_ollama_sql(query, schema, dialect=dialect, schema_text=schema_prompt_str)
                                if use_ollama
                                else get_gemini_sql(query, schema, api_key.strip(), dialect=dialect, schema_text=schema_prompt_str)
                            )
                            if sql:
                                sql_cache_set(st.session_state.sql_cache, bundle_ck, sql)
            
            if not sql:
                st.error("Could not generate SQL. Try rephrasing your question.")
            else:
                have_df = False
                if use_bundle:
                    have_df = True
                else:
                    ok_sql, sql_err = validate_readonly_sql(sql)
                    if not ok_sql:
                        st.warning(
                            "That response is not a safe read-only query, or it does not match your data. "
                            "Ask something about **your tables** — for example totals, trends, or top categories."
                        )
                        with st.expander("Technical details"):
                            st.code(sql, language="sql")
                            st.caption(sql_err)
                    else:
                        try:
                            df_result = pd.read_sql_query(sql, conn)
                        except sqlite3.OperationalError as e:
                            st.error("The query could not run on your data. Try simpler wording or check column names in the sidebar.")
                            with st.expander("Technical details"):
                                st.code(sql, language="sql")
                                st.write(str(e))
                        except sqlite3.ProgrammingError as e:
                            st.error("The query structure was not valid for this database. Try a simpler question.")
                            with st.expander("Technical details"):
                                st.code(sql, language="sql")
                                st.write(str(e))
                        except Exception as e:
                            st.error("Something went wrong running the query. Try rephrasing or ask about columns shown in the sidebar.")
                            with st.expander("Technical details"):
                                st.code(sql, language="sql")
                                st.caption(str(e))
                        else:
                            st.session_state.search_result_bundle = {
                                "key": bundle_ck,
                                "sql": sql,
                                "df": df_result.copy(),
                                "canned": canned,
                            }
                            have_df = True

                if have_df:
                    if df_result.empty:
                        st.warning("No data found for that query.")
                        with st.expander("SQL"):
                            st.code(sql, language="sql")
                    else:
                        if not use_bundle:
                            st.session_state.query_history = (st.session_state.query_history + [query])[-10:]
                        st.success("✅ Query executed successfully!")
                        with st.expander("🤖 How was this query written?", expanded=include_explanation):
                            if canned:
                                st.info(
                                    "This uses a **pre-validated SQL** statement for the demo `inventory` table "
                                    "(matches data.csv). No AI translation step — reliable for demos."
                                )
                            elif include_explanation:
                                with st.spinner("Explaining the solution..."):
                                    explanation = get_ollama_explanation(query, sql) if use_ollama else get_gemini_explanation(query, sql, df_result, api_key.strip())
                                if explanation:
                                    st.info(explanation)
                                else:
                                    st.caption("Could not generate (check API quota). View the SQL below.")
                            else:
                                st.caption("Turn on **Why this SQL? → Include AI explanation** in the sidebar for a plain-language walkthrough.")
                        with st.expander("🔍 View generated SQL", expanded=False):
                            st.code(sql, language="sql")
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.markdown("### 📋 Results Table")
                            st.dataframe(df_result, use_container_width=True, height=400)
                            d1, d2 = st.columns(2)
                            with d1:
                                csv = df_result.to_csv(index=False).encode("utf-8")
                                st.download_button("📥 CSV", csv, "results.csv", "text/csv", use_container_width=True)
                            with d2:
                                try:
                                    pdf_bytes = export_to_pdf(df_result, query)
                                    st.download_button("📥 PDF Report", pdf_bytes, "report.pdf", "application/pdf", use_container_width=True)
                                except Exception:
                                    pass
                        with col2:
                            chart_type = st.radio(
                                "Chart type",
                                ["Auto", "Bar", "Line", "Pie", "Donut", "Scatter"],
                                horizontal=True,
                                key="chart_type",
                            )
                            ct = "auto" if chart_type == "Auto" else chart_type.lower()
                            fig = create_chart(df_result, query, ct)
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Chart requires categorical and numeric columns.")
                        with st.expander("📊 Raw Data Explorer", expanded=False):
                            st.dataframe(df_result, use_container_width=True, height=300)

    with tab2:
        st.markdown("### 💬 Chat")
        st.caption("Multi-turn conversation. Ask follow-ups like \"Now only USA\" or \"Add a chart\".")
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []  # [(question, sql), ...] for LLM context

        def _render_msg(msg):
            role_label = "**You:**" if msg["role"] == "user" else "**Assistant:**"
            st.markdown(f"{role_label} {msg['content']}")
            if msg.get("sql"):
                with st.expander("🔍 SQL"):
                    st.code(msg["sql"], language="sql")
            if msg.get("df") is not None and not msg["df"].empty:
                st.dataframe(msg["df"], use_container_width=True, height=250)
                fig_chat = create_chart(msg["df"], msg["content"], "auto")
                if fig_chat:
                    st.plotly_chart(fig_chat, use_container_width=True)

        for msg in st.session_state.chat_messages:
            try:
                with st.chat_message(msg["role"]):
                    _render_msg(msg)
            except AttributeError:
                st.markdown("---")
                _render_msg(msg)

        chat_input = None
        try:
            chat_input = st.chat_input("Ask a follow-up or new question...")
        except AttributeError:
            ci_col, btn_col = st.columns([5, 1])
            with ci_col:
                chat_input = st.text_input("Your message", placeholder="Ask a follow-up or new question...", key="chat_text", label_visibility="collapsed")
            with btn_col:
                chat_submit = st.button("Send", key="chat_send")
            if not (chat_submit and chat_input):
                chat_input = None
            elif chat_input:
                chat_input = chat_input.strip()
        if chat_input:
            st.session_state.chat_messages.append({"role": "user", "content": chat_input})
            with st.chat_message("assistant"):
                with st.spinner("Translating to SQL..."):
                    hist = st.session_state.chat_history
                    hist_ctx = json.dumps(hist[-6:], default=str)
                    ck_chat = sql_cache_key(chat_input, schema, dialect, extra=hist_ctx)
                    sql = st.session_state.sql_cache.get(ck_chat)
                    if sql is None:
                        sql = (
                            get_ollama_sql(
                                chat_input,
                                schema,
                                chat_history=hist,
                                dialect=dialect,
                                schema_text=schema_prompt_str,
                            )
                            if use_ollama
                            else get_gemini_sql(
                                chat_input,
                                schema,
                                api_key.strip(),
                                chat_history=hist,
                                dialect=dialect,
                                schema_text=schema_prompt_str,
                            )
                        )
                        if sql:
                            sql_cache_set(st.session_state.sql_cache, ck_chat, sql)
                if not sql:
                    st.error("Could not generate SQL. Try rephrasing or ask about your tables.")
                    st.session_state.chat_messages.append({"role": "assistant", "content": "I couldn't translate that to SQL. Try rephrasing.", "df": None, "sql": None})
                else:
                    ok_sql, sql_err = validate_readonly_sql(sql)
                    if not ok_sql:
                        st.warning(
                            "That is not a safe read-only query for your data. "
                            "Ask follow-ups about your tables, or switch to the Search tab."
                        )
                        with st.expander("Technical details"):
                            st.code(sql, language="sql")
                            st.caption(sql_err)
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": "I could not run that as a safe query. Try asking about your data columns.", "df": None, "sql": sql}
                        )
                    else:
                        try:
                            df_chat = pd.read_sql_query(sql, conn)
                            if df_chat.empty:
                                st.warning("No data found.")
                                resp = "No rows matched your question."
                            else:
                                st.success(f"✅ {len(df_chat)} rows")
                                resp = f"Found {len(df_chat)} rows."
                            st.session_state.chat_history.append((chat_input, sql))
                            st.session_state.chat_history = st.session_state.chat_history[-6:]
                            st.session_state.chat_messages.append({"role": "assistant", "content": resp, "df": df_chat, "sql": sql})
                        except Exception as e:
                            st.error("The query could not run. Try simpler wording or check your column names.")
                            with st.expander("Technical details"):
                                st.code(sql, language="sql")
                                st.caption(str(e))
                            st.session_state.chat_messages.append(
                                {"role": "assistant", "content": "The query failed to run. Try rephrasing.", "df": None, "sql": sql}
                            )
            if "chat_text" in st.session_state:
                st.session_state.chat_text = ""
            st.rerun()

        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state.chat_messages = []
            st.session_state.chat_history = []
            st.rerun()

    with tab3:
        st.markdown("### ✏️ SQL Editor")
        st.caption("Write and run raw SQL. Tables: " + ", ".join(schema.keys()))
        first_tbl = next(iter(schema), "inventory")
        ph = f"SELECT TOP 10 * FROM {first_tbl}" if dialect == "mssql" else f"SELECT * FROM {first_tbl} LIMIT 10"
        sql_raw = st.text_area("Enter SQL", placeholder=ph, height=120, key="sql_editor")
        if st.button("Run SQL", type="primary", key="run_sql"):
            if sql_raw.strip():
                ok_raw, raw_err = validate_readonly_sql(sql_raw.strip())
                if not ok_raw:
                    st.warning("Only read-only **SELECT** queries are allowed here (no INSERT/UPDATE/DELETE).")
                    with st.expander("Technical details"):
                        st.caption(raw_err)
                else:
                    try:
                        df_sql = pd.read_sql_query(sql_raw.strip(), conn)
                        st.success(f"✅ {len(df_sql)} rows")
                        st.dataframe(df_sql, use_container_width=True, height=350)
                        fig = create_chart(df_sql, "SQL Result", "auto")
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                    except sqlite3.OperationalError as e:
                        st.error("SQL could not run. Check table and column names.")
                        with st.expander("Technical details"):
                            st.caption(str(e))
                    except Exception as e:
                        st.error("Could not run that query.")
                        with st.expander("Technical details"):
                            st.caption(str(e))
            else:
                st.warning("Enter a SQL query.")

    with tab4:
        st.markdown("### 📈 Full Data Trends")
        st.caption("Overview charts from your loaded data")
        try:
            first_table = next(iter(schema), "inventory")
            limit_sql = f"SELECT TOP 5000 * FROM {first_table}" if dialect == "mssql" else f"SELECT * FROM {first_table} LIMIT 5000"
            df_all = pd.read_sql_query(limit_sql, conn)
            if "brand" in df_all.columns and "revenue_usd" in df_all.columns:
                by_brand = df_all.groupby("brand")["revenue_usd"].sum().reset_index().sort_values("revenue_usd", ascending=False).head(15)
                fig1 = px.bar(by_brand, x="brand", y="revenue_usd", title="Revenue by Brand", template="plotly_dark", color="revenue_usd", color_continuous_scale="purples")
                fig1.update_layout(paper_bgcolor="rgba(15, 23, 42, 0.8)", plot_bgcolor="rgba(30, 41, 59, 0.6)", font=dict(color="#e2e8f0"))
                st.plotly_chart(fig1, use_container_width=True)
            if "country" in df_all.columns and "revenue_usd" in df_all.columns:
                by_country = df_all.groupby("country")["revenue_usd"].sum().reset_index().sort_values("revenue_usd", ascending=False).head(12)
                fig2 = px.pie(by_country, names="country", values="revenue_usd", title="Revenue by Country", template="plotly_dark", hole=0.4)
                fig2.update_layout(paper_bgcolor="rgba(15, 23, 42, 0.8)", colorway=px.colors.qualitative.Set3)
                st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            st.info("Add data with brand, country, and revenue columns to see trends.")

    # --- Footer ---
    st.markdown("---")
    ai_tech = "Ollama" if use_ollama else "Gemini AI"
    st.markdown(f"""
    <div style="text-align: center; padding: 1.5rem 0; color: #64748b; font-size: 0.85rem;">
        <strong>DataQuery AI</strong> — Natural Language to SQL • Built with Streamlit & {ai_tech}
    </div>
    """, unsafe_allow_html=True)
    st.caption(f"Build: {_footer_build_label()} — after a Git push, this should update once Streamlit Cloud redeploys.")


if __name__ == "__main__":
    main()
