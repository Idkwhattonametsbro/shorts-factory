import os, sys, json, time, requests, subprocess

MAGIC_HOUR_KEY = os.environ.get('MAGIC_HOUR_API_KEY', '')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')

def log(msg):
    print(f"[LOG] {msg}")
def die(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)

# ============================================
# STEP 1: Generate script
# ============================================
log("Step 1: Generating script...")
prompt = (
    "Identify the #1 viral topic on YouTube Shorts right now. "
    "Write a 30-60 second vertical video script about it. "
    "Make it attention-grabbing from the first second. No captions instructions."
)

script = None

# --- Primary: Gemini 1.5 Flash (stable, 1,500 req/day) ---
if GEMINI_KEY:
    log("Trying Gemini 1.5 Flash...")
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.9, "maxOutputTokens": 500}
            },
            headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
            timeout=30
        )
        if resp.status_code == 200:
            script = resp.json()['candidates'][0]['content']['parts'][0]['text']
            log(f"Gemini script: {script[:120]}...")
        else:
            log(f"Gemini returned {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        log(f"Gemini error: {e}")

# --- Fallback: Pollinations text (no key) ---
if not script:
    log("Falling back to Pollinations text...")
    try:
        resp = requests.get(
            "https://gen.pollinations.ai/text/" + requests.utils.quote(prompt),
            timeout=60
        )
        if resp.status_code == 200:
            script = resp.text.strip()
            log(f"Pollinations script: {script[:120]}...")
    except Exception as e:
        die(f"All text generators failed: {e}")

if not script:
    die("No script generated")

# ============================================
# STEP 2: Generate video with Magic Hour
# ============================================
log("Step 2: Generating video with Magic Hour...")

video_downloaded = False

if MAGIC_HOUR_KEY:
    try:
        from magic_hour import Client
        client = Client(token=MAGIC_HOUR_KEY)
        
        log("Calling Magic Hour text-to-video API...")
        result = client.v1.text_to_video.generate(
            end_seconds=8.0,
            orientation="portrait",
            style={"prompt": script[:500]},
            name="YouTube Short",
            resolution="720p",
            wait_for_completion=True,
            download_outputs=True,
            download_directory="."
        )
        log(f"Magic Hour result: {result}")
        
        # Check for downloaded video files
        import glob
        mp4_files = glob.glob("*.mp4")
        if mp4_files:
            # Rename the first found mp4 to output.mp4
            import shutil
            shutil.move(mp4_files[0], "output.mp4")
            video_downloaded = True
            log(f"Video downloaded from Magic Hour: {mp4_files[0]}")
    except Exception as e:
        log(f"Magic Hour failed: {e}")

# --- Fallback: Pollinations.ai video ---
if not video_downloaded:
    log("Falling back to Pollinations video...")
    try:
        video_resp = requests.get(
            "https://gen.pollinations.ai/video/" + requests.utils.quote(script[:300] + ", vertical 9:16, viral style"),
            timeout=180
        )
        if video_resp.status_code == 200 and len(video_resp.content) > 10000:
            with open("output.mp4", "wb") as f:
                f.write(video_resp.content)
            video_downloaded = True
            log(f"Pollinations video saved: {len(video_resp.content)} bytes")
    except Exception as e:
        log(f"Pollinations video error: {e}")

if not video_downloaded:
    die("All video generators failed")

log("SUCCESS: output.mp4 ready!")
