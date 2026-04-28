"""
=========================================================
  MercadoAR — notify_discord.py v2
  Manda UN mensaje rico a Discord con todo lo importante:
  resumen, movimientos destacados y noticias clave.
  Solo notifica en los 4 horarios fijos (no en cada update).
=========================================================
"""
 
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
 
# ===== CONFIGURACIÓN =====
DISCORD_WEBHOOK = os.environ.get(
    "DISCORD_WEBHOOK",
    "https://discord.com/api/webhooks/1498658206593978418/koBlfSpV9bk5O4B1c0TwLAfQqJYuSGl9yxatP-NbFpVMUWtsRXUnANWuDA_TzVuiyCyd"
)
 
# Horarios en que SÍ se manda el resumen completo (hora ARG)
NOTIFY_HOURS_ARG = {7, 10, 13, 18}
 
# Umbrales
SCORE_DESTACADO = 62
SCORE_BAJO      = 38
SCORE_FUERTE    = 72
 
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
 
 
def es_horario_notificacion():
    ahora_arg = datetime.now(timezone(timedelta(hours=-3)))
    hora = ahora_arg.hour
    for h in NOTIFY_HOURS_ARG:
        if hora == h:
            return True, h
        if hora == h + 1 and ahora_arg.minute <= 15:
            return True, h
    return False, hora
 
 
