"""
=========================================================
  MercadoAR — update_bonds.py v1
  Descarga precios de bonos soberanos argentinos
  desde data912.com (API pública, gratis, sin auth).

  Bonos: AL30, GD30 (y otros si se agregan)

  data912.com es usado por tasasargentinas.vercel.app
  y otros proyectos financieros argentinos.
=========================================================

REQUISITOS:
    Sin librerías extra — solo urllib que viene con Python

USO:
    python update_bonds.py
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== Bonos a seguir =====
BONOS = [
    {"ticker": "AL30", "name": "Bonar 2030 (Ley AR)",    "tipo": "Soberano USD"},
    {"ticker": "GD30", "name": "Global 2030 (Ley NY)",   "tipo": "Soberano USD"},
    {"ticker": "AL35", "name": "Bonar 2035",              "tipo": "Soberano USD"},
    {"ticker": "GD35", "name": "Global 2035",             "tipo": "Soberano USD"},
]

# API de data912 — usada por varios proyectos AR de finanzas (gratis, sin auth)
API_URL = "https://data912.com/live/arg_soberanos"


def fetch_bonds():
    """Descarga todos los bonos soberanos desde data912."""
    print(f"  Conectando a data912.com...")
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MercadoAR/1.0)",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            return raw
    except urllib.error.HTTPError as e:
        print(f"  ✗ HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def parse_bond(ticker, name, tipo, raw_data):
    """Extrae los datos de un bono específico del response de data912."""
    # data912 devuelve una lista de objetos con campo "ticker"
    if not raw_data:
        return None

    entry = None
    # Buscar por ticker exacto o con sufijo "D" (dólar)
    for item in raw_data:
        t = item.get("ticker", "").upper()
        if t == ticker.upper() or t == ticker.upper() + "D":
            entry = item
            break

    if not entry:
        print(f"  ✗ {ticker}: no encontrado en data912")
        return None

    try:
        price    = float(entry.get("c", 0) or entry.get("last", 0) or 0)
        prev     = float(entry.get("pc", 0) or entry.get("prev", 0) or price)
        change   = ((price - prev) / prev * 100) if prev > 0 else 0
        volume   = int(entry.get("v", 0) or 0)

        print(f"  ✓ {ticker}... ${price:.2f}  {'+' if change >= 0 else ''}{change:.2f}%")

        return {
            "ticker":   ticker,
            "name":     name,
            "tipo":     tipo,
            "price":    round(price, 4),
            "change":   round(change, 2),
            "volume":   volume,
            "prev":     round(prev, 4),
        }

    except Exception as e:
        print(f"  ✗ {ticker}: error parseando → {e}")
        return None


def main():
    print("\n┌─────────────────────────────────────────┐")
    print("│   MercadoAR — Fetch bonos  v1           │")
    print(f"│   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                 │")
    print("└─────────────────────────────────────────┘\n")
    print("Descargando bonos soberanos desde data912.com...\n")

    raw = fetch_bonds()

    if not raw:
        # Fallback: intentar con Yahoo Finance para AL30D
        print("  data912 no disponible, intentando Yahoo Finance fallback...")
        try:
            import yfinance as yf
            bonds_data = []
            for b in BONOS[:2]:  # Solo AL30 y GD30 tienen ticker en Yahoo a veces
                try:
                    t = yf.Ticker(f"{b['ticker']}D.BA")
                    hist = t.history(period="5d")
                    if not hist.empty:
                        price  = float(hist["Close"].iloc[-1])
                        prev   = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
                        change = ((price - prev) / prev * 100) if prev > 0 else 0
                        bonds_data.append({
                            "ticker": b["ticker"], "name": b["name"],
                            "tipo": b["tipo"], "price": round(price, 4),
                            "change": round(change, 2), "volume": 0, "prev": round(prev, 4),
                        })
                        print(f"  ✓ {b['ticker']} (Yahoo fallback): ${price:.2f}  {change:+.2f}%")
                except Exception:
                    pass
            if bonds_data:
                save(bonds_data)
                return
        except ImportError:
            pass
        print("  ✗ No se pudo obtener datos de bonos.")
        return

    # Parsear cada bono
    bonds_data = []
    for b in BONOS:
        result = parse_bond(b["ticker"], b["name"], b["tipo"], raw)
        if result:
            bonds_data.append(result)

    if not bonds_data:
        print("\n✗ No se obtuvo ningún dato de bonos.")
        return

    save(bonds_data)


def save(bonds_data):
    output = {
        "updated_at":  datetime.now().isoformat(),
        "updated_str": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "source":      "data912.com",
        "bonds":       bonds_data,
    }

    path = os.path.join(SCRIPT_DIR, "bonds.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(bonds_data)} bonos guardados → bonds.json")
    for b in bonds_data:
        print(f"  {b['ticker']}: ${b['price']:.2f}  {b['change']:+.2f}%")
    print()


if __name__ == "__main__":
    main()
