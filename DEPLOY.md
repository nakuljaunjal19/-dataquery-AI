# Deploy DataQuery AI to a Live Website

Your Streamlit app can be live on the internet in a few minutes using **Streamlit Community Cloud** (free).

## Step 1: Push to GitHub

1. Create a new repository at [github.com/new](https://github.com/new)
2. Initialize git and push your project:

```powershell
cd "c:\Users\Nakul\Desktop\AI app project"
git init
git add app.py data.csv requirements.txt .streamlit/config.toml .gitignore
git commit -m "DataQuery AI - Natural Language to SQL"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

> **Important:** Do NOT add `.streamlit/secrets.toml` — your API key stays private.

## Step 2: Deploy on Streamlit Community Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
2. Click **"Create app"** → **"Yup, I have an app"**
3. Fill in:
   - **Repository:** `YOUR_USERNAME/YOUR_REPO_NAME`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL (optional):** e.g. `dataquery-ai` → `https://dataquery-ai.streamlit.app`
4. Click **"Advanced settings"**
5. Paste your secrets (replace with your actual Gemini key):

```toml
GEMINI_API_KEY = "your-key-here"
```

6. Click **"Deploy"**

### Demo dataset & shared links

The bundled **`data.csv`** in the repo is treated as a **demo / sample** dataset so visitors can try the app immediately. They can also **upload their own CSVs** or connect to a database. Users can turn off the demo with the **Include demo dataset** checkbox in the sidebar if they want uploads only.

## Step 3: Wait & Share

- Deployment usually takes 2–5 minutes
- Your app will be live at `https://YOUR-SUBDOMAIN.streamlit.app`
- Share the URL with anyone

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "data.csv not found" | Ensure `data.csv` is committed and pushed to GitHub |
| "Gemini API error" | Check GEMINI_API_KEY in Advanced settings → Secrets |
| App crashes on load | Try Python 3.10 or 3.11 in Advanced settings |
| Slow first load | Expected — CSV loads on first run; subsequent loads are cached |

## Alternative: Other Platforms

You can also deploy on:
- **Render** — [render.com](https://render.com) (free tier)
- **Railway** — [railway.app](https://railway.app)
- **Hugging Face** — [huggingface.co/spaces](https://huggingface.co/spaces)
