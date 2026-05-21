import os
import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import cloudinary
import cloudinary.uploader
import requests

from database import (
    db_get_profiles, db_add_profile, db_delete_profile,
    db_save_token, db_get_token, db_save_flow_state, db_get_flow_state,
    db_save_schedule, db_get_schedule, db_mark_uploaded, db_get_uploaded_files
)


load_dotenv()

app = FastAPI(title="YouTube Shorts Auto Scheduler Backend")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL")
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, os.getenv("VIDEOS_DIR", "videos"))
DATA_DIR = os.path.join(BASE_DIR, os.getenv("DATA_DIR", "data"))

# Path Management
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
if not os.path.exists(CLIENT_SECRET_FILE):
    CLIENT_SECRET_FILE = "/etc/secrets/client_secret.json"

PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def get_profile_dir(profile: str):
    pdir = os.path.join(PROFILES_DIR, profile)
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(os.path.join(pdir, "videos"), exist_ok=True)
    return pdir

def get_paths(profile: str):
    pdir = get_profile_dir(profile)
    return {
        "token": os.path.join(pdir, "token.json"),
        "schedule": os.path.join(pdir, "schedule.csv"),
        "uploaded": os.path.join(pdir, "uploaded.txt"),
        "videos": os.path.join(pdir, "videos")
    }

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEZONE_OFFSET = os.getenv("TIMEZONE_OFFSET", "+05:30")
DEFAULT_START_DATE = os.getenv("DEFAULT_START_DATE", "2026-05-21")

DEFAULT_DESCRIPTION = os.getenv(
    "DEFAULT_DESCRIPTION",
    "Adobe Premiere Pro editing tips, effects, transitions, and video editing tricks in Shorts format.\nFollow for more editing tutorials.\n\n#premierepro #videoediting #editingtips #shorts #ytshorts #adobepremierepro #editingtutorial #viralshorts #ytshorts #youtubeshorts #viralshorts #trending #viralvideo #shortvideo #reels #explore #entertainment #creativevideo #newshorts #indianyoutuber #dailyshorts #subscribe",
)

DEFAULT_TAGS = os.getenv(
    "DEFAULT_TAGS",
    "premierepro,videoediting,editingtips,shorts,ytshorts,adobepremierepro,editingtutorial,viralshorts,youtubeshorts,trending,viralvideo,shortvideo,reels,explore,entertainment,creativevideo,newshorts,indianyoutuber,dailyshorts,subscribe",
)

UPLOAD_TIMES = [
    t.strip() for t in os.getenv("UPLOAD_TIMES", "09:00,09:05,09:10").split(",") if t.strip()
]

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def ensure_files(profile: str):
    paths = get_paths(profile)
    if not os.path.exists(paths["schedule"]):
        with open(paths["schedule"], "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["filename", "title", "description", "tags", "publish_time", "status"],
            )
            writer.writeheader()

    if not os.path.exists(paths["uploaded"]):
        open(paths["uploaded"], "w", encoding="utf-8").close()


def get_uploaded_files(profile: str):
    return set(db_get_uploaded_files(profile))


def mark_uploaded(profile: str, filename: str):
    db_mark_uploaded(profile, filename)


def read_schedule(profile: str):
    return db_get_schedule(profile)


def write_schedule(profile: str, rows: List):
    db_save_schedule(profile, rows)


def clean_title(filename):
    title = os.path.splitext(filename)[0]
    title = title.replace("_", " ").replace("-", " ")
    title = " ".join(title.split())
    return title[:95]


def get_redirect_uri():
    return f"{APP_BASE_URL}/auth/callback"


