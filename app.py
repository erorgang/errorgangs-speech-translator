import os
import re
import json
import time
import random
import shutil
import tempfile
from pathlib import Path
import requests
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
try:
    import yt_dlp
except ImportError:
    yt_dlp=None

BASE=Path(__file__).resolve().parent
DATA_DIR=Path.home()/".error_gang_speech_translator"
DATA_DIR.mkdir(parents=True,exist_ok=True)
ENV=DATA_DIR/".env"
_LEGACY_ENV=BASE/".env"

def load_env():
    if not ENV.exists() and _LEGACY_ENV.exists():
        # migrate a key saved by an older version of this app (stored next to app.py)
        # into the persistent, update-proof location so it survives future app updates
        try: ENV.write_text(_LEGACY_ENV.read_text(encoding="utf-8"),encoding="utf-8")
        except OSError: pass
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip())
def save_key(key):
    lines=ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    out=[]; found=False
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            out.append("GEMINI_API_KEY="+key); found=True
        elif line.strip(): out.append(line)
    if not found: out.append("GEMINI_API_KEY="+key)
    if not any(x.startswith("GEMINI_MODEL=") for x in out): out.append("GEMINI_MODEL=gemini-3.5-flash-lite")
    ENV.write_text("\n".join(out)+"\n",encoding="utf-8")
    os.environ["GEMINI_API_KEY"]=key

import random

def get_gemini_keys():
    """Return every configured Gemini API key as a list. Supports a single key
    (GEMINI_API_KEY) and/or a comma-separated pool (GEMINI_API_KEYS) for load-
    spreading and automatic failover across multiple keys/accounts."""
    keys=[]
    raw=os.getenv("GEMINI_API_KEYS","").strip()
    if raw:
        keys=[k.strip() for k in raw.split(",") if k.strip()]
    single=os.getenv("GEMINI_API_KEY","").strip()
    if single and single not in keys:
        keys.append(single)
    return keys

