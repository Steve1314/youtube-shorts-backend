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

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


load_dotenv()

app = FastAPI(title="YouTube Shorts Auto Scheduler Backend")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, os.getenv("VIDEOS_DIR", "videos"))
DATA_DIR = os.path.join(BASE_DIR, os.getenv("DATA_DIR", "data"))

CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.csv")
UPLOADED_FILE = os.path.join(DATA_DIR, "uploaded.txt")

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEZONE_OFFSET = os.getenv("TIMEZONE_OFFSET", "+05:30")
DEFAULT_START_DATE = os.getenv("DEFAULT_START_DATE", "2026-05-21")

DEFAULT_DESCRIPTION = os.getenv(
    "DEFAULT_DESCRIPTION",
    "Quick and useful Adobe Premiere Pro editing tip. Subscribe for more daily Shorts. #shorts #youtubeshorts",
)

DEFAULT_TAGS = os.getenv(
    "DEFAULT_TAGS",
    "shorts,youtubeshorts,viral,trending",
)

UPLOAD_TIMES = [
    t.strip() for t in os.getenv("UPLOAD_TIMES", "11:00,19:00").split(",") if t.strip()
]

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def ensure_files():
    if not os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["filename", "title", "description", "tags", "publish_time", "status"],
            )
            writer.writeheader()

    if not os.path.exists(UPLOADED_FILE):
        open(UPLOADED_FILE, "w", encoding="utf-8").close()


ensure_files()


