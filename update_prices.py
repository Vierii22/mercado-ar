"""
=========================================================
  MercadoAR — update_prices.py v2
  Descarga precios + 20 días de historial desde Yahoo Finance.
  Calcula tendencia, media móvil, momentum y señal de auge.
=========================================================

REQUISITOS:
    pip install yfinance

USO:
    python update_prices.py
"""

import yfinance as yf
import json
from datetime import datetime
import os

TICKERS = [
    {"yahoo": "YPFD.BA",  "ticker": "YPFD",  "name": "YPF"},
    {"yahoo": "GGAL.BA",  "ticker": "GGAL",  "name": "Galicia"},
    {"yahoo": "PAMP.BA",  "ticker": "PAMP",  "name": "Pampa Energía"},
    {"yahoo": "BMA.BA",   "ticker": "BMA",   "name": "Banco Macro"},
    {"yahoo": "TXAR.BA",  "ticker": "TXAR",  "name": "Ternium AR"},
    {"yahoo": "ALUA.BA",  "ticker": "ALUA",  "name": "Aluar"},
    {"yahoo": "TECO2.BA", "ticker": "TECO2", "name": "Telecom AR"},
    {"yahoo": "CEPU.BA",  "ticker": "CEPU",  "name": "Central Puerto"},
    {"yahoo": "AL30.BA",  "ticker": "AL30",  "name": "Bonar 2030"},
]

# ===== Umbrales de detección =====
THRESHOLDS = {
    "change_hot":       3.0,   # % variación diaria para marcar hot
    "change_cold":     -3.0,   # % caída diaria para marcar cold
    "volume_hot":       1.8,   # ratio volumen vs promedio
    "trend_days":       5,     # días consecutivos para confirmar tendencia
    "ma_short":         5,     # media móvil corta (días)
    "ma_long":          20,    # media móvil larga (días)
}


def calc_moving_average(prices, n):
    if len(prices) < n:
        return None
    return sum(prices[-n:]) / n


def calc_trend(prices, n=5):
    """
    Calcula tendencia de los últimos n días.
    Devuelve: 'up' | 'down' | 'neutral'
    y la racha consecutiva de días subiendo o bajando.
    """
    if len(prices) < n + 1:
        return "neutral", 0
    recent = prices[-(n+1):]
    ups = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
    downs = sum(1 for i in range(1, len(recent)) if recent[i] < recent[i-1])
    if ups >= n - 1:
        return "up", ups
    elif downs >= n - 1:
        return "down", downs
    return "neutral", 0


def calc_momentum_score(change, volume_ratio, trend, ma_cross):
    """
    Score de 0-100. La variación diaria es el factor dominante.
    Tendencia y MA son confirmadores secundarios.

    Ejemplos esperados:
      +5% variación + tendencia up + vol alto  → ~90
      +1.5% variación + tendencia up           → ~65
      -0.1% variación + tendencia down         → ~35
      -4% variación + vol alto                 → ~15
    """
    score = 50  # base neutral

    # Factor 1: Variación diaria — dominante (hasta ±35 pts)
    # ±5% → ±35 | ±3% → ±21 | ±1% → ±7
    score += max(-35, min(35, change * 7))

    # Factor 2: Volumen anormal — solo suma (hasta +10 pts)
    if volume_ratio > 1.5:
        score += min((volume_ratio - 1.0) * 6, 10)

    # Factor 3: Tendencia 5 días — confirmador (±10 pts)
    if trend == "up":
        score += 10
    elif trend == "down":
        score -= 10

    # Factor 4: Cruce MA5/MA20 — confirmador leve (±5 pts)
    score += ma_cross * 5

    return max(0, min(100, round(score)))


def get_signal(score, change):
    """
    Convierte score en señal legible.
    """
    if score >= 70:
        return "fuerte_suba" if change >= 0 else "fuerte_baja"
    elif score >= 55:
        return "suba" if change >= 0 else "baja"
    elif score <= 30:
        return "fuerte_baja" if change < 0 else "fuerte_suba"
    elif score <= 45:
        return "baja" if change < 0 else "suba"
    return "neutral"


