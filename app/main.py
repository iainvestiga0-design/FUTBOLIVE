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


def cached(key: str):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < config.CACHE_TTL:
        return hit[1]
    return None


def store(key: str, value):
    _cache[key] = (time.time(), value)
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(headers={"User-Agent": "FUTBOLIVE/1.0"})
    yield
    await app.state.client.aclose()


app = FastAPI(title="FUTBOLIVE API", version="1.0.0", lifespan=lifespan)


def _check_league(slug: str):
    if slug not in BY_SLUG:
        raise HTTPException(404, f"Liga desconocida: {slug}")


async def _league_matches(slug: str) -> tuple[list[dict], bool]:
    """Devuelve (partidos, es_demo)."""
    if config.DATA_MODE == "demo":
        return demo.matches(slug), True
    key = f"m:{slug}"
    if (hit := cached(key)) is not None:
        return hit
    try:
        data = await providers.fetch_matches(app.state.client, slug)
        return store(key, (data, False))
    except providers.ProviderError:
        if config.DATA_MODE == "live":
            raise
        # Falla breve: no reintentar de inmediato a cada petición
        return store(key, (demo.matches(slug), True))


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

    sem = asyncio.Semaphore(4)

    async def one(s):
        async with sem:
            return s, await _league_matches(s)

    try:
        results = await asyncio.gather(*(one(s) for s in slugs))
    except providers.ProviderError as e:
        raise HTTPException(502, f"Proveedor de datos no disponible: {e}")

    items, demo_leagues = [], []
    for slug, (data, is_demo) in results:
        items.extend(data)
        if is_demo:
            demo_leagues.append(slug)

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
        "source": "demo" if len(demo_leagues) == len(slugs) else ("mixed" if demo_leagues else "live"),
        "demo_leagues": demo_leagues,
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
    if (hit := cached(key)) is not None:
        return hit
    try:
        table = await providers.fetch_standings(app.state.client, league)
        resp = {"source": "live", "league": public(BY_SLUG[league]), "table": table}
        if not table and config.DATA_MODE == "auto":
            # Sin tabla publicada (p. ej. torneo por fases): mostrar vacío, no inventar
            resp["note"] = "Tabla no disponible para esta competición."
        return store(key, resp)
    except providers.ProviderError as e:
        if config.DATA_MODE == "live":
            raise HTTPException(502, f"Proveedor de datos no disponible: {e}")
        return store(key, {"source": "demo", "league": public(BY_SLUG[league]), "table": demo.standings(league)})


# --- App web (PWA) ---
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js", include_in_schema=False)
async def sw():
    # El service worker debe servirse desde la raíz para controlar toda la app
    return FileResponse(STATIC / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=STATIC), name="static")