load_env()
app=Flask(__name__)
LANGS=[
    {"flag":"🇬🇧","cc":"gb","native":"English","en":"English"},
    {"flag":"🇪🇸","cc":"es","native":"Español","en":"Spanish"},
    {"flag":"🇫🇷","cc":"fr","native":"Français","en":"French"},
    {"flag":"🇩🇪","cc":"de","native":"Deutsch","en":"German"},
    {"flag":"🇮🇹","cc":"it","native":"Italiano","en":"Italian"},
    {"flag":"🇵🇹","cc":"pt","native":"Português","en":"Portuguese"},
    {"flag":"🇳🇱","cc":"nl","native":"Nederlands","en":"Dutch"},
    {"flag":"🇸🇦","cc":"sa","native":"العربية","en":"Arabic"},
    {"flag":"🇵🇰","cc":"pk","native":"اردو","en":"Urdu"},
    {"flag":"🇮🇳","cc":"in","native":"हिन्दी","en":"Hindi"},
    {"flag":"🇧🇩","cc":"bd","native":"বাংলা","en":"Bengali"},
    {"flag":"🇹🇷","cc":"tr","native":"Türkçe","en":"Turkish"},
    {"flag":"🇷🇺","cc":"ru","native":"Русский","en":"Russian"},
    {"flag":"🇺🇦","cc":"ua","native":"Українська","en":"Ukrainian"},
    {"flag":"🇨🇳","cc":"cn","native":"简体中文","en":"Chinese (Simplified)"},
    {"flag":"🇹🇼","cc":"tw","native":"繁體中文","en":"Chinese (Traditional)"},
    {"flag":"🇯🇵","cc":"jp","native":"日本語","en":"Japanese"},
    {"flag":"🇰🇷","cc":"kr","native":"한국어","en":"Korean"},
    {"flag":"🇮🇩","cc":"id","native":"Bahasa Indonesia","en":"Indonesian"},
    {"flag":"🇲🇾","cc":"my","native":"Bahasa Melayu","en":"Malay"},
    {"flag":"🇵🇭","cc":"ph","native":"Filipino","en":"Filipino (Tagalog)"},
    {"flag":"🇵🇱","cc":"pl","native":"Polski","en":"Polish"},
    {"flag":"🇷🇴","cc":"ro","native":"Română","en":"Romanian"},
    {"flag":"🇬🇷","cc":"gr","native":"Ελληνικά","en":"Greek"},
    {"flag":"🇮🇱","cc":"il","native":"עברית","en":"Hebrew"},
    {"flag":"🇮🇷","cc":"ir","native":"فارسی","en":"Persian (Farsi)"},
    {"flag":"🇦🇫","cc":"af","native":"پښتو","en":"Pashto"},
    {"flag":"🇹🇭","cc":"th","native":"ไทย","en":"Thai"},
    {"flag":"🇻🇳","cc":"vn","native":"Tiếng Việt","en":"Vietnamese"},
    {"flag":"🇲🇲","cc":"mm","native":"မြန်မာ","en":"Burmese"},
    {"flag":"🇰🇭","cc":"kh","native":"ខ្មែរ","en":"Khmer"},
    {"flag":"🇱🇦","cc":"la","native":"ລາວ","en":"Lao"},
    {"flag":"🇳🇵","cc":"np","native":"नेपाली","en":"Nepali"},
    {"flag":"🇱🇰","cc":"lk","native":"සිංහල","en":"Sinhala"},
    {"flag":"🇮🇳","cc":"in","native":"தமிழ்","en":"Tamil"},
    {"flag":"🇮🇳","cc":"in","native":"తెలుగు","en":"Telugu"},
    {"flag":"🇮🇳","cc":"in","native":"मराठी","en":"Marathi"},
    {"flag":"🇮🇳","cc":"in","native":"ગુજરાતી","en":"Gujarati"},
    {"flag":"🇮🇳","cc":"in","native":"ਪੰਜਾਬੀ","en":"Punjabi"},
    {"flag":"🇮🇳","cc":"in","native":"ಕನ್ನಡ","en":"Kannada"},
    {"flag":"🇮🇳","cc":"in","native":"മലയാളം","en":"Malayalam"},
    {"flag":"🇸🇪","cc":"se","native":"Svenska","en":"Swedish"},
    {"flag":"🇳🇴","cc":"no","native":"Norsk","en":"Norwegian"},
    {"flag":"🇩🇰","cc":"dk","native":"Dansk","en":"Danish"},
    {"flag":"🇫🇮","cc":"fi","native":"Suomi","en":"Finnish"},
    {"flag":"🇨🇿","cc":"cz","native":"Čeština","en":"Czech"},
    {"flag":"🇸🇰","cc":"sk","native":"Slovenčina","en":"Slovak"},
    {"flag":"🇭🇺","cc":"hu","native":"Magyar","en":"Hungarian"},
    {"flag":"🇧🇬","cc":"bg","native":"Български","en":"Bulgarian"},
    {"flag":"🇭🇷","cc":"hr","native":"Hrvatski","en":"Croatian"},
    {"flag":"🇷🇸","cc":"rs","native":"Српски","en":"Serbian"},
    {"flag":"🇸🇮","cc":"si","native":"Slovenščina","en":"Slovenian"},
    {"flag":"🇱🇹","cc":"lt","native":"Lietuvių","en":"Lithuanian"},
    {"flag":"🇱🇻","cc":"lv","native":"Latviešu","en":"Latvian"},
    {"flag":"🇪🇪","cc":"ee","native":"Eesti","en":"Estonian"},
    {"flag":"🇦🇱","cc":"al","native":"Shqip","en":"Albanian"},
    {"flag":"🇬🇪","cc":"ge","native":"ქართული","en":"Georgian"},
    {"flag":"🇦🇲","cc":"am","native":"Հայերեն","en":"Armenian"},
    {"flag":"🇦🇿","cc":"az","native":"Azərbaycan","en":"Azerbaijani"},
    {"flag":"🇰🇿","cc":"kz","native":"Қазақ","en":"Kazakh"},
    {"flag":"🇺🇿","cc":"uz","native":"Oʻzbek","en":"Uzbek"},
    {"flag":"🇲🇳","cc":"mn","native":"Монгол","en":"Mongolian"},
    {"flag":"🇰🇪","cc":"ke","native":"Kiswahili","en":"Swahili"},
    {"flag":"🇪🇹","cc":"et","native":"አማርኛ","en":"Amharic"},
    {"flag":"🇳🇬","cc":"ng","native":"Hausa","en":"Hausa"},
    {"flag":"🇳🇬","cc":"ng","native":"Yorùbá","en":"Yoruba"},
    {"flag":"🇳🇬","cc":"ng","native":"Igbo","en":"Igbo"},
    {"flag":"🇿🇦","cc":"za","native":"isiZulu","en":"Zulu"},
]

