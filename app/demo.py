"""Datos de demostración. NO son partidos reales: se generan en torno a la fecha de hoy
para que la app se vea viva aunque no haya internet ni llave de API."""
from datetime import datetime, timedelta, timezone

from .leagues import LEAGUES

TEAMS = {
    "champions": ["Real Madrid", "Arsenal", "Bayern", "Inter", "PSG", "Man City", "Barcelona", "Dortmund"],
    "premier": ["Liverpool", "Everton", "Chelsea", "Tottenham", "Newcastle", "Aston Villa", "Man United", "Brighton"],
    "laliga": ["Barcelona", "Celta Vigo", "Atlético", "Sevilla", "Valencia", "Betis", "Real Sociedad", "Girona"],
    "seriea": ["Juventus", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Torino"],
    "bundesliga": ["Leverkusen", "Stuttgart", "Leipzig", "Frankfurt", "Wolfsburg", "Mainz", "Bremen", "Freiburg"],
    "ligue1": ["Marseille", "Lyon", "Monaco", "Lille", "Nice", "Rennes", "Lens", "Nantes"],
    "libertadores": ["Flamengo", "Boca Juniors", "River Plate", "Palmeiras", "Nacional", "Peñarol", "Atlético Nacional", "LDU Quito"],
    "betplay": ["Millonarios", "Nacional", "Junior", "América de Cali", "Santa Fe", "Once Caldas", "Tolima", "Medellín"],
    "liga1": ["Alianza Lima", "Universitario", "Sporting Cristal", "Cienciano", "Melgar", "Cusco FC", "Garcilaso", "Binacional"],
}


def _utc_noon(days: int) -> datetime:
    base = datetime.now(timezone.utc).replace(hour=19, minute=0, second=0, microsecond=0)
    return base + timedelta(days=days)


def matches(slug: str) -> list[dict]:
    """8 partidos: 2 pasados, 1 en vivo, 5 próximos."""
    teams = TEAMS[slug]
    league = next(l for l in LEAGUES if l["slug"] == slug)
    out = []
    # (día relativo, minutos de desfase, estado, marcador)
    plan = [
        (-2, 0, "FT", (2, 1)), (-1, 0, "FT", (0, 0)),
        (0, -55, "LIVE", (1, 1)),
        (0, 120, "NS", None), (1, 0, "NS", None), (2, 0, "NS", None),
        (4, 0, "NS", None), (6, 0, "NS", None),
    ]
    for i, (d, off, st, sc) in enumerate(plan):
        home, away = teams[(i * 2) % 8], teams[(i * 2 + 1) % 8]
        kick = _utc_noon(d) + timedelta(minutes=off)
        out.append({
            "id": f"demo-{slug}-{i}",
            "league": slug,
            "league_name": league["name"],
            "kickoff": kick.isoformat().replace("+00:00", "Z"),
            "status": st,
            "minute": "55'" if st == "LIVE" else None,
            "home": {"name": home, "badge": None, "score": sc[0] if sc else None},
            "away": {"name": away, "badge": None, "score": sc[1] if sc else None},
            "venue": None,
            "round": None,
        })
    return out


def standings(slug: str) -> list[dict]:
    teams = TEAMS[slug]
    rows = []
    for i, t in enumerate(teams):
        played = 12
        won = 9 - i
        drawn = 2 + (i % 3)
        lost = played - won - drawn
        gf, ga = 28 - i * 2, 10 + i * 2
        rows.append({
            "rank": i + 1, "team": t, "badge": None, "played": played,
            "won": won, "drawn": drawn, "lost": lost,
            "gf": gf, "ga": ga, "gd": gf - ga, "points": won * 3 + drawn,
        })
    return rows
