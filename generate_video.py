import os, sys, json, time, requests

GEMINI_KEY = os.environ['GEMINI_API_KEY']

def log(msg):
    print(f"[LOG] {msg}")
def die(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)

# ============================================
# STEP 1: Script generation
# ============================================
log("Step 1: Generating script...")
prompt = (
    "Identify the #1 viral topic on YouTube Shorts right now. "
    "Write a 30-60 second vertical video script about it. "
    "Make it attention-grabbing from the first second. "
    "No captions or text overlays instructions."
)

script = None

# --- Attempt 1: Gemini 2.5 Flash Preview (500 req/day free) ---
log("Trying Gemini 2.5 Flash Preview...")
try:
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview:generateContent",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 500}
        },
        headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
        timeout=30
    )
    if resp.status_code == 200:
        script = resp.json()['candidates'][0]['content']['parts'][0]['text']
        log(f"Gemini script ({len(script)} chars): {script[:120]}...")
    else:
        log(f"Gemini returned {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log(f"Gemini error: {e}")

# --- Attempt 2: Pollinations.ai (OpenAI-compatible, no key) ---
if not script:
    log("Trying Pollinations.ai (free, no key)...")
    try:
        resp = requests.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai-fast",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
                "max_tokens": 500
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            script = data['choices'][0]['message']['content']
            log(f"Pollinations script ({len(script)} chars): {script[:120]}...")
        else:
            log(f"Pollinations returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log(f"Pollinations error: {e}")

if not script:
    die("All script generators failed")

# ============================================
# STEP 2: AI Video generation via Magic Hour
# ============================================
log("Step 2: Generating AI video with Magic Hour...")

MAGIC_HOUR_KEY = os.environ.get('MAGIC_HOUR_API_KEY', '')
video_url = None

if MAGIC_HOUR_KEY:
    try:
        # Submit generation job
        job_resp = requests.post(
            "https://api.magichour.ai/v1/video/generate",
            headers={
                "Authorization": f"Bearer {MAGIC_HOUR_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "prompt": script[:500],
                "duration": 8,
                "aspect_ratio": "9:16"
            },
            timeout=30
        )
        
        if job_resp.status_code == 200:
            job_data = job_resp.json()
            job_id = job_data.get("job_id") or job_data.get("id")
            
            if job_id:
                log(f"Magic Hour job: {job_id}")
                for _ in range(60):
                    status_resp = requests.get(
                        f"https://api.magichour.ai/v1/video/status/{job_id}",
                        headers={"Authorization": f"Bearer {MAGIC_HOUR_KEY}"},
                        timeout=20
                    )
                    if status_resp.status_code == 200:
                        s = status_resp.json()
                        if s.get("status") == "completed":
                            video_url = s.get("video_url") or s.get("url")
                            break
                        elif s.get("status") == "failed":
                            log("Magic Hour generation failed")
                            break
                    time.sleep(5)
            else:
                log(f"Magic Hour response: {job_data}")
        else:
            log(f"Magic Hour returned {job_resp.status_code}: {job_resp.text[:200]}")
    except Exception as e:
        log(f"Magic Hour error: {e}")

# --- Fallback: Pollinations.ai image + FFmpeg ---
if not video_url:
    log("Step 2b: Falling back to Pollinations.ai image + TTS...")
    try:
        # Generate AI image
        img_resp = requests.get(
            "https://image.pollinations.ai/prompt/" + requests.utils.quote(script[:200] + ", vertical 9:16, viral style"),
            params={"width": 1080, "height": 1920},
            timeout=60
        )
        if img_resp.status_code == 200:
            with open("frame.jpg", "wb") as f:
                f.write(img_resp.content)
            
            # Generate TTS
            import subprocess
            subprocess.run([
                "edge-tts", "--text", script,
                "--voice", "en-US-JennyNeural",
                "--write-media", "audio.mp3"
            ], check=True)
            
            # Combine with FFmpeg
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", "frame.jpg",
                "-i", "audio.mp3",
                "-vf", "scale=1080:1920",
                "-t", "30",
                "-shortest",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                "output.mp4"
            ], check=True)
            video_url = "local"
            log("Fallback video assembled locally")
    except Exception as e:
        die(f"All video methods failed: {e}")

# ============================================
# STEP 3: Download (if remote URL)
# ============================================
if video_url and video_url != "local":
    log(f"Step 3: Downloading video...")
    try:
        r = requests.get(video_url, timeout=120)
        r.raise_for_status()
        with open("output.mp4", "wb") as f:
            f.write(r.content)
        log(f"Downloaded: {len(r.content)} bytes")
    except Exception as e:
        die(f"Download failed: {e}")

log("SUCCESS: output.mp4 ready!")