@app.get("/")
def home(): return render_template("index.html",languages=LANGS)

@app.get("/api/settings")
def settings():
    load_env()
    keys=get_gemini_keys()
    n=len(keys)
    masked=("••••••••"+keys[0][-4:] if n==1 and len(keys[0])>=4 else (f"{n} keys configured" if n>1 else ""))
    return jsonify(configured=n>0,masked=masked,key_count=n)

@app.post("/api/settings")
def settings_save():
    k=(request.get_json(silent=True) or {}).get("gemini_api_key","").strip()
    if not k:return jsonify(error="Please enter a Gemini API key."),400
    try: save_key(k); return jsonify(ok=True,masked="••••••••"+k[-4:])
    except Exception as e:return jsonify(error=str(e)),500

def extract_video_id(url):
    url=url.strip()
    patterns=[
        r"(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtube\.com/embed/|youtube\.com/live/|youtu\.be/)([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m=re.search(p,url)
        if m: return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}",url): return url
    return None

# Non-speech captions Gemini sometimes leaves in, e.g. [Music], (Applause), 【笑い】
_NONSPEECH_WORDS=r"(?:music|musique|música|musik|musica|applause|aplausos|laughter|laughing|laughs?|laugh|silence|silêncio|silencio|cheering|cheers|clapping|coughing|inaudible|background noise|noise|singing|instrumental|audience|crowd noise|indistinct chatter|indistinct|foreign language|no audio|blank_audio|static)"
_BRACKET_TAG_RE=re.compile(r"[\[\(【][^\]\)】]{0,40}\b"+_NONSPEECH_WORDS+r"\b[^\]\)】]{0,10}[\]\)】]",re.IGNORECASE)
# Fallback: strip ANY short bracketed/parenthesized tag (covers un-listed sound-effect labels
# like [Beat drops], (dramatic music), etc.) as long as it doesn't look like real dialogue.
_GENERIC_BRACKET_RE=re.compile(r"[\[【][^\]】]{1,40}[\]】]")

def _clean_caption_text(t):
    t=_BRACKET_TAG_RE.sub("",t)
    t=_GENERIC_BRACKET_RE.sub("",t)
    return re.sub(r"\s{2,}"," ",t).strip()

def get_youtube_metadata(video_id):
    """Get title/duration from YouTube metadata without asking Gemini.
    Uses oEmbed first for the exact public title, then yt-dlp for duration/title fallback.
    """
    title=""
    duration=0
    url=f"https://www.youtube.com/watch?v={video_id}"
    try:
        r=requests.get("https://www.youtube.com/oembed",params={"url":url,"format":"json"},timeout=12,
                       headers={"User-Agent":"Mozilla/5.0"})
        if r.ok:
            title=(r.json().get("title") or "").strip()
    except Exception:
        pass
    if yt_dlp is not None:
        opts={"quiet":True,"no_warnings":True,"skip_download":True,"noplaylist":True,
              "socket_timeout":60,"retries":3,"fragment_retries":3,
              "http_headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info=ydl.extract_info(url,download=False)
            if not title: title=(info.get("title") or "").strip()
            duration=int(info.get("duration") or 0)
        except Exception:
            pass
    return title,duration

def format_duration(seconds):
    seconds=int(seconds or 0)
    mm,ss=divmod(seconds,60)
    hh,mm=divmod(mm,60)
    return f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm}:{ss:02d}"

