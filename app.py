import random
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import httpx

class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        import json
        return json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")

app = FastAPI(default_response_class=PrettyJSONResponse)

store = {}
RESET_HOUR_UTC = 4

# Sentinel value: timezone-aware datetime far in the past
_EPOCH_AWARE = datetime(1970, 1, 1, tzinfo=timezone.utc)

def _random_likes(level: int) -> int:
    if level < 30:
        return random.randint(50, 100)
    if level <= 50:
        return random.randint(100, 150)
    return random.randint(100, 220)

def _reset_time() -> datetime:
    now = datetime.now(timezone.utc)
    reset = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    return reset if now >= reset else reset - timedelta(days=1)

@app.get("/")
async def root():
    return {
        "message": "Divan's Like API",
        "endpoint": "/like?uid=12345678",
        "credit": "@DivanSingh, @FireXDecoder"
    }

@app.get("/like")
async def like(uid: str = Query(...)):
    reset = _reset_time()
    # Use the timezone-aware sentinel instead of datetime.min
    first = store.get(uid, _EPOCH_AWARE) < reset

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"https://info.killersharmabot.online/player-info?uid={uid}")
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return {
                "status": 0,
                "message": str(e),
                "UID": uid
            }

    basic = data.get("basicInfo")
    if not basic:
        return {"status": 0, "message": "Missing basicInfo", "UID": uid}

    level = basic.get("level")
    actual = basic.get("liked")
    if level is None or actual is None:
        return {"status": 0, "message": "Missing level/liked", "UID": uid}

    if first:
        fake = _random_likes(level)
        store[uid] = datetime.now(timezone.utc)   # store timezone-aware
    else:
        fake = 0

    return {
        "Level": level,
        "LikesGivenByAPI": fake,
        "LikesafterCommand": actual,
        "LikesbeforeCommand": actual - fake,
        "PlayerNickname": basic.get("nickname", "Unknown"),
        "Region": basic.get("region", "Unknown"),
        "UID": basic.get("accountId", uid),
        "status": 1
    }
