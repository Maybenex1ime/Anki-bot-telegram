import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "reminder.db"
MEDIA_DIR = DATA_DIR / "media"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
CEDICT_URL = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
DEFAULT_SETTINGS = {
    "reminder_times": "07:30,12:30,20:00",
    "evening_nudge": "21:30",
    "new_per_day": "20",
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "review_mode": "",
    "quiz_fast_sec": "5",
    "quiz_slow_sec": "15",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "max_sentences": "3000",
}


def today():
    return datetime.now(TZ).date()


def today_iso():
    return today().isoformat()
