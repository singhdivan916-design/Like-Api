import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import httpx

class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        import json
        return json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")

app = FastAPI(default_response_class=PrettyJSONResponse)

# External APIs
INFO_API_URL = "https://info.killersharmabot.online/player-info"
RISHU_API_URL = "https://rishu-codex.vercel.app/rishu"
FRUX_API_URL = "https://frux-like-apiii.vercel.app/like"
FRUX_KEY = "fruxlikes"

async def fetch_player_info(uid: str, client: httpx.AsyncClient):
    """Get level, nickname, region, and actual likes from info API."""
    resp = await client.get(INFO_API_URL, params={"uid": uid}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    basic = data.get("basicInfo")
    if not basic:
        raise ValueError("Missing basicInfo in info API response")
    return {
        "level": basic.get("level"),
        "nickname": basic.get("nickname", "Unknown"),
        "region": basic.get("region", "Unknown"),
        "actual_likes": basic.get("liked", 0)
    }

async def call_rishu_api(uid: str, client: httpx.AsyncClient) -> int:
    try:
        resp = await client.get(RISHU_API_URL, params={"uid": uid}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("likes_sent", 0)
    except Exception:
        return 0

async def call_frux_api(uid: str, region: str, client: httpx.AsyncClient) -> int:
    try:
        resp = await client.get(FRUX_API_URL, params={
            "uid": uid,
            "server_name": region,
            "key": FRUX_KEY
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("LikesGivenByAPI", 0)
    except Exception:
        return 0

@app.get("/")
async def root():
    return {
        "message": "Divan's Like API",
        "endpoint": "/like?uid=12345678",
        "credit": "@DivanSingh, @FireXDecoder"
    }

@app.get("/like")
async def like(uid: str = Query(...)):
    async with httpx.AsyncClient() as client:
        # 1. Fetch player info
        try:
            info = await fetch_player_info(uid, client)
        except Exception as e:
            return {
                "status": 0,
                "message": f"Failed to fetch player info: {str(e)}",
                "UID": uid
            }

        level = info["level"]
        nickname = info["nickname"]
        region = info["region"]
        actual = info["actual_likes"]

        # 2. Call both like APIs concurrently
        rishu_task = call_rishu_api(uid, client)
        frux_task = call_frux_api(uid, region, client)
        rishu_likes, frux_likes = await asyncio.gather(rishu_task, frux_task)

    total_likes = rishu_likes + frux_likes

    # 3. Prevent negative likes_before
    if total_likes > actual:
        total_likes = actual   # cap at actual likes
        likes_before = 0
    else:
        likes_before = actual - total_likes

    # 4. Return original response format
    return {
        "Level": level,
        "LikesGivenByAPI": total_likes,
        "LikesafterCommand": actual,
        "LikesbeforeCommand": likes_before,
        "PlayerNickname": nickname,
        "Region": region,
        "UID": uid,
        "status": 1 if total_likes > 0 else 0   # status 1 if any likes given
    }