def gemini_youtube_video_info(video_id,keys,configured_model):
    """Fetch both the title and a verbatim transcript directly from Gemini, using only
    the YouTube link. Gemini fetches the video through Google's own servers (not this
    machine's IP), so this keeps working even when YouTube blocks/rate-limits scraping
    from cloud-host IPs (very common on Render, Railway, etc.). Rotates across every
    configured API key (random start, then fails over key-by-key) so one quota-limited
    key doesn't stop the request."""
    if not keys:
        raise RuntimeError("No Gemini API key configured (add one in Settings).")
    url=f"https://www.youtube.com/watch?v={video_id}"
    prompt=(
        "Watch this YouTube video. Respond with ONLY a raw JSON object (no markdown "
        "code fences, no commentary before or after) in exactly this shape:\n"
        '{"title": "the video\'s title", "transcript": "complete verbatim transcript"}\n\n'
        "The transcript must be a complete, word-for-word transcript of everything "
        "spoken in the video, in the original spoken language. Do not summarize, "
        "shorten, or translate it. Do not add timestamps, speaker labels, or bracketed "
        "sound tags like [Music]."
    )
    candidates=[configured_model]
    for fb in ("gemini-3.5-flash","gemini-flash-latest","gemini-3.1-flash-lite","gemini-3.6-flash"):
        if fb not in candidates:candidates.append(fb)
    start=random.randrange(len(keys))
    last_err=None
    for ki in range(len(keys)):
        key=keys[(start+ki)%len(keys)]
        for model in candidates:
            try:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",params={"key":key},
                                 json={"contents":[{"parts":[{"file_data":{"file_uri":url}},{"text":prompt}]}]},timeout=600)
                if r.status_code==200:
                    parts=r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[])
                    raw="".join(p.get("text","") for p in parts).strip()
                    if not raw:
                        last_err="Empty response from model.";continue
                    cleaned=re.sub(r"^```(?:json)?\s*|\s*```\s*$","",raw,flags=re.MULTILINE).strip()
                    try:
                        data=json.loads(cleaned)
                    except Exception:
                        m=re.search(r"\{.*\}",cleaned,re.DOTALL)
                        if not m:
                            last_err="Could not read the model's response.";continue
                        try:
                            data=json.loads(m.group(0))
                        except Exception:
                            last_err="Could not read the model's response.";continue
                    title=(data.get("title") or "").strip()
                    transcript=_clean_caption_text((data.get("transcript") or "").strip())
                    if transcript:
                        return title,transcript
                    last_err="Empty transcript returned.";continue
                try:e=r.json().get("error",{}).get("message",r.text)
                except Exception:e=r.text
                last_err=e
                if r.status_code==429:break  # this key is quota-limited — move to the next key
                continue
            except requests.RequestException as e:
                last_err=str(e);continue
    raise RuntimeError(f"Gemini request failed: {last_err}")

def fetch_youtube_thumbnail(video_id):
    """Return the best-quality thumbnail URL that actually exists for this video.
    YouTube always returns HTTP 200 for these paths (even missing ones serve a tiny
    120x90 placeholder), so we check the payload size to tell a real thumbnail apart
    from the placeholder."""
    for q_ in ("maxresdefault","sddefault","hqdefault","mqdefault","default"):
        url=f"https://img.youtube.com/vi/{video_id}/{q_}.jpg"
        try:
            r=requests.get(url,timeout=6)
            if r.status_code==200 and len(r.content)>2000:
                return url
        except Exception:
            continue
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

