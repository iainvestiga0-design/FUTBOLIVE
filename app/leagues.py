"""Catálogo de competiciones.

`sportsdb_id`: id de la liga en TheSportsDB.
`expect`: palabra que debe aparecer en el nombre de la liga que devuelve la API.
Si no coincide, ese resultado se descarta (protege contra un id equivocado).
Para agregar una liga: añade una línea aquí. Los ids se ven en la URL de
https://www.thesportsdb.com/League/<id>
"""

LEAGUES = [
    {"slug": "champions", "name": "Champions League", "country": "Europa", "region": "europa", "icon": "🏆", "sportsdb_id": 4480, "expect": "Champions"},
    {"slug": "premier", "name": "Premier League", "country": "Inglaterra", "region": "europa", "icon": "🦁", "sportsdb_id": 4328, "expect": "Premier"},
    {"slug": "laliga", "name": "LaLiga", "country": "España", "region": "europa", "icon": "⚽", "sportsdb_id": 4335, "expect": "La Liga"},
    {"slug": "seriea", "name": "Serie A", "country": "Italia", "region": "europa", "icon": "🇮🇹", "sportsdb_id": 4332, "expect": "Serie A"},
    {"slug": "bundesliga", "name": "Bundesliga", "country": "Alemania", "region": "europa", "icon": "🇩🇪", "sportsdb_id": 4331, "expect": "Bundesliga"},
    {"slug": "ligue1", "name": "Ligue 1", "country": "Francia", "region": "europa", "icon": "🇫🇷", "sportsdb_id": 4334, "expect": "Ligue 1"},
    {"slug": "libertadores", "name": "Copa Libertadores", "country": "Sudamérica", "region": "america", "icon": "🌎", "sportsdb_id": 4501, "expect": "Libertadores"},
    {"slug": "betplay", "name": "Liga BetPlay", "country": "Colombia", "region": "america", "icon": "🇨🇴", "sportsdb_id": 4497, "expect": "Colombia"},
    {"slug": "amistosos", "name": "Amistosos", "country": "Selecciones", "region": "selecciones", "icon": "🤝", "sportsdb_id": 4562, "expect": "Friendlies", "by_day": True, "table": False},
    {"slug": "liga1", "name": "Liga 1 Perú", "country": "Perú", "region": "america", "icon": "🇵🇪", "sportsdb_id": 4688, "expect": "Peru"},
]

BY_SLUG = {l["slug"]: l for l in LEAGUES}

REGIONS = {"todos": "Todos", "europa": "Europa", "america": "América", "selecciones": "Selecciones"}


def public(league: dict) -> dict:
    """Versión de la liga que se expone en la API (sin datos internos)."""
    return {**{k: league[k] for k in ("slug", "name", "country", "region", "icon")}, "has_table": league.get("table", True)}
