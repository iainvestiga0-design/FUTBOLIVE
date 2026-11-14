"""Proveedor de datos reales: TheSportsDB (llave pública gratuita "123").

Convierte la respuesta de la API a un formato propio y estable, de modo que si
mañana cambias de proveedor solo se toca este archivo.
"""
from datetime import datetime, timezone

import asyncio
import time

import httpx

from . import config
from .leagues import BY_SLUG

CALENDAR_YEAR_LEAGUES = {"libertadores", "betplay", "liga1"}  # temporada = año calendario


class ProviderError(Exception):
    pass


def current_season(slug: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if slug in CALENDAR_YEAR_LEAGUES:
        return str(now.year)
    start = now.year if now.month >= 7 else now.year - 1
    return f"{start}-{start + 1}"


_lock = asyncio.Lock()
_last = 0.0
_memo: dict = {}  # cachés de rondas y de números de ronda (se limpia al reiniciar)


async def _throttle():
    """Espacia las peticiones al proveedor (límite de la llave gratuita)."""
    global _last
    if config.MIN_INTERVAL <= 0:
        return
    async with _lock:
        wait = _last + config.MIN_INTERVAL - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last = time.monotonic()


async def _get(client: httpx.AsyncClient, endpoint: str, **params) -> dict:
    """GET con hasta 3 intentos (el plan gratuito responde 429 si se pide muy rápido)."""
    url = f"{config.SPORTSDB_BASE}/{config.SPORTSDB_KEY}/{endpoint}.php"
    last = None
    for attempt in range(3):
        try:
            await _throttle()
            r = await client.get(url, params=params, timeout=config.HTTP_TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
            else:
                r.raise_for_status()
                return r.json() or {}
        except (httpx.HTTPError, ValueError) as e:
            last = f"{type(e).__name__}: {e}"
        await asyncio.sleep(1.0 * (attempt + 1))
    raise ProviderError(f"{endpoint} {params}: {last}")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _kickoff(ev: dict) -> str | None:
    ts = ev.get("strTimestamp")
    if ts:
        return ts.replace(" ", "T").rstrip("Z") + "Z"
    d, t = ev.get("dateEvent"), ev.get("strTime") or "00:00:00"
    return f"{d}T{t}Z" if d else None


def _status(ev: dict, kickoff: str | None) -> tuple[str, str | None]:
    raw = (ev.get("strStatus") or "").strip().lower()
    if raw in {"match finished", "ft", "aet", "pen", "after extra time", "finished"}:
        return "FT", None
    if raw in {"not started", "ns", "", "scheduled"}:
        has_score = ev.get("intHomeScore") not in (None, "")
        if not has_score:
            return "NS", None
        return "FT", None
    if raw in {"postponed", "pst", "cancelled", "canceled", "abandoned"}:
        return "PST", None
    if raw == "ht":
        return "LIVE", "ET"  # entretiempo
    # 1H, 2H, ET, minutos tipo "45", etc.
    prog = ev.get("strProgress")
    return "LIVE", (f"{prog}'" if prog else None)


def _normalize_event(ev: dict, slug: str) -> dict | None:
    league = BY_SLUG[slug]
    if league["expect"].lower() not in (ev.get("strLeague") or "").lower():
        return None
    kick = _kickoff(ev)
    status, minute = _status(ev, kick)
    hs, as_ = _int(ev.get("intHomeScore")), _int(ev.get("intAwayScore"))
    return {
        "id": str(ev.get("idEvent")),
        "league": slug,
        "league_name": league["name"],
        "kickoff": kick,
        "status": status,
        "minute": minute,
        "home": {"name": ev.get("strHomeTeam"), "badge": ev.get("strHomeTeamBadge"), "score": hs},
        "away": {"name": ev.get("strAwayTeam"), "badge": ev.get("strAwayTeamBadge"), "score": as_},
        "venue": ev.get("strVenue") or None,
        "round": ev.get("intRound") or None,
    }


def _is_final(m: dict) -> bool:
    return m["status"] in ("FT", "PST")


async def _round_events(client, slug: str, lid: int, season: str, rnd: int) -> list[dict]:
    """Partidos de una jornada. Las jornadas terminadas se guardan 6 h; las demás 2 min."""
    key = ("round", slug, rnd)
    hit = _memo.get(key)
    if hit and time.monotonic() - hit[0] < hit[2]:
        return hit[1]
    data = await _get(client, "eventsround", id=lid, r=rnd, s=season)
    events = [m for ev in (data.get("events") or []) if (m := _normalize_event(ev, slug)) and m["kickoff"]]
    ttl = 21600 if events and all(_is_final(m) for m in events) else 120
    _memo[key] = (time.monotonic(), events, ttl)
    return events


async def fetch_matches(client: httpx.AsyncClient, slug: str) -> list[dict]:
    """Último y próximo partido (siempre) + jornadas vecinas completas (si la liga usa jornadas)."""
    lid = BY_SLUG[slug]["sportsdb_id"]
    info = _memo.get(("info", slug))
    if not info or time.monotonic() - info["ts"] > 1800:
        nxt = await _get(client, "eventsnextleague", id=lid)
        past = await _get(client, "eventspastleague", id=lid)
        past_ev, next_ev = past.get("events") or [], nxt.get("events") or []
        pr = [r for ev in past_ev if (r := _int(ev.get("intRound")))]
        nr = [r for ev in next_ev if (r := _int(ev.get("intRound")))]
        season = next((ev.get("strSeason") for ev in past_ev + next_ev if ev.get("strSeason")), None) or current_season(slug)
        rounds = set()
        if pr:
            rounds |= {max(pr) - 1, max(pr)}
        if nr:
            rounds |= {min(nr), min(nr) + 1}
        info = {"ts": time.monotonic(), "season": season, "rounds": sorted(r for r in rounds if r >= 1),
                "base": [m for ev in past_ev + next_ev if (m := _normalize_event(ev, slug)) and m["kickoff"]]}
        _memo[("info", slug)] = info

    by_id = {m["id"]: m for m in info["base"]}
    errors = []
    for rnd in info["rounds"]:
        try:
            for m in await _round_events(client, slug, lid, info["season"], rnd):
                by_id[m["id"]] = m  # los de la jornada son más recientes que los del arranque
        except ProviderError as e:
            errors.append(str(e))
    if errors and not by_id:
        raise ProviderError("; ".join(errors))
    return sorted(by_id.values(), key=lambda m: m["kickoff"])


async def fetch_standings(client: httpx.AsyncClient, slug: str) -> list[dict]:
    lid = BY_SLUG[slug]["sportsdb_id"]
    data = await _get(client, "lookuptable", l=lid, s=current_season(slug))
    rows = []
    for r in data.get("table") or []:
        rows.append({
            "rank": _int(r.get("intRank")),
            "team": r.get("strTeam"),
            "badge": r.get("strBadge"),
            "played": _int(r.get("intPlayed")),
            "won": _int(r.get("intWin")),
            "drawn": _int(r.get("intDraw")),
            "lost": _int(r.get("intLoss")),
            "gf": _int(r.get("intGoalsFor")),
            "ga": _int(r.get("intGoalsAgainst")),
            "gd": _int(r.get("intGoalDifference")),
            "points": _int(r.get("intPoints")),
        })
    rows.sort(key=lambda x: (x["rank"] is None, x["rank"] or 0))
    return rows
