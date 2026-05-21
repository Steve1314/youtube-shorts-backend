import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://vahlaydigital_db_user:GWOLQNfkkC6HZo15@cluster0.kaixweg.mongodb.net/?appName=Cluster0&tlsAllowInvalidCertificates=true")
client = MongoClient(MONGO_URI)
db = client["youtube_shorts_studio"]

# Collections
profiles_col = db["profiles"]
auth_col = db["auth"]
schedules_col = db["schedules"]
uploaded_col = db["uploaded"]

def db_get_profiles():
    profiles = list(profiles_col.find({}, {"_id": 0, "name": 1}))
    return [p["name"] for p in profiles] or ["default"]

def db_add_profile(name):
    if not profiles_col.find_one({"name": name}):
        profiles_col.insert_one({"name": name})

def db_delete_profile(name):
    profiles_col.delete_one({"name": name})
    auth_col.delete_one({"profile": name})
    schedules_col.delete_one({"profile": name})
    uploaded_col.delete_many({"profile": name})

def db_save_token(profile, token_data):
    auth_col.update_one(
        {"profile": profile},
        {"$set": {"token": token_data}},
        upsert=True
    )

def db_get_token(profile):
    doc = auth_col.find_one({"profile": profile})
    return doc["token"] if doc else None

def db_save_flow_state(profile, state_data):
    auth_col.update_one(
        {"profile": profile},
        {"$set": {"flow_state": state_data}},
        upsert=True
    )

def db_get_flow_state(profile):
    doc = auth_col.find_one({"profile": profile})
    return doc.get("flow_state") if doc else None

def db_save_schedule(profile, items):
    schedules_col.update_one(
        {"profile": profile},
        {"$set": {"items": items}},
        upsert=True
    )

def db_get_schedule(profile):
    doc = schedules_col.find_one({"profile": profile})
    return doc["items"] if doc else []

def db_mark_uploaded(profile, filename):
    uploaded_col.update_one(
        {"profile": profile, "filename": filename},
        {"$set": {"uploaded": True}},
        upsert=True
    )

def db_get_uploaded_files(profile):
    docs = list(uploaded_col.find({"profile": profile}))
    return [d["filename"] for d in docs]
