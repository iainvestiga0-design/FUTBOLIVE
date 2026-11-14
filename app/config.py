"""Configuración leída de variables de entorno (ver .env.example)."""
import os

# auto  = intenta datos reales; si fallan, usa demostración (recomendado)
# live  = solo datos reales (error 502 si el proveedor falla)
# demo  = siempre datos de demostración (no usa internet)
DATA_MODE = os.getenv("DATA_MODE", "auto").lower()

# TheSportsDB: la llave pública gratuita es "123". Si compras plan, pon tu llave aquí.
SPORTSDB_KEY = os.getenv("SPORTSDB_KEY", "123")
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json"

CACHE_TTL = int(os.getenv("CACHE_TTL", "120"))  # segundos
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "8"))

# Zona horaria en que se muestran las horas (el celular las convierte a su hora local)
TIMEZONE = os.getenv("TIMEZONE", "America/Bogota")