def load_json(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
 
 
def send_to_discord(payload):
    import subprocess
    data = json.dumps(payload, ensure_ascii=False)
    cmd = [
        "curl", "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", data,
        DISCORD_WEBHOOK
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        ok = result.returncode == 0
        if not ok:
            print(f"  [DISCORD] curl error: {result.stderr[:200]}")
        return ok
    except Exception as e:
        print(f"  [DISCORD] Error: {e}")
        return False
 
 
def fmt(change):
    return f"{'+' if change >= 0 else ''}{change:.2f}%"
 
def arrow(change):
    return "▲" if change >= 0 else "▼"
 
def em(score):
    if score >= SCORE_FUERTE:          return "🔥"
    if score >= SCORE_DESTACADO:       return "🟢"
    if score <= (100 - SCORE_FUERTE):  return "💀"
    if score <= SCORE_BAJO:            return "🔴"
    return "⚪"
 
HORARIO_NOMBRE = {7: "Apertura", 10: "Media mañana", 13: "Mediodía", 18: "Cierre"}
 
 
def build_mensaje(stocks, summary, news, hora_ref):
    ahora_arg = datetime.now(timezone(timedelta(hours=-3)))
    fecha_str = ahora_arg.strftime("%a %d %b · %H:%Mhs").capitalize()
    nombre    = HORARIO_NOMBRE.get(hora_ref, "Actualización")
 
    isUp    = summary["change"] >= 0
    color   = 0x4ade80 if isUp else 0xf87171
    winners = [s for s in stocks if s["change"] > 0]
    losers  = [s for s in stocks if s["change"] < 0]
    leader  = max(stocks, key=lambda s: s["change"])
    worst   = min(stocks, key=lambda s: s["change"])
 
    # ── Resumen ─────────────────────────────────────────────────
    resumen = "\n".join([
        f"{'📈' if isUp else '📉'} **Promedio:** {fmt(summary['change'])}  |  ✅ {len(winners)} subas · ❌ {len(losers)} bajas",
        f"🏆 **Mejor:** {leader['ticker']} {fmt(leader['change'])}   |   📉 **Peor:** {worst['ticker']} {fmt(worst['change'])}",
    ])
 
    # ── Tabla tickers ───────────────────────────────────────────
    tickers_sorted = sorted(stocks, key=lambda x: x["change"], reverse=True)
    ticker_rows = []
    for s in tickers_sorted:
        score = s.get("score", 50)
        vol   = f" · 🔊{s.get('volume_ratio',1):.1f}x" if s.get("volume_ratio", 1) > 1.5 else ""
        ticker_rows.append(
            f"{em(score)} **{s['ticker']}** {arrow(s['change'])} {fmt(s['change'])}  `{score}/100`{vol}"
        )
 
    # ── Movimientos destacados ───────────────────────────────────
    destacados = sorted(
        [s for s in stocks if s.get("score", 50) >= SCORE_DESTACADO or s.get("score", 50) <= SCORE_BAJO],
        key=lambda s: abs(s.get("score", 50) - 50),
        reverse=True
    )[:4]
 
    dest_rows = []
    for s in destacados:
        score    = s.get("score", 50)
        trend    = s.get("trend_dir", "neutral")
        streak   = s.get("trend_streak", 0)
        vol_r    = s.get("volume_ratio", 1)
        razones  = []
        if abs(s["change"]) > 2:  razones.append(f"movimiento {fmt(s['change'])}")
        if vol_r > 1.5:           razones.append(f"vol {vol_r:.1f}x")
        if streak >= 3:           razones.append(f"{streak}d {'↑' if trend=='up' else '↓'}")
        razon = " · ".join(razones) or s.get("signal","").replace("_"," ")
        dest_rows.append(f"{em(score)} **{s['ticker']}** ({s['name']}) — {razon}")
 
    # ── Noticias ─────────────────────────────────────────────────
    noticias_rows = []
    if news and "news" in news:
        vistas = set()
        # Noticias de tickers destacados primero
        for s in destacados[:3]:
            for n in news["news"].get(s["ticker"], [])[:1]:
                t = n["title"][:88] + ("…" if len(n["title"]) > 88 else "")
                k = t[:40]
                if k not in vistas:
                    noticias_rows.append(f"• **[{s['ticker']}]** {t}")
                    vistas.add(k)
        # Noticias generales
        for n in news["news"].get("GENERAL", [])[:5]:
            t = n["title"][:88] + ("…" if len(n["title"]) > 88 else "")
            k = t[:40]
            if k not in vistas and len(noticias_rows) < 6:
                noticias_rows.append(f"• {t}")
                vistas.add(k)
 
    # ── Armar embed ──────────────────────────────────────────────
    fields = [
        {"name": "📊 Resumen", "value": resumen, "inline": False},
        {"name": "📋 Tickers (mejor → peor)", "value": "\n".join(ticker_rows) or "—", "inline": False},
        {
            "name": "⚡ Movimientos destacados",
            "value": "\n".join(dest_rows) if dest_rows else "✅ Todo dentro del rango normal.",
            "inline": False,
        },
        {
            "name": "📰 Noticias clave",
            "value": "\n".join(noticias_rows) if noticias_rows else "Sin noticias relevantes en las últimas 48hs.",
            "inline": False,
        },
    ]
 
    return {
        "embeds": [{
            "title":  f"{'📈' if isUp else '📉'} MercadoAR — {nombre} · {fecha_str}",
            "color":  color,
            "fields": fields,
            "footer": {"text": "MercadoAR · Yahoo Finance · ~15 min delay"},
        }]
    }
 
 
def main():
    print("\n  [DISCORD] Chequeando horario...")
    notificar, hora_ref = es_horario_notificacion()
    ahora_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M")
 
    if not notificar:
        print(f"  [DISCORD] {ahora_str} ARG — actualización silenciosa, sin mensaje.")
        return True
 
    print(f"  [DISCORD] {ahora_str} ARG — enviando resumen a Discord...")
 
    data = load_json("data.json")
    if not data:
        print("  [DISCORD] ✗ No se encontró data.json")
        return False
 
    news    = load_json("news.json")
    stocks  = data["stocks"]
    summary = data["summary"]
 
    payload = build_mensaje(stocks, summary, news, hora_ref)
    ok = send_to_discord(payload)
    print(f"  [DISCORD] {'✓ Enviado correctamente' if ok else '✗ Falló el envío'}")
    return ok
 
 
if __name__ == "__main__":
    main()
