"""FUTBOLIVE — API (FastAPI) + servidor de la app web.

Ejecutar:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, demo, providers
from .leagues import BY_SLUG, LEAGUES, REGIONS, public

STATIC = Path(__file__).resolve().parent.parent / "static"

_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: float | None = None):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < (config.CACHE_TTL if ttl is None else ttl):
        return hit[1]
    return None


def store(key: str, value):
    _cache[key] = (time.time(), value)
    return value


# Datos por liga, mantenidos al día por una tarea en segundo plano:
# las peticiones de los usuarios NUNCA esperan al proveedor.
STORE: dict[str, dict] = {}


async def refresh_league(slug: str):
    try:
        data = await providers.fetch_matches(app.state.client, slug)
        STORE[slug] = {"matches": data, "error": None, "ts": time.time()}
    except providers.ProviderError as e:
        old = STORE.get(slug, {})
        STORE[slug] = {"matches": old.get("matches", []), "error": str(e), "ts": old.get("ts", 0)}


async def refresher():
    while True:
        for lg in LEAGUES:
            await refresh_league(lg["slug"])
        await asyncio.sleep(config.REFRESH_PAUSE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(headers={"User-Agent": "FUTBOLIVE/1.0"})
    task = asyncio.create_task(refresher()) if config.DATA_MODE != "demo" else None
    yield
    if task:
        task.cancel()
    await app.state.client.aclose()


app = FastAPI(title="FUTBOLIVE API", version="1.0.0", lifespan=lifespan)


def _check_league(slug: str):
    if slug not in BY_SLUG:
        raise HTTPException(404, f"Liga desconocida: {slug}")


def _league_matches(slug: str) -> tuple[list[dict], bool, str | None]:
    """Devuelve (partidos, es_demo, estado). estado: None=ok, 'cargando' o el error."""
    if config.DATA_MODE == "demo":
        return demo.matches(slug), True, None
    entry = STORE.get(slug)
    if entry is None:
        return [], False, "cargando"
    if not entry["matches"] and entry["error"]:
        return [], False, entry["error"]
    return entry["matches"], False, None


def _day_bounds():
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _parse(k: str) -> datetime:
    return datetime.fromisoformat(k.replace("Z", "+00:00"))


@app.get("/api/health")
async def health():
    return {"ok": True, "mode": config.DATA_MODE, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/leagues")
async def leagues():
    return {"regions": REGIONS, "leagues": [public(l) for l in LEAGUES]}


@app.get("/api/matches")
async def matches(
    league: str = Query("all", description="slug de liga o 'all'"),
    region: str = Query("todos", description="todos | europa | america"),
    when: str = Query("today", pattern="^(today|live|upcoming|results|all)$"),
):
    if league != "all":
        _check_league(league)
        slugs = [league]
    else:
        slugs = [l["slug"] for l in LEAGUES if region in ("todos", l["region"])]

    items, demo_leagues, errors = [], [], {}
    for slug in slugs:
        data, is_demo, err = _league_matches(slug)
        items.extend(data)
        if is_demo:
            demo_leagues.append(slug)
        if err:
            errors[slug] = err

    start, end = _day_bounds()
    now = datetime.now(timezone.utc)

    def keep(m):
        k = _parse(m["kickoff"])
        if when == "live":
            return m["status"] == "LIVE"
        if when == "today":
            return start <= k < end or m["status"] == "LIVE"
        if when == "upcoming":
            return m["status"] == "NS" and k >= now
        if when == "results":
            return m["status"] == "FT"
        return True

    items = [m for m in items if keep(m)]
    items.sort(key=lambda m: m["kickoff"], reverse=(when == "results"))
    return {
        "source": "demo" if demo_leagues else "live",
        "demo_leagues": demo_leagues,
        "loading": [k for k, v in errors.items() if v == "cargando"],
        "unavailable": [k for k, v in errors.items() if v != "cargando"],
        "errors": errors,
        "count": len(items),
        "matches": items,
        "updated": now.isoformat(),
    }


@app.get("/api/standings")
async def standings(league: str):
    _check_league(league)
    if config.DATA_MODE == "demo":
        return {"source": "demo", "league": public(BY_SLUG[league]), "table": demo.standings(league)}
    key = f"s:{league}"
    if (hit := cached(key, ttl=600)) is not None:
        return hit
    try:
        table = await providers.fetch_standings(app.state.client, league)
        resp = {"source": "live", "league": public(BY_SLUG[league]), "table": table}
        if not table:
            resp["note"] = "Tabla no disponible para esta competición."
        return store(key, resp)
    except providers.ProviderError as e:
        resp = {"source": "live", "league": public(BY_SLUG[league]), "table": [],
                "note": "No pudimos cargar la tabla ahora. Intenta de nuevo en un minuto.", "error": str(e)}
        _cache[key] = (time.time() - 600 + 20, resp)  # reintento a los ~20 s
        return resp


# --- App web (PWA) ---
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js", include_in_schema=False)
async def sw():
    # El service worker debe servirse desde la raíz para controlar toda la app
    return FileResponse(STATIC / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=STATIC), name="static")
