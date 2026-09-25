# SpeechTranslate Pro

## Run locally (Windows)
Double-click RUN.bat. The CMD opens and the browser opens automatically.
Then click the ⚙ Settings icon at the top-right and enter your Gemini API key.
The key is saved locally in `.env`; it is not placed in frontend JavaScript.

## YouTube transcript
Paste a YouTube video link into the box above "Original Speech" and click
"Get Transcript". The title and the full transcript are both pulled directly
by Gemini (it fetches the video through Google's own servers using just the
link), so this works reliably even from cloud hosts like Render, where
YouTube commonly blocks scraping-based methods. A Gemini API key must be
configured before this will work.

## Deploy live on Render (free)
1. Push this folder to a new GitHub repo (public or private).
2. Go to https://render.com → sign up/log in → **New +** → **Web Service**.
3. Connect your GitHub repo (Render auto-detects `render.yaml`, or set these manually):
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. Under **Environment**, add:
   - `GEMINI_API_KEY` = your Gemini API key (single-key setup), **or**
   - `GEMINI_API_KEYS` = `key1,key2,key3,...` — a comma-separated list of every
     key you have (15–20 keys from separate accounts works fine). The app
     picks a random key for each request and automatically tries the next
     one if a key hits its quota limit — this spreads load across accounts
     and avoids "quota exceeded" errors under heavy use. No spaces around
     the commas.
   - `GEMINI_MODEL` = `gemini-3.5-flash-lite` (optional, this is the default)
5. Click **Create Web Service**. Render gives you a free `https://your-app.onrender.com` link.

Setting the key(s) as an environment variable means you don't need to
open Settings in the browser after deploying — it's already configured.
Free-tier disk is temporary, so anything saved only via the in-app Settings
box can be lost on restart; the environment variable is the reliable way to
keep keys on a free plan. Note: the free plan also sleeps after 15
minutes of no traffic and takes ~30-50 seconds to wake back up on the next
visit.

### Note on using many Gemini accounts
Google's Gemini API free tier is meant for one account. Using several
accounts' keys together to raise your effective quota is a common practice,
but it sits outside the strict terms of the free tier, so treat it as
something you're doing at your own discretion.
