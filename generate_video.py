import os, sys, json, time, requests
import traceback

# --- Configuration ---
# For Gemini, switch to the free Gemma 4 model which has a 3,000 req/day allowance
GEMINI_MODEL = "gemma-4-9b-it"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# --- API Keys ---
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')   # Optional, but strongly recommended fallback

def log(msg):
    print(f"[LOG] {msg}")

def fail(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)

# ============================================
# STEP 1: Get trending topic + script
# ============================================
log("Step 1: Generating script...")
prompt = (
    "Identify the #1 viral topic on YouTube Shorts right now. "
    "Write a 30-60 second vertical video script about it. "
    "Make it attention-grabbing from the first second. "
    "No captions or text overlays instructions."
)

script = None

# --- Attempt 1: Gemini (Gemma 4, free 3K requests/day) ---
if GEMINI_KEY:
    log("Trying Gemini (Gemma 4)...")
    try:
        resp = requests.post(
            GEMINI_URL,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.9, "maxOutputTokens": 500}
            },
            headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            script = data['candidates'][0]['content']['parts'][0]['text']
            log(f"Gemini script generated ({len(script)} chars)")
        else:
            log(f"Gemini returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log(f"Gemini error: {e}")

# --- Attempt 2: Groq (14,400 free requests/day) ---
if not script and GROQ_KEY:
    log("Trying Groq (Llama 3.1 8B)...")
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
                "max_tokens": 500
            },
            headers={
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        if resp.status_code == 200:
            script = resp.json()['choices'][0]['message']['content']
            log(f"Groq script generated ({len(script)} chars)")
        else:
            log(f"Groq returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log(f"Groq error: {e}")

# --- Attempt 3: Pollinations.ai (no API key needed) ---
if not script:
    log("Trying Pollinations.ai (no key required)...")
    try:
        resp = requests.get(
            "https://text.pollinations.ai/",
            params={"prompt": prompt, "model": "openai"},
            timeout=30
        )
        if resp.status_code == 200 and resp.text.strip():
            script = resp.text.strip()
            log(f"Pollinations script generated ({len(script)} chars)")
        else:
            log(f"Pollinations returned {resp.status_code}")
    except Exception as e:
        log(f"Pollinations error: {e}")

if not script:
    fail("All script generators failed")

log(f"Final script: {script[:200]}...")

# ============================================
# STEP 2: Generate AI video with NexaAPI
# ============================================
log("Step 2: Generating AI video with NexaAPI...")
NEXA_KEY = os.environ.get('NEXA_API_KEY')
if not NEXA_KEY:
    fail("NEXA_API_KEY not set")

video_url = None

try:
    job_resp = requests.post(
        "https://api.nexa-api.com/v1/video/generate",
        headers={
            "Authorization": f"Bearer {NEXA_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "prompt": script[:500],
            "duration": 8,
            "aspect_ratio": "9:16",
            "quality": "high"
        },
        timeout=30
    )
    
    if job_resp.status_code == 200:
        job_data = job_resp.json()
        job_id = job_data.get("job_id")
        
        if job_id:
            log(f"NexaAPI job submitted: {job_id}")
            
            for attempt in range(60):
                status_resp = requests.get(
                    f"https://api.nexa-api.com/v1/video/status/{job_id}",
                    headers={"Authorization": f"Bearer {NEXA_KEY}"},
                    timeout=20
                )
                
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    if status.get("status") == "completed":
                        video_url = status.get("video_url")
                        if video_url:
                            log("NexaAPI video ready!")
                            break
                    elif status.get("status") == "failed":
                        fail("NexaAPI generation failed")
                
                time.sleep(5)
        else:
            fail("No job_id in NexaAPI response")
    else:
        fail(f"NexaAPI returned {job_resp.status_code}: {job_resp.text[:200]}")
        
except Exception as e:
    fail(f"NexaAPI error: {e}")

if not video_url:
    fail("No video URL obtained after generation")

# ============================================
# STEP 3: Download final video
# ============================================
log(f"Step 3: Downloading video...")
try:
    video_data = requests.get(video_url, timeout=120)
    video_data.raise_for_status()
    with open("output.mp4", "wb") as f:
        f.write(video_data.content)
    log(f"Video downloaded: {len(video_data.content)} bytes")
except Exception as e:
    fail(f"Download failed: {e}")

log("SUCCESS: Video ready for upload!")
print("::notice title=Video Generated::Your AI Short is ready! Download from Releases.")
