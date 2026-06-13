import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import httpx

class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        import json
        return json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")

app = FastAPI(default_response_class=PrettyJSONResponse)

# ------------------ Configuration ------------------
LIKE_LIMIT_STORE = {}          # uid -> last request datetime (UTC)
RESET_HOUR_UTC = 4             # daily reset at 4 AM UTC
EPOCH_AWARE = datetime(1970, 1, 1, tzinfo=timezone.utc)

EXTERNAL_APIS = [
    {
        "name": "Frux",
        "url": "https://frux-like-apiii.vercel.app/like",
        "params": {"uid": "{uid}", "server_name": "{region}", "key": "fruxlikes"},
        "like_field": "LikesGivenByAPI"
    },
    {
        "name": "AutoLike",
        "url": "https://autolike1-2000-like1-api.vercel.app/like",
        "params": {"uid": "{uid}", "server_name": "{region}", "key": "AJAY"},
        "like_field": "LikesGivenByAPI"
    },
    {
        "name": "Rishu",
        "url": "https://rishu-codex.vercel.app/rishu",
        "params": {"uid": "{uid}"},
        "like_field": "likes_sent"     # Rishu returns "likes_sent" as the increase
    },
    {
        "name": "Darki",
        "url": "https://darki-like.vercel.app/like",
        "params": {"uid": "{uid}", "server_name": "{region}"},
        "like_field": "LikesGivenByAPI"
    }
]
# ---------------------------------------------------

def get_reset_time() -> datetime:
    """Return the last 4 AM UTC datetime."""
    now = datetime.now(timezone.utc)
    reset_today = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    return reset_today if now >= reset_today else reset_today - timedelta(days=1)

async def call_external_api(client: httpx.AsyncClient, api_def: dict, uid: str, region: str) -> dict:
    """Call one external like API and return the number of likes it gave."""
    params = {k: v.format(uid=uid, region=region) for k, v in api_def["params"].items()}
    try:
        resp = await client.get(api_def["url"], params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        likes = data.get(api_def["like_field"], 0)
        # Special handling for Rishu (increase field also available)
        if api_def["like_field"] == "likes_sent" and "increase" in data:
            likes = data.get("increase", likes)
        return {"name": api_def["name"], "likes_given": likes, "status": data.get("status", -1)}
    except Exception:
        return {"name": api_def["name"], "likes_given": 0, "status": -1}

@app.get("/")
async def root():
    return {
        "message": "Divan's Real Like API",
        "endpoint": "/like?uid=12345678",
        "credit": "@DivanSingh, @FireXDecoder"
    }

@app.get("/like")
async def like(uid: str = Query(...), region: str = Query(None)):
    # 1. Fetch real player info
    info_url = f"https://info.killersharmabot.online/player-info?uid={uid}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(info_url)
            r.raise_for_status()
            info = r.json()
        except Exception as e:
            return {
                "status": 0,
                "message": f"Failed to fetch player info: {str(e)}",
                "UID": uid
            }

    basic = info.get("basicInfo")
    if not basic:
        return {"status": 0, "message": "Missing basicInfo", "UID": uid}

    level = basic.get("level")
    original_likes = basic.get("liked")
    nickname = basic.get("nickname", "Unknown")
    player_region = basic.get("region", "Unknown")
    account_id = basic.get("accountId", uid)

    if level is None or original_likes is None:
        return {"status": 0, "message": "Missing level or liked", "UID": uid}

    # Use passed region or fallback to player's region
    region = region or player_region

    # 2. Daily limit check (one real like request per UID per day)
    reset_time = get_reset_time()
    last_request = LIKE_LIMIT_STORE.get(uid, EPOCH_AWARE)
    first_request_today = last_request < reset_time

    if not first_request_today:
        # Already used today – return 0 total likes
        total_likes_given = 0
        external_summary = []
    else:
        # 3. Call all external like APIs concurrently
        async with httpx.AsyncClient(timeout=15) as client:
            tasks = [call_external_api(client, api, uid, region) for api in EXTERNAL_APIS]
            external_results = await asyncio.gather(*tasks)

        # 4. Sum real likes given by external APIs
        total_likes_given = sum(res["likes_given"] for res in external_results)
        external_summary = [
            {"api": res["name"], "likes_given": res["likes_given"], "status": res["status"]}
            for res in external_results
        ]
        # Store the timestamp of this successful request
        LIKE_LIMIT_STORE[uid] = datetime.now(timezone.utc)

    # 5. Build response – exactly the original structure
    response = {
        "Level": level,
        "LikesGivenByAPI": total_likes_given,                     # total real likes from external APIs
        "LikesafterCommand": original_likes + total_likes_given, # new total after adding
        "LikesbeforeCommand": original_likes,                    # original likes before
        "PlayerNickname": nickname,
        "Region": player_region,
        "UID": account_id,
        "status": 1 if total_likes_given > 0 else 0 if not first_request_today else 1,
    }
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
