import asyncio
import os

os.environ["DATA_MODE"] = "demo"
os.environ["MIN_INTERVAL"] = "0"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, main, providers
from app.main import app


@pytest.fixture(autouse=True)
def _clean():
    providers._memo.clear(); main.STORE.clear(); main._cache.clear()
    yield
    providers._memo.clear(); main.STORE.clear(); main._cache.clear()


def test_health_and_leagues():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"] is True
        data = c.get("/api/leagues").json()
        slugs = {l["slug"] for l in data["leagues"]}
        assert {"premier", "betplay", "liga1"} <= slugs


def test_demo_matches_today_has_live_and_is_flagged_demo():
    with TestClient(app) as c:
        r = c.get("/api/matches", params={"when": "today"}).json()
        assert r["source"] == "demo"
        assert any(m["status"] == "LIVE" for m in r["matches"])
        assert all(m["home"]["name"] and m["away"]["name"] for m in r["matches"])


def test_filters():
    with TestClient(app) as c:
        eu = c.get("/api/matches", params={"region": "europa", "when": "all"}).json()["matches"]
        assert eu and all(m["league"] not in ("betplay", "liga1", "libertadores") for m in eu)
        res = c.get("/api/matches", params={"when": "results", "league": "laliga"}).json()["matches"]
        assert res and all(m["status"] == "FT" for m in res)
        up = c.get("/api/matches", params={"when": "upcoming", "league": "liga1"}).json()["matches"]
        assert up and all(m["status"] == "NS" for m in up)


def test_standings_and_errors():
    with TestClient(app) as c:
        t = c.get("/api/standings", params={"league": "premier"}).json()["table"]
        assert t[0]["rank"] == 1 and t[0]["points"] >= t[-1]["points"]
        assert c.get("/api/standings", params={"league": "nope"}).status_code == 404
        assert c.get("/api/matches", params={"when": "xx"}).status_code == 422


def test_static_app_is_served():
    with TestClient(app) as c:
        assert "FUTBOLIVE" in c.get("/").text
        assert c.get("/manifest.webmanifest").status_code == 200
        assert c.get("/sw.js").headers["content-type"].startswith("application/javascript")


# --- Proveedor real, con respuesta simulada (formato de TheSportsDB) ---
def _mock_client():
    def handler(req: httpx.Request):
        ep = req.url.path.rsplit("/", 1)[-1]
        if ep == "eventsnextleague.php":
            return httpx.Response(200, json={"events": [{
                "idEvent": "1", "strLeague": "English Premier League",
                "strHomeTeam": "Liverpool", "strAwayTeam": "Everton",
                "intHomeScore": None, "intAwayScore": None, "strStatus": "Not Started",
                "strTimestamp": "2099-04-16T14:30:00", "strHomeTeamBadge": "h.png", "strAwayTeamBadge": "a.png",
            }, {  # liga equivocada: debe descartarse
                "idEvent": "2", "strLeague": "Other League", "strHomeTeam": "X", "strAwayTeam": "Y",
                "strStatus": "Not Started", "strTimestamp": "2099-04-16T14:30:00",
            }]})
        if ep == "eventspastleague.php":
            return httpx.Response(200, json={"events": [{
                "idEvent": "3", "strLeague": "English Premier League",
                "strHomeTeam": "Chelsea", "strAwayTeam": "Arsenal",
                "intHomeScore": "2", "intAwayScore": "1", "strStatus": "Match Finished",
                "strTimestamp": "2020-01-01T15:00:00",
            }]})
        if ep == "lookuptable.php":
            return httpx.Response(200, json={"table": [
                {"intRank": "2", "strTeam": "B", "intPlayed": "5", "intWin": "3", "intDraw": "1", "intLoss": "1",
                 "intGoalsFor": "8", "intGoalsAgainst": "4", "intGoalDifference": "4", "intPoints": "10"},
                {"intRank": "1", "strTeam": "A", "intPlayed": "5", "intWin": "4", "intDraw": "1", "intLoss": "0",
                 "intGoalsFor": "9", "intGoalsAgainst": "2", "intGoalDifference": "7", "intPoints": "13"},
            ]})
        return httpx.Response(404)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_provider_normalizes_real_format():
    async def run():
        async with _mock_client() as c:
            m = await providers.fetch_matches(c, "premier")
            t = await providers.fetch_standings(c, "premier")
            return m, t
    matches, table = asyncio.run(run())
    assert [m["id"] for m in matches] == ["3", "1"]  # ordenados, liga equivocada descartada
    assert matches[0]["status"] == "FT" and matches[0]["home"]["score"] == 2
    assert matches[1]["status"] == "NS" and matches[1]["home"]["badge"] == "h.png"
    assert matches[1]["kickoff"].endswith("Z")
    assert [r["team"] for r in table] == ["A", "B"] and table[0]["points"] == 13


