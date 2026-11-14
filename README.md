# FUTBOLIVE

App web instalable (PWA) de fútbol para celular: partidos de hoy, en vivo, próximos, resultados y tablas de posiciones. Backend en Python (FastAPI) + app móvil en HTML/CSS/JS.

> **Importante:** FUTBOLIVE muestra marcadores, programación y tablas. **No transmite video.** Las transmisiones solo se pueden agregar con permiso escrito de cada competición/territorio.

## Estructura

```
app/        API en Python (FastAPI)
  main.py       endpoints + sirve la app
  providers.py  conexión a TheSportsDB (datos reales)
  demo.py       datos de ejemplo (sin internet)
  leagues.py    lista de ligas (aquí agregas más)
static/     la app (index.html, styles.css, app.js, manifest, service worker, iconos)
tests/      pruebas automáticas
docs/       imágenes de referencia de diseño
```

## 1. Probarla en tu computadora

Necesitas Python 3.10 o superior.

- **Mac/Linux:** `./run.sh`
- **Windows:** doble clic en `run.bat`

Abre `http://localhost:8000`. Arranca con datos reales. Sin internet usa `DATA_MODE=demo` para ver datos de ejemplo.

## 2. Probarla en tu celular (Android o iPhone)

**Opción A, mismo Wi-Fi (rápida):** con la app corriendo, abre en el celular la dirección que imprime `run.sh` (algo como `http://192.168.1.20:8000`). Si no abre, revisa que ambos estén en la misma red y que el firewall permita el puerto 8000.

**Opción B, publicada en internet (recomendada):** sube a GitHub y despliega en Render (abajo). Obtienes un enlace `https://...` que abre desde cualquier celular.

### Instalarla como app
La instalación como app requiere `https` (o `localhost`), por eso funciona con la Opción B.
- **Android (Chrome):** menú ⋮ → *Instalar app* / *Agregar a pantalla de inicio*.
- **iPhone (Safari):** botón Compartir → *Agregar a pantalla de inicio*.

Queda con su icono, abre a pantalla completa y carga al instante.

## 3. Subir a GitHub

```bash
cd FUTBOLIVE
git init
git add .
git commit -m "FUTBOLIVE v1"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/futbolive.git
git push -u origin main
```
(Crea antes el repositorio vacío en github.com → *New repository*.)

## 4. Publicar (GitHub guarda el código; Render lo ejecuta)

GitHub Pages **no** ejecuta Python, solo páginas estáticas. Para que funcione la API necesitas un servicio que corra Python. Con Render (plan gratuito):

1. Entra a render.com y conecta tu cuenta de GitHub.
2. *New +* → *Blueprint* → elige el repo `futbolive`. Render lee `render.yaml` y lo despliega.
3. Te da una URL `https://futbolive-xxxx.onrender.com`. Esa es tu app.

El plan gratuito se "duerme" tras un rato sin visitas y la primera carga tarda unos segundos. Cada `git push` la actualiza sola. Alternativas equivalentes: Railway, Fly.io o cualquier servidor con el `Dockerfile` incluido.

## Datos

- Fuente real: [TheSportsDB](https://www.thesportsdb.com) con su llave pública gratuita (`123`). Es una fuente comunitaria con límites: el plan gratuito devuelve pocos partidos por liga y puede tener retrasos, y **no es un marcador oficial en tiempo real**. Para marcadores en vivo fiables, más adelante conviene un plan de pago o un proveedor profesional (el cambio se hace solo en `app/providers.py`).
- Modos (`DATA_MODE`): `auto`/`live` (solo datos reales; si una liga falla queda vacía y la app avisa cuál, nunca inventa partidos) y `demo` (datos de ejemplo, solo para pruebas sin internet: `DATA_MODE=demo ./run.sh`).
- Los ids de liga están en `app/leagues.py`. Liga BetPlay (Colombia) y Liga 1 (Perú) fueron verificados contra el sitio; los de ligas europeas y Libertadores están sin verificar en vivo, y la app descarta cualquier resultado cuyo nombre de liga no coincida con el esperado.

## Probar el código

```bash
pip install -r requirements.txt
pytest
```

## Próximos pasos sugeridos
1. Noticias y detalle de partido (alineaciones, eventos).
2. Equipos favoritos y notificaciones (requiere cuentas: ver Supabase).
3. Cuentas y Premium (pagos solo cuando el servicio esté listo).
4. Publicar en Play Store / App Store envolviendo esta PWA.
