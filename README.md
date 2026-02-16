# 🔮 DataQuery AI

**Natural Language to SQL Analytics Platform**

Ask questions in plain English. Get instant insights from your data—no SQL required.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **Natural Language to SQL** — Ask questions like "Top 10 brands by revenue" and get results instantly
- **Multi-dataset support** — Upload multiple CSVs; each becomes a queryable table
- **AI-powered** — Powered by Google Gemini or run locally with Ollama (unlimited, no API limits)
- **Interactive charts** — Bar, line, donut, scatter—auto-selected or choose manually
- **Export** — Download results as CSV or Excel
- **SQL Editor** — Write and run raw SQL for power users
- **Explainable AI** — Get plain-language explanations of how queries were built

---

## 🚀 Quick Start

### Option 1: Run locally

```bash
# Clone and install
git clone <your-repo-url>
cd "AI app project"
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Open **http://localhost:8501**

### Option 2: Docker

```bash
docker build -t dataquery-ai .
docker run -p 8501:8501 dataquery-ai
```

---

## ⚙️ Configuration

### Gemini API (cloud)

1. Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Paste it in the sidebar when the app loads
3. Or add to `.streamlit/secrets.toml`:
   ```toml
   GEMINI_API_KEY = "your-key"
   ```

### Ollama (local, unlimited)

1. Install [Ollama](https://ollama.ai)
2. Run: `ollama pull llama3.2`
3. In the app sidebar, select **Ollama** as the AI backend
4. No API key needed—unlimited queries

---

## 📁 Data

- Place `data.csv` in the project folder (loads by default)
- Or upload CSV files via the sidebar
- Each file becomes a table; use JOINs for related data

---

## 🛠 Tech Stack

- **Python** — Streamlit, Pandas, Plotly
- **AI** — Google Gemini API / Ollama
- **Database** — SQLite (in-memory)

---

## 📄 License

MIT
