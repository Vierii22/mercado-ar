"""
=========================================================
  MercadoAR — notify_discord.py
  Lee data.json y news.json y manda resumen diario +
  alertas de movimientos anormales a Discord via webhook.
=========================================================

USO (manual):
    python notify_discord.py

Se llama automáticamente desde server.py cada vez que
apretás "Refrescar" en el dashboard.

NO requiere librerías extra — usa urllib que viene con Python.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime

# ===== CONFIGURACIÓN =====
import os
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1498658206593978418/koBlfSpV9bk5O4B1c0TwLAfQqJYuSGl9yxatP-NbFpVMUWtsRXUnANWuDA_TzVuiyCyd")

# Umbrales para decidir si mandar alerta
SCORE_ALERTA_SUBA  = 65   # score >= este valor → alerta alcista
SCORE_ALERTA_BAJA  = 35   # score <= este valor → alerta bajista
SCORE_FUERTE       = 75   # score fuera de este rango → emoji de fuego

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ===== Emojis y helpers =====
def emoji_signal(signal, score):
    if signal == "fuerte_suba":  return "🔥" if score >= SCORE_FUERTE else "🟢"
    if signal == "suba":         return "🟢"
    if signal == "neutral":      return "⚪"
    if signal == "baja":         return "🔴"
    if signal == "fuerte_baja":  return "🔥" if score <= (100 - SCORE_FUERTE) else "🔴"
    return "⚪"

def arrow(change):
    return "▲" if change >= 0 else "▼"

def fmt_change(change):
    return f"{'+' if change >= 0 else ''}{change:.2f}%"

def trend_emoji(trend_dir):
    return {"up": "📈", "down": "📉", "neutral": "➡️"}.get(trend_dir, "➡️")


def send_to_discord(payload):
    """Manda un payload JSON al webhook de Discord."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ✗ Discord HTTP {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"  ✗ Discord error: {e}")
        return False


def load_json(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_resumen_embed(stocks, summary, updated_str):
    """Embed principal con resumen de la cartera."""
    isUp = summary["change"] >= 0
    color = 0x4ade80 if isUp else 0xf87171  # verde o rojo

    winners = [s for s in stocks if s["change"] > 0]
    losers  = [s for s in stocks if s["change"] < 0]
    leader  = max(stocks, key=lambda s: s["change"])
    worst   = min(stocks, key=lambda s: s["change"])

    # Tabla de tickers
    rows = []
    for s in stocks:
        em = emoji_signal(s.get("signal", "neutral"), s.get("score", 50))
        rows.append(
            f"{em} **{s['ticker']}** {arrow(s['change'])} {fmt_change(s['change'])}"
            f"  •  score `{s.get('score', '?')}`"
        )

    desc = "\n".join(rows)

    fields = [
        {"name": "📊 Promedio cartera", "value": fmt_change(summary["change"]), "inline": True},
        {"name": "🏆 Líder",            "value": f"{leader['ticker']} {fmt_change(leader['change'])}", "inline": True},
        {"name": "📉 Peor",             "value": f"{worst['ticker']} {fmt_change(worst['change'])}", "inline": True},
        {"name": "✅ Subas / ❌ Bajas", "value": f"{len(winners)} subas · {len(losers)} bajas", "inline": True},
    ]

    return {
        "title": f"{'📈' if isUp else '📉'} Resumen de cartera — {updated_str}",
        "description": desc,
        "color": color,
        "fields": fields,
        "footer": {"text": "MercadoAR · Yahoo Finance · ~15 min delay"},
    }


def build_alerta_embed(stock, news_items):
    """Embed de alerta para un ticker con movimiento anormal."""
    signal  = stock.get("signal", "neutral")
    score   = stock.get("score", 50)
    isUp    = score >= 50
    color   = 0x4ade80 if isUp else 0xf87171
    if score >= SCORE_FUERTE or score <= (100 - SCORE_FUERTE):
        color = 0xd4ff3a  # amarillo brillante para señales fuertes

    em = emoji_signal(signal, score)

    title = f"{em} ALERTA: {stock['ticker']} ({stock['name']})"

    lines = [
        f"**Precio:** ${stock['price']:,.2f}",
        f"**Variación:** {arrow(stock['change'])} {fmt_change(stock['change'])}",
        f"**Score:** {score}/100 — {signal.replace('_', ' ').upper()}",
        f"**Volumen:** {stock.get('volume_ratio', 1):.1f}x promedio",
        f"**Tendencia:** {trend_emoji(stock.get('trend_dir', 'neutral'))} {stock.get('trend_dir', 'neutral').upper()} ({stock.get('trend_streak', 0)} días)",
    ]

    if stock.get("ma5") and stock.get("ma20"):
        ma_gap = ((stock["ma5"] - stock["ma20"]) / stock["ma20"]) * 100
        lines.append(f"**MA5 vs MA20:** {'+' if ma_gap >= 0 else ''}{ma_gap:.1f}%")

    desc = "\n".join(lines)

    fields = []
    if news_items:
        top3 = news_items[:3]
        noticias_text = "\n".join(
            f"• [{n['source']} {n.get('time','')}] {n['title'][:80]}{'...' if len(n['title'])>80 else ''}"
            for n in top3
        )
        fields.append({"name": "📰 Noticias relacionadas", "value": noticias_text, "inline": False})

    return {
        "title": title,
        "description": desc,
        "color": color,
        "fields": fields,
        "footer": {"text": f"MercadoAR · {datetime.now().strftime('%d/%m/%Y %H:%M')}"},
    }


def main():
    print("\n  [DISCORD] Preparando notificaciones...")

    data = load_json("data.json")
    if not data:
        print("  [DISCORD] ✗ No se encontró data.json")
        return False

    news = load_json("news.json")
    stocks   = data["stocks"]
    summary  = data["summary"]
    updated  = data.get("updated_str", datetime.now().strftime("%d/%m/%Y %H:%M"))

    # ===== Mensaje 1: Resumen general =====
    resumen_embed = build_resumen_embed(stocks, summary, updated)
    ok = send_to_discord({"embeds": [resumen_embed]})
    print(f"  [DISCORD] Resumen: {'✓ enviado' if ok else '✗ falló'}")

    # ===== Mensajes 2+: Alertas por ticker anormal =====
    alertas = [
        s for s in stocks
        if s.get("score", 50) >= SCORE_ALERTA_SUBA or s.get("score", 50) <= SCORE_ALERTA_BAJA
    ]

    if not alertas:
        ok2 = send_to_discord({"content": "✅ Sin movimientos anormales detectados hoy. Cartera dentro del rango habitual."})
        print("  [DISCORD] Sin alertas: ✓ enviado")
    else:
        print(f"  [DISCORD] {len(alertas)} alerta(s) para enviar...")
        for s in alertas:
            ticker_news = []
            if news and "news" in news:
                ticker_news = news["news"].get(s["ticker"], [])
            alerta_embed = build_alerta_embed(s, ticker_news)
            ok2 = send_to_discord({"embeds": [alerta_embed]})
            print(f"  [DISCORD] Alerta {s['ticker']}: {'✓ enviado' if ok2 else '✗ falló'}")

    print("  [DISCORD] Listo.\n")
    return True


if __name__ == "__main__":
    main()
