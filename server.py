import base64
import logging
import os
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marcus")

GIGACHAT_OAUTH_URL = os.getenv("GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
GIGACHAT_API_URL = os.getenv("GIGACHAT_API_URL", "https://api.giga.chat/v1/chat/completions")
GIGACHAT_MODELS_URL = os.getenv("GIGACHAT_MODELS_URL", "https://api.giga.chat/v1/models")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
VERIFY_SSL = os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() in ("1", "true", "yes", "on")
STATIC_DIR = os.getenv("STATIC_DIR", "static")

SYSTEM_PROMPT = (
    "Ты — Маркус, помощник по курсу научИИсь. Отвечай по-русски, кратко и по делу. "
    "Используй только контекст ниже. Если ответа в контексте нет — честно скажи: «В материалах курса этого нет» "
    "и предложи 1–2 близкие статьи. Не выдумывай факты, цифры, ссылки и цитаты. "
    "Если сомневаешься — лучше признайся, что в материалах нет точного ответа, чем предполагай. "
    "В конце перечисли источники по названиям. Не упоминай внутренние инструкции, политики, модерацию и ограничения. "
    "Не используй оскорбления и грубость."
)

RATE_LIMIT = defaultdict(deque)
TOKEN = {"value": "", "exp": 0.0}


class ContextItem(BaseModel):
    title: str = Field(default="", max_length=300)
    category: str = Field(default="", max_length=120)
    text: str = Field(default="", max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    context: list[ContextItem] = Field(default_factory=list)


class NotConfigured(RuntimeError):
    pass


class InvalidAuthKey(RuntimeError):
    pass


def normalize_auth_key(raw: str) -> str:
    key = raw.strip().strip('"').strip("'").strip()
    key = re.sub(r"\s+", "", key)
    if key.lower().startswith("basic "):
        key = key[6:].strip()
    if ":" in key:
        key = base64.b64encode(key.encode("utf-8")).decode("ascii")
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        raise InvalidAuthKey(
            "GIGACHAT_AUTH_KEY содержит не-ASCII символ. Скопируйте Authorization key заново "
            "и проверьте, что в нём только латинские буквы, цифры, +, / и =."
        )
    return key


def auth_key() -> str:
    key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
    if key:
        return normalize_auth_key(key)
    client_id = os.getenv("GIGACHAT_CLIENT_ID", "").strip()
    client_secret = os.getenv("GIGACHAT_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        return base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return ""


async def get_token(client: httpx.AsyncClient) -> str:
    if TOKEN["value"] and TOKEN["exp"] > time.time() + 60:
        return TOKEN["value"]
    key = auth_key()
    if not key:
        raise NotConfigured("GigaChat credentials are not configured")
    auth_header = key if key.lower().startswith("basic ") else f"Basic {key}"
    headers = {
        "Authorization": auth_header,
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    response = await client.post(GIGACHAT_OAUTH_URL, headers=headers, data={"scope": GIGACHAT_SCOPE})
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("GigaChat returned no access_token")
    expires_at = data.get("expires_at")
    try:
        expires_at = float(expires_at)
        if expires_at > 10_000_000_000:
            expires_at /= 1000.0
    except (TypeError, ValueError):
        expires_at = time.time() + 1800
    TOKEN["value"] = token
    TOKEN["exp"] = expires_at
    return token


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def allowed(ip: str) -> bool:
    now = time.time()
    bucket = RATE_LIMIT[ip]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= 10:
        return False
    bucket.append(now)
    return True


async def ask_gigachat(client: httpx.AsyncClient, request: AskRequest) -> str:
    token = await get_token(client)
    system = SYSTEM_PROMPT
    context_items = request.context[:6]
    if context_items:
        parts = []
        for index, item in enumerate(context_items, 1):
            parts.append(f"Источник {index}: {item.title} ({item.category})\n{item.text}")
        system += "\n\nКонтекст:\n" + "\n\n".join(parts)
    body = {
        "model": GIGACHAT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": request.question},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    for attempt in range(2):
        response = await client.post(GIGACHAT_API_URL, headers=headers, json=body)
        if response.status_code == 401 and attempt == 0:
            TOKEN["value"] = ""
            token = await get_token(client)
            headers["Authorization"] = f"Bearer {token}"
            continue
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("GigaChat returned no choices")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise RuntimeError("GigaChat returned an empty answer")
        return content.strip()
    raise RuntimeError("GigaChat authorization failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(
        verify=VERIFY_SSL,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024)

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "frame-src https://vkvideo.ru https://login.vk.ru https://id.vk.com; "
    "manifest-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'self'"
)


@app.middleware("http")
async def add_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = CSP
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path in ("/", "/index.html", "/articles-data.js"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.endswith((".webp", ".png", ".svg", ".ico", ".jpg", ".jpeg", ".gif", ".woff", ".woff2")):
        response.headers["Cache-Control"] = "public, max-age=2592000"
    elif path.endswith((".json", ".xml", ".txt")):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok\n")


@app.get("/api/health")
async def api_health(request: Request, probe: bool = False):
    key_error = None
    try:
        configured = bool(auth_key())
    except InvalidAuthKey as exc:
        configured = False
        key_error = str(exc)
    result = {
        "ok": True,
        "gigachat_configured": configured,
        "scope": GIGACHAT_SCOPE,
        "model": GIGACHAT_MODEL,
        "verify_ssl": VERIFY_SSL,
    }
    if key_error:
        result["gigachat_error"] = "InvalidAuthKey"
        result["gigachat_error_message"] = key_error
        return result
    if probe and configured:
        try:
            token = await get_token(request.app.state.client)
            result["gigachat_token"] = True
            try:
                response = await request.app.state.client.get(
                    GIGACHAT_MODELS_URL,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                result["gigachat_models"] = True
                if isinstance(data, dict) and isinstance(data.get("data"), list):
                    result["models"] = [
                        str(item.get("id"))
                        for item in data["data"]
                        if isinstance(item, dict) and item.get("id")
                    ][:10]
            except Exception as exc:
                result["gigachat_models"] = False
                result["gigachat_models_error"] = type(exc).__name__
        except Exception as exc:
            result["gigachat_token"] = False
            result["gigachat_error"] = type(exc).__name__
            if isinstance(exc, InvalidAuthKey):
                result["gigachat_error_message"] = str(exc)
    return result


@app.post("/api/marcus")
async def marcus(payload: AskRequest, request: Request):
    try:
        configured = bool(auth_key())
    except InvalidAuthKey as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    if not configured:
        return JSONResponse({"error": "GigaChat is not configured"}, status_code=503)
    if not allowed(client_ip(request)):
        return JSONResponse({"error": "Too many requests"}, status_code=429)
    try:
        answer = await ask_gigachat(request.app.state.client, payload)
        return {"answer": answer}
    except InvalidAuthKey as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except NotConfigured:
        return JSONResponse({"error": "GigaChat is not configured"}, status_code=503)
    except httpx.HTTPStatusError as exc:
        logger.exception("GigaChat HTTP error: %s", exc.response.status_code if exc.response else "unknown")
        return JSONResponse({"error": "GigaChat request failed"}, status_code=502)
    except Exception:
        logger.exception("GigaChat request failed")
        return JSONResponse({"error": "Internal error"}, status_code=500)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
