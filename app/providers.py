"""Proveedor de datos reales: TheSportsDB (llave pública gratuita "123").

Convierte la respuesta de la API a un formato propio y estable, de modo que si
mañana cambias de proveedor solo se toca este archivo.
"""
from datetime import datetime, timezone

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


async def _get(client: httpx.AsyncClient, endpoint: str, **params) -> dict:
    url = f"{config.SPORTSDB_BASE}/{config.SPORTSDB_KEY}/{endpoint}.php"
    try:
        r = await client.get(url, params=params, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json() or {}
    except (httpx.HTTPError, ValueError) as e:
        raise ProviderError(f"{endpoint}: {e}") from e


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


async def fetch_matches(client: httpx.AsyncClient, slug: str) -> list[dict]:
    lid = BY_SLUG[slug]["sportsdb_id"]
    nxt = await _get(client, "eventsnextleague", id=lid)
    past = await _get(client, "eventspastleague", id=lid)
    events = (past.get("events") or []) + (nxt.get("events") or [])
    seen, out = set(), []
    for ev in events:
        m = _normalize_event(ev, slug)
        if m and m["kickoff"] and m["id"] not in seen:
            seen.add(m["id"])
            out.append(m)
    out.sort(key=lambda m: m["kickoff"])
    return out


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
