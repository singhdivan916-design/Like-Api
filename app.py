import asyncio
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

LIKE_LIMIT_STORE = {}
RESET_HOUR_UTC = 4
EPOCH_AWARE = datetime(1970, 1, 1, tzinfo=timezone.utc)

EXTERNAL_APIS = [
    {"name": "Frux", "url": "https://frux-like-apiii.vercel.app/like", "params": {"uid": "{uid}", "server_name": "{region}", "key": "fruxlikes"}, "like_field": "LikesGivenByAPI"},
    {"name": "AutoLike", "url": "https://autolike1-2000-like1-api.vercel.app/like", "params": {"uid": "{uid}", "server_name": "{region}", "key": "AJAY"}, "like_field": "LikesGivenByAPI"},
    {"name": "Rishu", "url": "https://rishu-codex.vercel.app/rishu", "params": {"uid": "{uid}"}, "like_field": "likes_sent"},
    {"name": "Darki", "url": "https://darki-like.vercel.app/like", "params": {"uid": "{uid}", "server_name": "{region}"}, "like_field": "LikesGivenByAPI"}
]

def get_random_likes(level: int, actual_likes: int) -> int:
    if level < 30:
        fake = random.randint(50, 100)
    elif level <= 50:
        fake = random.randint(100, 150)
    else:
        fake = random.randint(100, 220)
    if actual_likes == 0:
        return 1
    if fake > actual_likes:
        return actual_likes
    return fake

def get_reset_time() -> datetime:
    now = datetime.now(timezone.utc)
    reset = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    return reset if now >= reset else reset - timedelta(days=1)

async def call_external_api(client, api_def, uid, region):
    params = {k: v.format(uid=uid, region=region) for k, v in api_def["params"].items()}
    try:
        resp = await client.get(api_def["url"], params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        likes = data.get(api_def["like_field"], 0)
        if api_def["like_field"] == "likes_sent" and "increase" in data:
            likes = data.get("increase", likes)
        return {"name": api_def["name"], "likes_given": likes, "status": data.get("status", -1)}
    except Exception:
        return {"name": api_def["name"], "likes_given": 0, "status": -1}

@app.get("/")
async def root():
    return {
        "message": "Divan's Like API",
        "endpoint": "/like?uid=12345678",
        "credit": "@DivanSingh, @FireXDecoder"
    }

@app.get("/like")
async def like(uid: str = Query(...), region: str = Query(None)):
    # 1. Fetch player info
    info_url = f"https://info.killersharmabot.online/player-info?uid={uid}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(info_url)
            r.raise_for_status()
            info = r.json()
        except Exception as e:
            return {"status": 0, "message": str(e), "UID": uid}

    basic = info.get("basicInfo")
    if not basic:
        return {"status": 0, "message": "Missing basicInfo", "UID": uid}

    level = basic.get("level")
    actual = basic.get("liked")
    nickname = basic.get("nickname", "Unknown")
    player_region = basic.get("region", "Unknown")
    if not region:
        region = player_region

    if level is None or actual is None:
        return {"status": 0, "message": "Missing level/liked", "UID": uid}

    # 2. Daily limit & main fake likes
    reset = get_reset_time()
    first = LIKE_LIMIT_STORE.get(uid, EPOCH_AWARE) < reset
    if first:
        main_likes = get_random_likes(level, actual)
        LIKE_LIMIT_STORE[uid] = datetime.now(timezone.utc)
    else:
        main_likes = 0

    # 3. Call external APIs
    async with httpx.AsyncClient(timeout=15) as client:
        tasks = [call_external_api(client, api, uid, region) for api in EXTERNAL_APIS]
        ext_results = await asyncio.gather(*tasks)

    # 4. Sum external likes
    ext_total = sum(res["likes_given"] for res in ext_results)
    total_likes = main_likes + ext_total

    # 5. Build original response (unchanged fields)
    response = {
        "Level": level,
        "LikesGivenByAPI": main_likes,          # unchanged meaning: your API's own likes
        "LikesafterCommand": actual,
        "LikesbeforeCommand": actual - main_likes,
        "PlayerNickname": nickname,
        "Region": player_region,
        "UID": uid,
        "status": 1,
        # Extra fields (do not break existing clients)
        "total_likes_given_all_apis": total_likes,
        "external_apis": ext_results
    }
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