@app.post("/api/youtube_transcript")
def youtube_transcript():
    d=request.get_json(silent=True) or {}
    url=d.get("url","").strip()
    if not url:return jsonify(error="Please paste a YouTube video link."),400
    vid=extract_video_id(url)
    if not vid:return jsonify(error="Couldn't read a valid YouTube link."),400
    load_env(); keys=get_gemini_keys(); model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not keys:return jsonify(error="Open Settings and add your Gemini API key first."),400
    try:
        gemini_title,text=gemini_youtube_video_info(vid,keys,model)
        original_title,_=get_youtube_metadata(vid)
        title=original_title or gemini_title
    except Exception as e:
        return jsonify(error=f"Could not fetch transcript: {e}"),502
    if not text:return jsonify(error="This video has no transcript available."),400
    thumbnail=fetch_youtube_thumbnail(vid)
    return jsonify(transcript=text,title=title,thumbnail=thumbnail,video_id=vid)

@app.get("/api/thumbnail_download")
def thumbnail_download():
    from flask import Response
    vid=(request.args.get("video_id") or "").strip()
    if not vid or not re.fullmatch(r"[0-9A-Za-z_-]{11}",vid):
        return jsonify(error="Missing or invalid video_id."),400
    url=fetch_youtube_thumbnail(vid)
    try:
        r=requests.get(url,timeout=15)
        r.raise_for_status()
    except Exception as e:
        return jsonify(error=f"Could not download thumbnail: {e}"),502
    return Response(r.content,mimetype="image/jpeg",headers={"Content-Disposition":f'attachment; filename="{vid}_thumbnail.jpg"'})

def gemini_extract_image_text(image_bytes,keys,configured_model):
    """Ask Gemini to read out any text that's visually printed/overlaid on an image (e.g. a YouTube thumbnail).
    Not every configured text model accepts image input (e.g. some '-lite' variants are text-only), so this
    tries the user's configured model first, then falls back through other known vision-capable models.
    Rotates across every configured API key (random start, then fails over key-by-key)."""
    import base64
    if not keys:
        return None,"No Gemini API key configured (add one in Settings)."
    b64=base64.b64encode(image_bytes).decode("utf-8")
    prompt=("Look carefully at this image, which is a YouTube video thumbnail. Extract ONLY the text that is "
            "visually printed or overlaid on top of the thumbnail itself (bold captions, titles, numbers, callouts, etc.) "
            "— do not describe the image or guess at anything that isn't actual on-image text. Preserve line breaks as shown. "
            "If there is no visible text anywhere on the thumbnail, respond with exactly: NONE")
    candidates=[configured_model]
    for fb in ("gemini-3.5-flash","gemini-flash-latest","gemini-3.1-flash-lite","gemini-3.6-flash"):
        if fb not in candidates:candidates.append(fb)
    start=random.randrange(len(keys))
    last_err=None
    for ki in range(len(keys)):
        key=keys[(start+ki)%len(keys)]
        for model in candidates:
            try:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",params={"key":key},
                                 json={"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":"image/jpeg","data":b64}}]}]},timeout=600)
                if r.status_code==200:
                    parts=r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[])
                    result="".join(p.get("text","") for p in parts).strip()
                    if result:return result,None
                    last_err="Empty response from model.";continue
                try:e=r.json().get("error",{}).get("message",r.text)
                except:e=r.text
                last_err=e
                if r.status_code==429:break
                continue
            except requests.RequestException as e:
                last_err=str(e);continue
    return None,f"Thumbnail text API error: {last_err}"

@app.get("/api/thumbnail_text")
def thumbnail_text():
    vid=(request.args.get("video_id") or "").strip()
    if not vid or not re.fullmatch(r"[0-9A-Za-z_-]{11}",vid):
        return jsonify(error="Missing or invalid video_id."),400
    load_env(); keys=get_gemini_keys(); model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not keys:return jsonify(error="Open Settings and add your Gemini API key first."),400
    url=fetch_youtube_thumbnail(vid)
    try:
        r=requests.get(url,timeout=15); r.raise_for_status()
    except Exception as e:
        return jsonify(error=f"Could not fetch thumbnail: {e}"),502
    text,err=gemini_extract_image_text(r.content,keys,model)
    if err:return jsonify(error=err),502
    if text.strip().upper()=="NONE":
        return jsonify(text="",found=False)
    return jsonify(text=text,found=True)