def fetch_ticker(yahoo_symbol, ticker_label, name):
    print(f"  → {ticker_label}...", end=" ", flush=True)
    try:
        t = yf.Ticker(yahoo_symbol)
        hist = t.history(period="30d")  # 30d para asegurar 20 ruedas hábiles

        if hist.empty or len(hist) < 3:
            print("✗ sin datos")
            return None

        closes = [float(p) for p in hist["Close"].tolist()]
        volumes = [int(v) for v in hist["Volume"].tolist()]

        last_price  = closes[-1]
        prev_price  = closes[-2]
        change_pct  = ((last_price - prev_price) / prev_price) * 100

        last_volume = volumes[-1]
        avg_volume  = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else last_volume
        volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1.0

        # Medias móviles
        ma5  = calc_moving_average(closes, THRESHOLDS["ma_short"])
        ma20 = calc_moving_average(closes, THRESHOLDS["ma_long"])

        ma_cross = 0
        if ma5 and ma20:
            # +1 si ma5 > ma20 (tendencia alcista), -1 si ma5 < ma20 (bajista)
            ma_cross = 1 if ma5 > ma20 else -1

        # Tendencia últimos 5 días
        trend, streak = calc_trend(closes, THRESHOLDS["trend_days"])

        # Score y señal
        score   = calc_momentum_score(change_pct, volume_ratio, trend, ma_cross)
        signal  = get_signal(score, change_pct)

        # Hot/cold para compatibilidad con dashboard
        is_hot  = score >= 65 and change_pct > 0
        is_cold = score <= 35 and change_pct < 0

        # Sparkline: últimos 10 cierres (para el mini gráfico)
        trend_spark = [round(float(p), 2) for p in closes[-10:]]

        print(f"✓ ${last_price:,.2f}  {change_pct:+.2f}%  score={score}  señal={signal}")

        return {
            "ticker":        ticker_label,
            "name":          name,
            "price":         round(last_price, 2),
            "change":        round(change_pct, 2),
            "volume":        last_volume,
            "volume_ratio":  round(volume_ratio, 2),
            "hot":           is_hot,
            "cold":          is_cold,
            "trend":         trend_spark,
            "trend_dir":     trend,
            "trend_streak":  streak,
            "ma5":           round(ma5, 2) if ma5 else None,
            "ma20":          round(ma20, 2) if ma20 else None,
            "ma_cross":      ma_cross,
            "score":         score,
            "signal":        signal,
        }

    except Exception as e:
        print(f"✗ error: {e}")
        return None


def calc_summary(stocks):
    valid = [s for s in stocks if s]
    if not valid:
        return {"change": 0, "leader": "—", "leader_change": 0,
                "worst": "—", "worst_change": 0}
    avg_change  = sum(s["change"] for s in valid) / len(valid)
    leader      = max(valid, key=lambda s: s["change"])
    worst       = min(valid, key=lambda s: s["change"])
    hot_count   = sum(1 for s in valid if s["hot"])
    cold_count  = sum(1 for s in valid if s["cold"])
    return {
        "change":        round(avg_change, 2),
        "leader":        leader["ticker"],
        "leader_change": leader["change"],
        "worst":         worst["ticker"],
        "worst_change":  worst["change"],
        "hot_count":     hot_count,
        "cold_count":    cold_count,
    }


def main():
    print("\n┌─────────────────────────────────────────┐")
    print("│   MercadoAR — Fetch precios  v2         │")
    print(f"│   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                 │")
    print("└─────────────────────────────────────────┘\n")
    print(f"Descargando {len(TICKERS)} tickers (30d historial)...\n")

    stocks_data = []
    for t in TICKERS:
        result = fetch_ticker(t["yahoo"], t["ticker"], t["name"])
        if result:
            stocks_data.append(result)

    if not stocks_data:
        print("\n✗ No se obtuvo ningún dato. Revisá tu conexión.")
        return

    summary = calc_summary(stocks_data)

    output = {
        "updated_at":  datetime.now().isoformat(),
        "updated_str": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "summary":     summary,
        "stocks":      stocks_data,
    }

    script_dir  = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(stocks_data)} tickers guardados → {output_path}")
    print(f"  Promedio: {summary['change']:+.2f}%")
    print(f"  Líder:    {summary['leader']} ({summary['leader_change']:+.2f}%)")
    print(f"  Peor:     {summary['worst']} ({summary['worst_change']:+.2f}%)")
    print(f"  🟢 Hot: {summary['hot_count']}   🔴 Cold: {summary['cold_count']}\n")


if __name__ == "__main__":
    main()
