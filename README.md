# YouTube Shorts Auto Scheduler Backend

Ek FastAPI-based backend jo automatically daily videos YouTube par upload/schedule karta hai.

## Features

- ✅ OAuth2 Google authentication
- ✅ Video upload queue management
- ✅ Schedule CSV-based uploads
- ✅ Auto daily upload worker (6 AM daily)
- ✅ Custom publish times
- ✅ Track uploaded videos
- ✅ Swagger API docs

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google OAuth Setup

1. Google Cloud Console par jaao: https://console.cloud.google.com
2. New project banao
3. YouTube Data API v3 enable karo
4. OAuth 2.0 Client ID (Desktop app) create karo
5. `client_secret.json` download karke project root me rakh do

**Redirect URI (Google Cloud Console me add karna):**
- Local: `http://localhost:8000/auth/callback`
- Production: `https://your-domain.com/auth/callback`

### 3. Configure .env

Edit `.env` file:

```
APP_BASE_URL=http://localhost:8000
UPLOAD_TIMES=11:00,19:00
TIMEZONE_OFFSET=+05:30
DEFAULT_START_DATE=2026-05-21
```

**3 videos daily ke liye:**
```
UPLOAD_TIMES=11:00,17:00,21:00
```

### 4. Local Development

```bash
uvicorn main:app --reload
```

Open: http://localhost:8000

## Usage Flow

### Step 1: Connect YouTube Account

```
http://localhost:8000/auth/start
```

YouTube account se login karo.

### Step 2: Upload Videos

**Option A: Manual (File Explorer)**
- Videos folder me `.mp4` files copy karo

**Option B: API (Swagger)**
- http://localhost:8000/docs
- POST `/videos/upload` se upload karo

### Step 3: Generate Schedule

```
http://localhost:8000/schedule/generate?start_date=2026-05-21&daily_uploads=2
```

Schedule CSV automatically ban jayega.

### Step 4: Check Queue

```
http://localhost:8000/schedule
```

Pending videos dekho.

### Step 5: Manual Upload (Testing)

```
POST /upload/next
```

Swagger me `/upload/next` run karo.

## Auto Upload

Backend automatically har din 6:00 AM (server time) par:
- Aaj ke date ke videos ko YouTube par upload karega
- Scheduled publish times set karega

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Status check |
| GET | `/health` | Health check |
| GET | `/auth/start` | YouTube login |
| GET | `/auth/callback` | OAuth callback |
| POST | `/videos/upload` | Video file upload |
| GET | `/videos` | List videos |
| POST | `/schedule/generate` | Generate schedule |
| GET | `/schedule` | Get schedule queue |
| POST | `/upload/next` | Upload next video |
| POST | `/upload/today` | Upload today's videos |

## Deployment

### Best Platforms

- Render (free tier, persistent disk)
- Railway (volume support)
- DigitalOcean App Platform
- AWS Lightsail
- Heroku alternatives

### Build Command
```
pip install -r requirements.txt
```

### Start Command
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Important

- Backend hamesha ON hona chahiye
- Free hosting sleep karta hai, avoid karo auto uploads ke liye
- Videos folder persistent hona chahiye
- Data folder persistent hona chahiye

## Environment Variables

```
APP_BASE_URL          - Backend URL (local: http://localhost:8000)
VIDEOS_DIR            - Videos folder path (default: videos)
DATA_DIR              - Data folder path (default: data)
UPLOAD_TIMES          - Comma-separated times (11:00,19:00)
TIMEZONE_OFFSET       - Timezone (+05:30, +00:00, etc)
DEFAULT_START_DATE    - Start date (YYYY-MM-DD)
DEFAULT_DESCRIPTION   - Video description
DEFAULT_TAGS          - Comma-separated tags
```

## File Structure

```
youtube-shorts-backend/
├── main.py
├── requirements.txt
├── .env
├── Procfile
├── client_secret.json
│
├── videos/
│   └── short1.mp4
│   └── short2.mp4
│
└── data/
    ├── schedule.csv
    ├── uploaded.txt
    └── token.json
```

## Troubleshooting

**Error: client_secret.json not found**
- Google Cloud se download karo aur root folder me rakh do

**Error: Token expired**
- `/auth/start` se fir se connect karo

**Videos not uploading at scheduled time**
- Backend must be running 24/7
- Server time check karo

**No videos found error**
- Videos folder check karo
- Sirf .mp4, .mov, .mkv, .webm files support hain

## License

MIT