@app.post("/api/audio_info")
def audio_info():
    if yt_dlp is None:return jsonify(error="Audio support is not installed. Reinstall dependencies and redeploy."),500
    d=request.get_json(silent=True) or {}
    vid=(d.get("video_id") or "").strip()
    if not vid or not re.fullmatch(r"[0-9A-Za-z_-]{11}",vid):
        return jsonify(error="Missing or invalid video_id."),400
    _,duration=get_youtube_metadata(vid)
    if not duration:
        return jsonify(error="YouTube did not return the video's duration. Try again after redeploying the latest yt-dlp."),502
    return jsonify(duration_seconds=duration,duration_text=format_duration(duration))

@app.get("/api/audio_download")
def audio_download():
    if yt_dlp is None:return jsonify(error="Audio support is not installed. Reinstall dependencies and redeploy."),500
    vid=(request.args.get("video_id") or "").strip()
    if not vid or not re.fullmatch(r"[0-9A-Za-z_-]{11}",vid):
        return jsonify(error="Missing or invalid video_id."),400
    tmp_dir=tempfile.mkdtemp(prefix="comp_audio_")
    url=f"https://www.youtube.com/watch?v={vid}"
    try:
        base={"quiet":True,"no_warnings":True,"noplaylist":True,"skip_download":False,
              "outtmpl":os.path.join(tmp_dir,"%(id)s.%(ext)s"),"retries":3,"fragment_retries":3,
              "socket_timeout":60,"concurrent_fragment_downloads":1,
              "http_headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"}}
        attempts=[
            {**base,"format":"bestaudio[ext=m4a]/bestaudio/best"},
            {**base,"format":"bestaudio/best","extractor_args":{"youtube":{"player_client":["android_vr","web_safari"]}}},
            {**base,"format":"worstaudio/worst","extractor_args":{"youtube":{"player_client":["android_vr"]}}},
        ]
        last_err=None; info=None; filename=None
        for opts in attempts:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info=ydl.extract_info(url,download=True)
                    filename=ydl.prepare_filename(info)
                if filename and os.path.exists(filename) and os.path.getsize(filename)>0:
                    break
            except Exception as e:
                last_err=str(e); info=None; filename=None
                for f in Path(tmp_dir).glob("*"):
                    try:f.unlink()
                    except OSError:pass
        if not filename or not os.path.exists(filename):
            shutil.rmtree(tmp_dir,ignore_errors=True)
            return jsonify(error=f"YouTube audio download failed. {last_err or 'No downloadable audio format was returned.'}"),502
        title=re.sub(r'[\\/:*?"<>|]+',"_",(info.get("title") or vid)).strip()[:80] or vid
        ext=os.path.splitext(filename)[1] or ".m4a"
        @after_this_request
        def _cleanup(response):
            shutil.rmtree(tmp_dir,ignore_errors=True)
            return response
        return send_file(filename,as_attachment=True,download_name=f"{title}{ext}")
    except Exception as e:
        shutil.rmtree(tmp_dir,ignore_errors=True)
        return jsonify(error=f"Could not download audio: {e}"),502


