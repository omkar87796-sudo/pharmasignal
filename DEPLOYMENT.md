# Deploying PharmaSignal: Vercel (frontend) + Render (backend)

Both free tiers. Two separate deploys, ~15 minutes total.

## Project layout for this deployment

```
pharmasignal/
├── backend/          ← deploy this to Render
│   ├── main.py
│   ├── signal_detection.py
│   ├── severity_scoring.py
│   ├── fetch_data.py
│   ├── generate_synthetic_data.py
│   ├── requirements.txt
│   ├── render.yaml
│   └── data/
└── frontend/          ← deploy this to Vercel
    └── index.html
```

---

## Part 1: Backend on Render

### 1. Push the `backend/` folder to GitHub

```bash
cd pharmasignal
git init
git add .
git commit -m "PharmaSignal: backend + frontend"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/pharmasignal.git
git push -u origin main
```

### 2. Create the Render service

1. Go to **https://render.com** → sign up / log in (GitHub login is easiest)
2. **New → Web Service**
3. Connect your `pharmasignal` GitHub repo
4. Configure:
   - **Root directory**: `backend`
   - **Environment**: `Python 3`
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
5. Click **Create Web Service**

Render will build and deploy. You'll get a URL like:
```
https://pharmasignal-api.onrender.com
```

### 3. Verify it's live

```bash
curl https://pharmasignal-api.onrender.com/
curl https://pharmasignal-api.onrender.com/api/signals
```

⚠️ **Free tier note**: Render's free web services spin down after 15 minutes of inactivity. The first request after idling takes ~30-60 seconds to "wake up." This is normal — just something to mention if a recruiter tries it and it's slow on the first load.

---

## Part 2: Frontend on Vercel

### 1. Point the frontend at your live backend

Open `frontend/index.html`, find this line near the top of the `<script>` block:

```js
const API_BASE = window.PHARMASIGNAL_API_BASE || "http://localhost:8000";
```

Change the fallback to your real Render URL:

```js
const API_BASE = window.PHARMASIGNAL_API_BASE || "https://pharmasignal-api.onrender.com";
```

### 2. Deploy to Vercel

```bash
cd pharmasignal/frontend
vercel login          # if you haven't already
vercel --prod
```

Answer the prompts (project name `pharmasignal`, directory `./`). You'll get:
```
https://pharmasignal.vercel.app
```

### 3. Lock down CORS (recommended, optional but good practice)

Right now the backend's `main.py` has:
```python
allow_origins=["*"],
```

Once you know your Vercel URL, tighten it:
```python
allow_origins=["https://pharmasignal.vercel.app"],
```
Commit + push — Render will auto-redeploy.

---

## Testing the live stack

1. Open your Vercel URL
2. It should immediately load the 5 precomputed signals from your Render API
3. Try the **"Live-analyze a drug"** search bar — type e.g. `warfarin` and hit Analyze. This calls your Render backend, which calls the real FDA openFDA API live, and returns fresh PRR/ROR results for that drug — this is the feature that separates it from a static demo.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend shows "Couldn't reach the API" | Check `API_BASE` matches your exact Render URL (no trailing slash) |
| First load takes 30-60s | Normal — Render free tier cold start. Mention this if demoing live. |
| CORS error in browser console | Make sure `allow_origins` in `main.py` includes your Vercel domain |
| `/api/analyze/{drug}` returns 404 | That drug has no FAERS reports under that exact name — try a well-known drug name (ibuprofen, metformin, warfarin, sertraline) |

## CV / portfolio note

This gives you a genuinely deployed full-stack project: FastAPI backend
computing real pharmacovigilance statistics, calling a live external
regulatory API on demand, with a separately-deployed frontend consuming
it over REST. That's a stronger story than a single static file.
