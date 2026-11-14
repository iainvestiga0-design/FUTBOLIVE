"""Configuración leída de variables de entorno (ver .env.example)."""
import os

# auto / live = solo datos reales. Si una liga falla queda vacía y se avisa (nunca se inventan partidos)
# demo        = datos de ejemplo, sin internet (solo para pruebas locales)
DATA_MODE = os.getenv("DATA_MODE", "auto").lower()

# TheSportsDB: la llave pública gratuita es "123". Si compras plan, pon tu llave aquí.
SPORTSDB_KEY = os.getenv("SPORTSDB_KEY", "123")
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json"

CACHE_TTL = int(os.getenv("CACHE_TTL", "120"))  # segundos
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "8"))

# Zona horaria en que se muestran las horas (el celular las convierte a su hora local)
TIMEZONE = os.getenv("TIMEZONE", "America/Bogota")

# La llave gratuita permite ~30 peticiones/min: se espacian para no ser bloqueados.
# Con llave de pago (plan premium) puedes bajarlo con MIN_INTERVAL=0.7
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "2.2" if SPORTSDB_KEY == "123" else "0.7"))
# Pausa (segundos) entre una vuelta completa de actualización de ligas y la siguiente
REFRESH_PAUSE = float(os.getenv("REFRESH_PAUSE", "45"))