def gemini_generate(prompt,keys,model):
    """Call Gemini with retries, rotating across every configured API key (random
    start, then fails over key-by-key) so one quota-limited key doesn't block a
    request. Returns (result_text, error_message)."""
    if not keys:
        return None,"Open Settings and add your Gemini API key first."
    start=random.randrange(len(keys))
    last_err=None
    for ki in range(len(keys)):
        key=keys[(start+ki)%len(keys)]
        attempts=2
        for i in range(attempts):
            try:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",params={"key":key},json={"contents":[{"parts":[{"text":prompt}]}]},timeout=600)
                if r.status_code==200:
                    parts=r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[])
                    result="".join(p.get("text","") for p in parts).strip()
                    return (result,None) if result else (None,"Empty translation returned.")
                try:e=r.json().get("error",{}).get("message",r.text)
                except:e=r.text
                last_err=e
                if r.status_code==429:break
                if r.status_code in (500,502,503,504) and i<attempts-1:
                    time.sleep(1.2*(i+1)); continue
                break
            except requests.RequestException as e:
                last_err=str(e)
                if i<attempts-1: time.sleep(1.2*(i+1)); continue
                break
    return None,f"Translation API error: {last_err}"

@app.post("/api/translate")
def translate():
    d=request.get_json(silent=True) or {}; text=d.get("text","").strip(); target=d.get("target","").strip(); title=d.get("title","").strip()
    load_env(); keys=get_gemini_keys(); model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not text:return jsonify(error="Please paste your speech first."),400
    if not keys:return jsonify(error="Open Settings and add your Gemini API key first."),400
    prompt=f"""Translate the COMPLETE speech below into {target}.
Do not summarize, shorten, omit, or add ideas. Preserve meaning, emotional tone, intent and paragraph structure.
Use natural fluent {target}, not awkward word-for-word translation.
Correct punctuation professionally, including commas, periods, question marks, exclamation marks, quotation marks and paragraph breaks.
Keep names, numbers and factual details accurate.
Return ONLY the finished translated speech, and nothing else — no title, no heading, no extra commentary.

SOURCE:
{text}"""
    result,err=gemini_generate(prompt,keys,model)
    if err:return jsonify(error=err),502
    title_translation=""
    if title:
        title_prompt=f"""Translate ONLY this video title into {target}. Keep it short, natural, and title-like.
Return ONLY the translated title text, nothing else — no quotes, no explanation.

TITLE:
{title}"""
        tt,terr=gemini_generate(title_prompt,keys,model)
        if not terr and tt: title_translation=tt
    return jsonify(translation=result,title_translation=title_translation)

@app.post("/api/detect_channel_mention")
def detect_channel_mention():
    d=request.get_json(silent=True) or {}
    transcript=d.get("transcript","").strip()
    load_env(); keys=get_gemini_keys(); model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not transcript:return jsonify(error="Nothing to check."),400
    if not keys:return jsonify(error="Open Settings and add your Gemini API key first."),400
    prompt=f"""Read this YouTube speech/transcript. Does the speaker mention their OWN channel name or brand name anywhere in it (e.g. "subscribe to [X]", "welcome back to [X]", "this is [X] channel")?
If yes, reply with ONLY that exact channel/brand name, nothing else.
If no such mention exists, reply with exactly: NONE

TRANSCRIPT:
{transcript}"""
    result,err=gemini_generate(prompt,keys,model)
    if err or not result:return jsonify(found=False,name="")
    result=result.strip().strip('"').strip()
    if result.upper()=="NONE" or len(result)>80:
        return jsonify(found=False,name="")
    return jsonify(found=True,name=result)

