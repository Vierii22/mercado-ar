# MercadoAR — Fase 2A

Dashboard de seguimiento del Merval con precios reales desde Yahoo Finance.

## 📦 Qué hay en esta carpeta

```
mercado-ar/
├── dashboard.html       ← La web. Se abre con doble clic.
├── update_prices.py     ← El script que trae los precios.
├── data.json            ← (se genera al correr el script)
└── README.md            ← Este archivo
```

## 🛠️ Setup inicial (1 sola vez)

### 1. Instalá Python
Si nunca usaste Python, bajalo de [python.org/downloads](https://www.python.org/downloads/)
**IMPORTANTE:** durante la instalación tildá la opción **"Add Python to PATH"**.

Para verificar que se instaló bien, abrí una terminal (CMD en Windows, Terminal en Mac):
```bash
python --version
```
Debería mostrarte algo como `Python 3.12.x`.

### 2. Instalá la librería yfinance
En la terminal, escribí:
```bash
pip install yfinance
```

## ▶️ Cómo usarlo

### Paso 1 — Actualizar precios

Abrí una terminal en la carpeta donde están estos archivos y corré:
```bash
python update_prices.py
```

Vas a ver algo así:
```
┌─────────────────────────────────────────┐
│   MercadoAR — Fetch precios reales      │
│   2026-04-26 14:35:22                   │
└─────────────────────────────────────────┘

Descargando 9 tickers desde Yahoo Finance...

  → YPFD (YPFD.BA)... ✓ $32,480.00 (+5.21%)
  → GGAL (GGAL.BA)... ✓ $4,985.00 (+2.14%)
  → PAMP (PAMP.BA)... ✓ $6,720.00 (+3.87%)
  → BMA  (BMA.BA)...  ✓ $8,420.00 (+1.92%)
  → TXAR (TXAR.BA)... ✓ $1,395.00 (-2.84%)
  → ALUA (ALUA.BA)... ✓ $1,180.00 (+0.42%)
  → TECO2(TECO2.BA)...✓ $3,890.00 (-0.65%)
  → CEPU (CEPU.BA)... ✓ $2,410.00 (+1.35%)
  → AL30 (AL30.BA)... ✓ $74,250.00 (+0.18%)

✓ 9 tickers guardados en: data.json
```

### Paso 2 — Abrí el dashboard

Hacé **doble clic en `dashboard.html`** y se abre en tu navegador con todos los datos reales.

> 💡 **Tip:** si lo abrís y dice "no se encontró data.json", es porque el navegador
> está bloqueando la lectura de archivos locales. Ver la sección "Soluciones" abajo.

## 🤖 Automatizar (opcional)

### Windows — Task Scheduler
1. Buscá "Programador de tareas" en el menú inicio
2. Crear tarea básica → cada día → a las 18:30 (después del cierre del mercado)
3. Acción: Iniciar programa
   - Programa: `python`
   - Argumentos: `update_prices.py`
   - Iniciar en: la carpeta donde guardaste los archivos

### Mac/Linux — Cron
```bash
crontab -e
```
Agregá:
```
30 18 * * 1-5 cd /ruta/a/mercado-ar && python update_prices.py
```
(corre cada día hábil a las 18:30)

## 🔧 Soluciones a problemas comunes

### "No se encontró data.json" en el dashboard

Algunos navegadores (Chrome moderno) bloquean leer archivos locales por seguridad.
Solución más fácil: levantar un servidor local con Python (un comando, sin instalación):

```bash
cd carpeta-donde-estan-los-archivos
python -m http.server 8000
```

Después abrí en el navegador: **http://localhost:8000/dashboard.html**

### Querés ver el dashboard en el celular

Mientras corrés `python -m http.server 8000` en tu PC:
1. Asegurate que tu PC y celular estén en la misma red WiFi
2. Buscá la IP de tu PC (en Windows: `ipconfig`, en Mac/Linux: `ifconfig`)
3. En el celular abrí: `http://TU-IP:8000/dashboard.html`
   (ej: `http://192.168.1.10:8000/dashboard.html`)

### Querés agregar/sacar tickers

Abrí `update_prices.py` con cualquier editor de texto y modificá la lista `TICKERS`:
```python
TICKERS = [
    {"yahoo": "YPFD.BA", "ticker": "YPFD", "name": "YPF"},
    # ... agregá o sacá los que quieras
]
```

## 📋 Próximas fases

- **Fase 2B:** Scraping de noticias de Ámbito, El Cronista, Infobae
- **Fase 2C:** Resumen automático con Claude API
- **Fase 3:** Notificaciones diarias / hosting online