def upload_to_cloudinary(profile: str, file_path: str):
    """Uploads video to Cloudinary for persistence."""
    try:
        response = cloudinary.uploader.upload_large(
            file_path,
            resource_type="video",
            folder=f"youtube_studio/{profile}",
            public_id=os.path.basename(file_path)
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None

def download_from_cloudinary(url: str, dest_path: str):
    """Downloads video from Cloudinary to local disk."""
    try:
        r = requests.get(url, stream=True)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Cloudinary Download Error: {e}")
        return False


@app.get("/")
def home():
    return {
        "status": "running",
        "message": "YouTube Shorts Auto Scheduler Backend is live",
        "auth_url": "/auth/start",
        "generate_schedule": "/schedule/generate",
        "upload_next": "/upload/next",
        "queue": "/schedule",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/profiles")
def list_profiles():
    return {"profiles": db_get_profiles()}

@app.post("/profiles")
def create_profile(name: str):
    db_add_profile(name)
    get_profile_dir(name) # Ensure disk folder exists for temp videos
    return {"status": "success", "message": f"Profile '{name}' created."}

@app.delete("/profiles/{name}")
def delete_profile_route(name: str):
    db_delete_profile(name)
    pdir = os.path.join(PROFILES_DIR, name)
    if os.path.exists(pdir):
        shutil.rmtree(pdir)
    return {"status": "success", "message": f"Profile '{name}' deleted."}

@app.get("/auth/status")
def auth_status(profile: str = "default"):
    token_json = db_get_token(profile)
    if not token_json:
        return {"authenticated": False, "message": "No token found in database"}
    
    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if creds and creds.valid:
            return {"authenticated": True, "profile": profile}
        elif creds and creds.refresh_token:
            return {"authenticated": True, "profile": profile}
        else:
            return {"authenticated": False, "message": "Invalid token"}
    except Exception as e:
        return {"authenticated": False, "message": str(e)}


@app.get("/auth/start")
def auth_start(profile: str = "default"):
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise HTTPException(status_code=400, detail="client_secret.json not found")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # Save state/verifier tied to profile in DB
    db_save_flow_state(profile, {"code_verifier": flow.code_verifier, "profile": profile})

    return RedirectResponse(auth_url)


@app.get("/auth/callback")
def auth_callback(code: str):
    # Find active flow_state across all profiles in DB
    profile = "default"
    code_verifier = None
    
    profiles = db_get_profiles()
    for p in profiles:
        state = db_get_flow_state(p)
        if state:
            profile = state.get("profile", "default")
            code_verifier = state.get("code_verifier")
            break

    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=get_redirect_uri(),
        )
        flow.code_verifier = code_verifier

        flow.fetch_token(code=code)
        creds = flow.credentials

        # Save to DB instead of file
        db_save_token(profile, creds.to_json())

        # Clean up
        state_path = os.path.join(PROFILES_DIR, profile, "flow_state.json")
        if os.path.exists(state_path):
            os.remove(state_path)

        return {
            "status": "success",
            "message": f"Channel connected for profile '{profile}'."
        }
    except Exception as e:
        print(f"AUTH ERROR: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/videos/upload")
async def upload_video_file(file: UploadFile = File(...), profile: str = "default"):
    allowed = [".mp4", ".mov", ".mkv", ".webm"]
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only video files are allowed.")

    paths = get_paths(profile)
    save_path = os.path.join(paths["videos"], file.filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Upload to Cloudinary for persistence
    cloudinary_url = upload_to_cloudinary(profile, save_path)

    return {
        "status": "success",
        "filename": file.filename,
        "cloudinary_url": cloudinary_url,
        "profile": profile
    }


@app.get("/videos")
def list_videos(profile: str = "default"):
    paths = get_paths(profile)
    vdir = paths["videos"]
    files = [
        f for f in sorted(os.listdir(vdir))
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
    ]

    return {
        "total": len(files),
        "videos": files,
        "profile": profile
    }


@app.post("/schedule/generate")
def generate_schedule(
    profile: str = "default",
    start_date: Optional[str] = Query(None, example="2026-05-21"),
    daily_uploads: Optional[int] = Query(None, example=2),
):
    paths = get_paths(profile)
    vdir = paths["videos"]
    video_files = [
        f for f in sorted(os.listdir(vdir))
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
    ]

    if not video_files:
        raise HTTPException(status_code=400, detail=f"No videos found for profile {profile}")

    final_start_date = start_date or DEFAULT_START_DATE

    if daily_uploads:
        selected_times = UPLOAD_TIMES[:daily_uploads]
    else:
        selected_times = UPLOAD_TIMES

    if not selected_times:
        raise HTTPException(status_code=400, detail="No upload times configured.")

    try:
        start = datetime.strptime(final_start_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date. Use YYYY-MM-DD.")

    rows = []
    video_index = 0
    day_offset = 0

    while video_index < len(video_files):
        for upload_time in selected_times:
            if video_index >= len(video_files):
                break

            current_date = start + timedelta(days=day_offset)
            publish_time = f"{current_date.strftime('%Y-%m-%d')}T{upload_time}:00{TIMEZONE_OFFSET}"

            filename = video_files[video_index]

            rows.append({
                "filename": filename,
                "title": clean_title(filename),
                "description": DEFAULT_DESCRIPTION,
                "tags": DEFAULT_TAGS,
                "publish_time": publish_time,
                "status": "pending",
            })

            video_index += 1

        day_offset += 1

    write_schedule(profile, rows)

    return {
        "status": "success",
        "total_scheduled": len(rows),
        "profile": profile,
        "start_date": final_start_date
    }


@app.get("/schedule")
def get_schedule(profile: str = "default"):
    rows = read_schedule(profile)
    uploaded = get_uploaded_files(profile)

    return {
        "status": "success",
        "profile": profile,
        "total": len(rows),
        "uploaded_count": len(uploaded),
        "pending_count": len([r for r in rows if r.get("status") != "uploaded"]),
        "items": rows,
    }
@app.delete("/schedule")
def clear_schedule(profile: str = "default"):
    """Clears the entire schedule for a profile."""
    write_schedule(profile, [])
    return {"status": "success", "message": f"Schedule cleared for profile '{profile}'"}


@app.delete("/schedule/{filename}")
def delete_schedule_item(filename: str, profile: str = "default"):
    """Removes a specific video from the schedule."""
    rows = read_schedule(profile)
    new_rows = [r for r in rows if r["filename"].strip() != filename.strip()]
    
    if len(new_rows) == len(rows):
        raise HTTPException(status_code=404, detail="Video not found in schedule.")
        
    write_schedule(profile, new_rows)
    return {"status": "success", "message": f"Removed {filename} from profile '{profile}'"}


def upload_to_youtube(profile: str, row: dict):
    youtube = get_youtube_service(profile)
    paths = get_paths(profile)

    filename = row["filename"].strip()
    video_path = os.path.join(paths["videos"], filename)

    # 1. Check if file exists locally, if not download from Cloudinary
    if not os.path.exists(video_path):
        cloudinary_url = row.get("cloudinary_url")
        if cloudinary_url:
            print(f"Downloading {filename} from Cloudinary...")
            download_from_cloudinary(cloudinary_url, video_path)
        else:
            raise Exception(f"Video file not found locally or on Cloudinary: {filename}")

    tags = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]

    body = {
        "snippet": {
            "title": row["title"].strip()[:100],
            "description": row["description"].strip(),
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": row["publish_time"].strip(),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    while response is None:
        status, response = request.next_chunk()

    return response


@app.post("/upload/next")
def upload_next(profile: str = "default"):
    rows = read_schedule(profile)
    uploaded = get_uploaded_files(profile)

    for row in rows:
        filename = row["filename"].strip()

        if filename in uploaded or row.get("status") == "uploaded":
            continue

        try:
            response = upload_to_youtube(profile, row)

            row["status"] = "uploaded"
            write_schedule(profile, rows)
            mark_uploaded(profile, filename)

            return {
                "status": "success",
                "message": "Next video uploaded successfully.",
                "filename": filename,
                "profile": profile,
                "youtube_video_id": response.get("id"),
                "publish_time": row["publish_time"],
            }

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "filename": filename,
                    "error": str(e),
                },
            )

    return {
        "status": "done",
        "message": "No pending videos left.",
    }
@app.post("/upload/instant")
async def upload_instant(file: UploadFile = File(...)):
    """
    Uploads a video file and publishes it to YouTube immediately (Public).
    """
    allowed = [".mp4", ".mov", ".mkv", ".webm"]
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only video files are allowed.")

    # Save temporarily
    save_path = os.path.join(VIDEOS_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        row = {
            "filename": file.filename,
            "title": clean_title(file.filename),
            "description": DEFAULT_DESCRIPTION,
            "tags": DEFAULT_TAGS,
            "publish_time": "" # Not used for instant
        }
        
        # Modify upload_to_youtube for instant if needed, 
        # but the current function supports 'private' + 'publishAt'.
        # For instant public, we just omit 'publishAt' and set privacy to 'public'.
        
        youtube = get_youtube_service("default")
        tags = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]

        body = {
            "snippet": {
                "title": row["title"].strip()[:100],
                "description": row["description"].strip(),
                "tags": tags,
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "public",  # Immediate public
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            save_path,
            chunksize=-1,
            resumable=True,
            mimetype="video/mp4",
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()

        mark_uploaded("default", file.filename)
        
        return {
            "status": "success",
            "message": "Video published instantly!",
            "video_id": response.get("id")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/today")
def upload_today(profile: str = "default"):
    """Uploads all videos scheduled for today for a specific profile."""
    rows = read_schedule(profile)
    uploaded = get_uploaded_files(profile)
    today = datetime.now().strftime("%Y-%m-%d")

    results = []

    for row in rows:
        filename = row["filename"].strip()
        publish_time = row["publish_time"].strip()

        if filename in uploaded or row.get("status") == "uploaded":
            continue

        if not publish_time.startswith(today):
            continue

        try:
            response = upload_to_youtube(profile, row)

            row["status"] = "uploaded"
            mark_uploaded(profile, filename)

            results.append({
                "filename": filename,
                "youtube_video_id": response.get("id"),
                "publish_time": publish_time,
                "status": "uploaded",
            })

        except Exception as e:
            results.append({
                "filename": filename,
                "publish_time": publish_time,
                "status": "error",
                "error": str(e),
            })

    write_schedule(profile, rows)

    return {
        "status": "success",
        "profile": profile,
        "date": today,
        "uploaded_today": len([r for r in results if r["status"] == "uploaded"]),
        "results": results,
    }


def scheduled_daily_upload():
    """Auto worker: iterate all profiles and upload today's videos."""
    try:
        profiles = db_get_profiles()
        for profile in profiles:
            print(f"Running daily auto upload for profile: {profile}...")
            upload_today(profile)
    except Exception as e:
        print(f"Daily upload error: {e}")


def auto_generate_schedule():
    """Auto-schedule new videos for ALL profiles."""
    try:
        profiles = db_get_profiles()
        for profile in profiles:
            print(f"Checking for new videos to auto-schedule for: {profile}...")
            paths = get_paths(profile)
            vdir = paths["videos"]
            
            video_files = [
                f for f in sorted(os.listdir(vdir))
                if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
            ]
            
            current_schedule = read_schedule(profile)
            scheduled_filenames = set(r["filename"] for r in current_schedule)
            
            new_videos = [f for f in video_files if f not in scheduled_filenames]
            
            if not new_videos:
                continue

            # Next availability
            if current_schedule:
                last_publish = current_schedule[-1]["publish_time"]
                last_date_str = last_publish.split("T")[0]
                start_date = datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=1)
            else:
                start_date = datetime.now() + timedelta(days=1)

            rows = current_schedule
            video_index = 0
            day_offset = 0
            while video_index < len(new_videos):
                for upload_time in UPLOAD_TIMES:
                    if video_index >= len(new_videos):
                        break
                    
                    current_date = start_date + timedelta(days=day_offset)
                    publish_time = f"{current_date.strftime('%Y-%m-%d')}T{upload_time}:00{TIMEZONE_OFFSET}"
                    filename = new_videos[video_index]
                    
                    rows.append({
                        "filename": filename,
                        "title": clean_title(filename),
                        "description": DEFAULT_DESCRIPTION,
                        "tags": DEFAULT_TAGS,
                        "publish_time": publish_time,
                        "status": "pending",
                    })
                    video_index += 1
                day_offset += 1
                
            write_schedule(profile, rows)
            print(f"Auto-scheduled {len(new_videos)} new videos for {profile}.")
    except Exception as e:
        print(f"Auto-schedule error: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_daily_upload, "cron", hour=6, minute=0)
scheduler.add_job(auto_generate_schedule, "cron", hour=1, minute=0) # Check for new videos at 1 AM
scheduler.start()