@app.post("/api/beat_competitor")
def beat_competitor():
    d=request.get_json(silent=True) or {}
    title=d.get("title","").strip()
    transcript=d.get("transcript","").strip()
    target_chars=d.get("target_chars")
    competitor_channel=d.get("competitor_channel","").strip()
    user_channel=d.get("user_channel","").strip()
    load_env(); keys=get_gemini_keys(); model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    if not transcript:return jsonify(error="Fetch a competitor video first."),400
    if not keys:return jsonify(error="Open Settings and add your Gemini API key first."),400
    orig_words=len(transcript.split())
    orig_chars=len(transcript)
    try:
        tc=int(target_chars)
        aim_chars=tc if tc>0 else orig_chars
    except (TypeError,ValueError):
        aim_chars=orig_chars
    tol=1500
    min_chars,max_chars=aim_chars-tol,aim_chars+tol
    length_line=f"EXACTLY approximately {aim_chars:,} characters — it must land between {min_chars:,} and {max_chars:,} characters, no more and no less. This is a hard requirement, not a rough guide."
    if competitor_channel and user_channel:
        branding_line=f"""BRANDING: The competitor's speech mentions their own channel/brand name, "{competitor_channel}". Wherever the competitor speech mentions "{competitor_channel}" (e.g. asking viewers to subscribe, welcoming them, or referring to their own channel), your new speech must mention OUR channel/brand name, "{user_channel}", at the equivalent point instead — naturally, as if the speaker is promoting their own channel. Never mention "{competitor_channel}" anywhere in your output."""
    elif user_channel:
        branding_line=f"""BRANDING: Naturally include one mention of our channel/brand name, "{user_channel}", at an appropriate point (e.g. a welcome line or a call to subscribe)."""
    else:
        branding_line="BRANDING: No channel/brand name substitution is needed for this speech."
    prompt=f"""You are an expert YouTube scriptwriter and audience-retention specialist.

Below is a competitor's video title and their full speech/transcript. Read it and extract: the core idea, the main topics/points it covers, the examples and facts it uses, and its overall angle on the subject.

COMPETITOR TITLE:
{title if title else "(not provided)"}

COMPETITOR SPEECH (source material for the core idea and topics ONLY — do not resize, reword, paraphrase, or lightly edit this text):
{transcript}

TASK: This is NOT a resize or rewrite job. Using the same core idea and topics as raw material, WRITE A COMPLETELY NEW SPEECH FROM SCRATCH, for the SAME video title, that is genuinely more engaging and higher-retention than the competitor's — a stronger hook in the first few seconds, tighter pacing, better story structure, more compelling delivery, more vivid language, and smarter use of curiosity/tension to keep viewers watching all the way through. It should cover the same ground (and can go deeper or add sharper examples, or trim to fit) but every sentence should be freshly written by you, not adapted from the competitor's phrasing or structure. The end result must genuinely outperform the competitor's speech in quality and retention.

{branding_line}

REQUIRED LENGTH: {length_line}

Return ONLY the new speech text, nothing else — no title, no notes, no commentary."""
    result,err=gemini_generate(prompt,keys,model)
    if err:return jsonify(error=err),502
    attempts=0
    while attempts<6:
        L=len(result)
        if min_chars<=L<=max_chars:break
        if L<min_chars:
            deficit=max(aim_chars-L,min_chars-L+300)
            fix=f"""This speech is currently {L:,} characters, but it must land between {min_chars:,} and {max_chars:,} characters (aim for {aim_chars:,}). Add roughly {deficit:,} more characters — as genuinely valuable content that raises retention further: a sharper example, a deeper explanation, a stronger story beat, an extra angle on the same topic. Do NOT pad with filler wording or repetition. The result must still be more engaging and higher-retention than the competitor's original, and must land in the required range. Return ONLY the expanded speech, nothing else.\n\nTEXT:\n{result}"""
        else:
            excess=max(L-aim_chars,L-max_chars+300)
            fix=f"""This speech is currently {L:,} characters, but it must land between {min_chars:,} and {max_chars:,} characters (aim for {aim_chars:,}). Cut roughly {excess:,} characters by tightening pacing and removing anything that slows retention — keep every strong hook, story beat, and example; remove only redundancy and slack. The result must remain more engaging and higher-retention than the competitor's original, and must land in the required range. Return ONLY the condensed speech, nothing else.\n\nTEXT:\n{result}"""
        r2,e2=gemini_generate(fix,keys,model)
        if not e2 and r2:result=r2
        attempts+=1
    return jsonify(speech=result,length=len(result),words=len(result.split()),original_words=orig_words,original_length=orig_chars)

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    debug=os.environ.get("FLASK_DEBUG","0")=="1"
    app.run(host="0.0.0.0",port=port,debug=debug)