def get_uploaded_files():
    if not os.path.exists(UPLOADED_FILE):
        return set()

    with open(UPLOADED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def mark_uploaded(filename):
    with open(UPLOADED_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")


def read_schedule():
    ensure_files()
    with open(SCHEDULE_FILE, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_schedule(rows):
    with open(SCHEDULE_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["filename", "title", "description", "tags", "publish_time", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)


def clean_title(filename):
    title = os.path.splitext(filename)[0]
    title = title.replace("_", " ").replace("-", " ")
    title = " ".join(title.split())
    return title[:95]


def get_redirect_uri():
    return f"{APP_BASE_URL}/auth/callback"


def get_youtube_service():
    if not os.path.exists(TOKEN_FILE):
        raise HTTPException(
            status_code=401,
            detail="YouTube auth missing. Open /auth/start first.",
        )

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as token:
                token.write(creds.to_json())
        else:
            raise HTTPException(
                status_code=401,
                detail="Token expired. Open /auth/start again.",
            )

    return build("youtube", "v3", credentials=creds)


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


@app.get("/auth/status")
def auth_status():
    if not os.path.exists(TOKEN_FILE):
        return {"authenticated": False, "message": "No token file found"}
    
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.valid:
            return {"authenticated": True, "message": "Authenticated"}
        elif creds and creds.refresh_token:
            return {"authenticated": True, "message": "Token expired but refreshable"}
        else:
            return {"authenticated": False, "message": "Invalid token"}
    except Exception as e:
        return {"authenticated": False, "message": str(e)}


@app.get("/auth/start")
def auth_start():
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise HTTPException(
            status_code=400,
            detail="client_secret.json not found in backend root folder.",
        )

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return RedirectResponse(auth_url)


@app.get("/auth/callback")
def auth_callback(code: str):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )

    flow.fetch_token(code=code)
    creds = flow.credentials

    with open(TOKEN_FILE, "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    return {
        "status": "success",
        "message": "YouTube account connected successfully. Now you can generate schedule and upload videos.",
    }


@app.post("/videos/upload")
async def upload_video_file(file: UploadFile = File(...)):
    allowed = [".mp4", ".mov", ".mkv", ".webm"]
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only video files are allowed.")

    save_path = os.path.join(VIDEOS_DIR, file.filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "status": "success",
        "filename": file.filename,
        "path": save_path,
    }


@app.get("/videos")
def list_videos():
    files = [
        f for f in sorted(os.listdir(VIDEOS_DIR))
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
    ]

    return {
        "total": len(files),
        "videos": files,
    }


@app.post("/schedule/generate")
def generate_schedule(
    start_date: Optional[str] = Query(None, example="2026-05-21"),
    daily_uploads: Optional[int] = Query(None, example=2),
):
    video_files = [
        f for f in sorted(os.listdir(VIDEOS_DIR))
        if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
    ]

    if not video_files:
        raise HTTPException(status_code=400, detail="No videos found in videos folder.")

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

    write_schedule(rows)

    return {
        "status": "success",
        "total_scheduled": len(rows),
        "start_date": final_start_date,
        "upload_times": selected_times,
        "schedule_file": SCHEDULE_FILE,
    }


@app.get("/schedule")
def get_schedule():
    rows = read_schedule()
    uploaded = get_uploaded_files()

    return {
        "total": len(rows),
        "uploaded_count": len(uploaded),
        "pending_count": len([r for r in rows if r.get("status") != "uploaded"]),
        "items": rows,
    }


def upload_to_youtube(row):
    youtube = get_youtube_service()

    filename = row["filename"].strip()
    video_path = os.path.join(VIDEOS_DIR, filename)

    if not os.path.exists(video_path):
        raise Exception(f"Video file not found: {filename}")

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
def upload_next():
    rows = read_schedule()
    uploaded = get_uploaded_files()

    for row in rows:
        filename = row["filename"].strip()

        if filename in uploaded or row.get("status") == "uploaded":
            continue

        try:
            response = upload_to_youtube(row)

            row["status"] = "uploaded"
            write_schedule(rows)
            mark_uploaded(filename)

            return {
                "status": "success",
                "message": "Next video uploaded and scheduled successfully.",
                "filename": filename,
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
        
        youtube = get_youtube_service()
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

        mark_uploaded(file.filename)
        
        return {
            "status": "success",
            "message": "Video published instantly!",
            "video_id": response.get("id")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/today")
def upload_today():
    """
    Uploads all videos scheduled for today's date.
    Best for daily backend cron.
    """
    rows = read_schedule()
    uploaded = get_uploaded_files()
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
            response = upload_to_youtube(row)

            row["status"] = "uploaded"
            mark_uploaded(filename)

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

    write_schedule(rows)

    return {
        "status": "success",
        "date": today,
        "uploaded_today": len([r for r in results if r["status"] == "uploaded"]),
        "results": results,
    }


def scheduled_daily_upload():
    """
    Auto worker:
    every day morning, upload today's scheduled videos to YouTube.
    YouTube will publish them at publish_time.
    """
    try:
        print("Running daily auto upload...")
        upload_today()
    except Exception as e:
        print(f"Daily upload error: {e}")


def auto_generate_schedule():
    """
    Check if there are any new videos in the videos folder 
    that are not in the schedule.csv, and auto-schedule them.
    """
    try:
        print("Checking for new videos to auto-schedule...")
        video_files = [
            f for f in sorted(os.listdir(VIDEOS_DIR))
            if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
        ]
        
        current_schedule = read_schedule()
        scheduled_filenames = set(r["filename"] for r in current_schedule)
        
        new_videos = [f for f in video_files if f not in scheduled_filenames]
        
        if not new_videos:
            return

        # Determine the next available start date
        if current_schedule:
            last_publish = current_schedule[-1]["publish_time"]
            last_date_str = last_publish.split("T")[0]
            start_date = datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=1)
        else:
            start_date = datetime.now() + timedelta(days=1)

        # Reuse generate_schedule logic but for internal use
        daily_uploads = len(UPLOAD_TIMES)
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
            
        write_schedule(rows)
        print(f"Auto-scheduled {len(new_videos)} new videos.")
    except Exception as e:
        print(f"Auto-schedule error: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_daily_upload, "cron", hour=6, minute=0)
scheduler.add_job(auto_generate_schedule, "cron", hour=1, minute=0) # Check for new videos at 1 AM
scheduler.start()