def test_season_format():
    from datetime import datetime, timezone
    assert providers.current_season("premier", datetime(2026, 11, 13, tzinfo=timezone.utc)) == "2026-2027"
    assert providers.current_season("premier", datetime(2027, 3, 1, tzinfo=timezone.utc)) == "2026-2027"
    assert providers.current_season("betplay", datetime(2026, 11, 13, tzinfo=timezone.utc)) == "2026"


def test_failed_league_is_reported_and_never_filled_with_fake_data(monkeypatch):
    monkeypatch.setattr(config, "DATA_MODE", "auto")

    async def boom(*a, **k):
        raise providers.ProviderError("HTTP 429")
    monkeypatch.setattr(providers, "fetch_matches", boom)
    with TestClient(app) as c:
        asyncio.run(main.refresh_league("premier"))  # simula una vuelta del refresco
        r = c.get("/api/matches", params={"league": "premier", "when": "all"}).json()
        assert r["source"] == "live" and r["count"] == 0
        assert r["unavailable"] == ["premier"] and "429" in r["errors"]["premier"]
        assert not any(m["id"].startswith("demo") for m in r["matches"])


def test_not_yet_loaded_league_is_reported_as_loading(monkeypatch):
    monkeypatch.setattr(config, "DATA_MODE", "auto")

    async def idle():
        pass
    monkeypatch.setattr(main, "refresher", idle)
    with TestClient(app) as c:
        r = c.get("/api/matches", params={"league": "laliga", "when": "all"}).json()
        assert r["loading"] == ["laliga"] and r["unavailable"] == [] and r["count"] == 0


def test_rounds_give_full_matchdays_and_finished_rounds_are_cached():
    calls = []

    def ev(i, rnd, status, h=None, a=None):
        return {"idEvent": str(i), "strLeague": "English Premier League", "strSeason": "2026-2027",
                "strHomeTeam": f"H{i}", "strAwayTeam": f"A{i}", "intRound": str(rnd), "strStatus": status,
                "intHomeScore": h, "intAwayScore": a, "strTimestamp": f"2026-11-{rnd:02d}T15:00:00"}

    def handler(req):
        ep = req.url.path.rsplit("/", 1)[-1]
        calls.append((ep, req.url.params.get("r")))
        if ep == "eventspastleague.php":
            return httpx.Response(200, json={"events": [ev(100, 10, "FT", "1", "0")]})
        if ep == "eventsnextleague.php":
            return httpx.Response(200, json={"events": [ev(200, 11, "NS")]})
        if ep == "eventsround.php":
            r = int(req.url.params["r"])
            if r == 11:
                return httpx.Response(200, json={"events": [ev(210 + k, 11, "NS") for k in range(10)]})
            if r in (9, 10):
                return httpx.Response(200, json={"events": [ev(r * 10 + k, r, "FT", "2", "1") for k in range(10)]})
            return httpx.Response(200, json={"events": None})
        return httpx.Response(404)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            first = await providers.fetch_matches(c, "premier")
            n_after_first = len(calls)
            await providers.fetch_matches(c, "premier")
            return first, n_after_first, len(calls)
    first, n1, n2 = asyncio.run(run())
    assert sum(m["status"] == "FT" for m in first) >= 20 and sum(m["status"] == "NS" for m in first) >= 10
    assert len({m["id"] for m in first}) == len(first)  # sin duplicados
    rounds_asked = sorted(r for ep, r in calls if ep == "eventsround.php")
    assert rounds_asked == ["10", "11", "12", "9"] or set(rounds_asked) == {"9", "10", "11", "12"}
    # 2.ª vuelta: no repite jornadas terminadas (9, 10) ni la consulta de arranque
    again = [(ep, r) for ep, r in calls[n1:]]
    assert ("eventsround.php", "9") not in again and ("eventsround.php", "10") not in again
    assert ("eventspastleague.php", None) not in again


def test_provider_retries_on_429(monkeypatch):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] < 3 else httpx.Response(200, json={"events": []})

    async def nosleep(_): pass
    monkeypatch.setattr(providers.asyncio, "sleep", nosleep)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await providers._get(c, "eventsnextleague", id=1)
    assert asyncio.run(run()) == {"events": []} and calls["n"] == 3
