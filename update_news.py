"""
=========================================================
  MercadoAR — update_news.py v3
  Descarga noticias de 7 fuentes RSS:
  Ámbito, El Cronista, Infobae, El Economista,
  iProfesional, Bloomberg Línea AR, Ámbito Mercados.
 
  Cambios v3:
  - 4 fuentes nuevas agregadas
=========================================================
 
REQUISITOS (instalar 1 sola vez):
    pip install feedparser
 
USO:
    python update_news.py
"""
 
import feedparser
import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
import os
 
# ===== FUENTES RSS =====
SOURCES = [
    # ── Fuentes originales ──────────────────────────────────────
    {
        "name": "Ámbito",
        "url": "https://www.ambito.com/rss/pages/finanzas.xml",
        "fallback_url": "https://www.ambito.com/rss/pages/economia.xml",
    },
    {
        "name": "El Cronista",
        "url": "https://www.cronista.com/files/rss/finanzas-y-mercados.xml",
        "fallback_url": "https://www.cronista.com/files/rss/economia-politica.xml",
    },
    {
        "name": "Infobae Economía",
        "url": "https://www.infobae.com/feeds/rss/economia/",
        "fallback_url": "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
    },
    # ── Fuentes nuevas ──────────────────────────────────────────
    {
        "name": "El Economista",
        "url": "https://eleconomista.com.ar/finanzas/feed/",
        "fallback_url": "https://eleconomista.com.ar/economia/feed/",
    },
    {
        "name": "iProfesional",
        "url": "https://www.iprofesional.com/rss/home.xml",
        "fallback_url": "https://www.iprofesional.com/rss/economia.xml",
    },
    {
        "name": "Bloomberg Línea AR",
        "url": "https://www.bloomberglinea.com/arc/outboundfeeds/rss/category/argentina/?outputType=xml",
        "fallback_url": "https://www.bloomberglinea.com/arc/outboundfeeds/rss/?outputType=xml",
    },
    {
        "name": "Ámbito Mercados",
        "url": "https://www.ambito.com/rss/pages/mercados.xml",
        "fallback_url": "https://www.ambito.com/rss/pages/economia.xml",
    },
    {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/api/sa/combined_feeds.xml?mode=xml&limit=100",
        "fallback_url": "https://seekingalpha.com/market-news/stocks.xml",
    },
]
 
# ===== TICKERS Y PALABRAS CLAVE =====
# "exact": palabras que tienen que matchear con bordes de palabra (\b)
#          Útil para siglas cortas que pueden ser parte de otra palabra
# "loose": frases que pueden aparecer en cualquier parte del texto
TICKERS_KEYWORDS = {
    "YPFD": {
        "name": "YPF",
        "exact": ["ypf", "ypfd"],
        "loose": ["vaca muerta", "petrolera estatal", "yacimientos petrolíferos",
                  "horacio marín", "horacio marin"],
    },
    "GGAL": {
        "name": "Galicia",
        "exact": ["galicia", "ggal"],
        "loose": ["grupo galicia", "banco galicia", "banco de galicia"],
    },
    "PAMP": {
        "name": "Pampa Energía",
        "exact": ["pampa", "pamp", "tgs", "paen"],
        "loose": ["pampa energía", "pampa energia", "pampa holding",
                  "transportadora gas del sur", "marcelo mindlin"],
    },
    "BMA": {
        "name": "Banco Macro",
        "exact": ["macro", "bma"],
        "loose": ["banco macro", "macro bansud", "jorge brito"],
    },
    "TXAR": {
        "name": "Ternium AR",
        "exact": ["ternium", "siderar", "txar", "techint"],
        "loose": ["paolo rocca", "industria siderúrgica", "industria siderurgica",
                  "acero argentino"],
    },
    "ALUA": {
        "name": "Aluar",
        "exact": ["aluar", "alua"],
        "loose": ["javier madanes", "industria del aluminio"],
    },
    "TECO2": {
        "name": "Telecom AR",
        "exact": ["telecom", "teco2", "personal", "cablevisión", "cablevision", "flow"],
        "loose": ["telecom argentina", "marcelo rivas", "héctor magnetto"],
    },
    "CEPU": {
        "name": "Central Puerto",
        "exact": ["cepu"],
        "loose": ["central puerto", "generación eléctrica", "generacion electrica"],
    },
}
 
# Keywords para clasificar como noticia general del mercado argentino
GENERAL_KEYWORDS = [
    # Mercado
    "merval", "byma", "rofex", "matba", "bolsa", "acciones",
    # Bancos / Política monetaria
    "bcra", "central de la república", "central de la republica",
    "banco central", "tasa de política", "tasa de politica",
    # Cambiario
    "dólar", "dolar", "blue", "ccl", "mep", "contado con liqui",
    "tipo de cambio", "brecha cambiaria",
    # Renta fija
    "bonos", "riesgo país", "riesgo pais", "deuda", "letras",
    "al30", "gd30", "lecap", "boncer",
    # Macro
    "tasas", "inflación", "inflacion", "ipc", "indec",
    "fmi", "deuda externa", "actividad económica", "actividad economica",
    "ministerio de economía", "ministerio de economia",
    "caputo", "milei", "sturzenegger",
    # General
    "mercado argentino", "acciones argentinas", "bolsa argentina",
    "wall street", "panel líder", "panel lider", "adrs",
]
 
 
def clean_text(text):
    """Limpia HTML y entidades de los textos del RSS."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
 
 
def parse_date(entry):
    """Parsea la fecha de una entrada de RSS de forma robusta."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(field)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                for fmt in ("%a, %d %b %Y %H:%M:%S %z",
                            "%a, %d %b %Y %H:%M:%S GMT",
                            "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        dt = datetime.strptime(val, fmt)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except ValueError:
                        continue
            except Exception:
                pass
    return None
 
 
def match_tickers(title, summary):
    """Detecta qué tickers matchean. Combina exact (bordes de palabra) y loose (substring)."""
    text = (title + " " + summary).lower()
    matched = set()
 
    for ticker, info in TICKERS_KEYWORDS.items():
        # Exact: requiere bordes de palabra para evitar falsos positivos
        for kw in info.get("exact", []):
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, text):
                matched.add(ticker)
                break
        if ticker in matched:
            continue
        # Loose: substring simple (frases largas, falsos positivos improbables)
        for kw in info.get("loose", []):
            if kw.lower() in text:
                matched.add(ticker)
                break
 
    return list(matched)
 
 
def matches_general(title, summary):
    """Detecta si la noticia es de interés general del mercado AR."""
    text = (title + " " + summary).lower()
    for kw in GENERAL_KEYWORDS:
        if kw in text:
            return True
    return False
 
 
def fetch_source(source):
    """Trae las noticias de un feed RSS."""
    print(f"\n  → {source['name']}...", end=" ", flush=True)
    feed = feedparser.parse(source["url"])
    if (not feed.entries or feed.bozo) and source.get("fallback_url"):
        feed = feedparser.parse(source["fallback_url"])
    if not feed.entries:
        print("✗ sin entradas")
        return []
    print(f"✓ {len(feed.entries)} noticias")
    return feed.entries
 
 
def process_entries(entries, source_name, cutoff_date):
    """Procesa entradas del RSS, filtra por fecha y limpia."""
    processed = []
    skipped_old = 0
    for entry in entries:
        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
        link = entry.get("link", "")
 
        if not title:
            continue
 
        pub_date = parse_date(entry)
        if pub_date and pub_date < cutoff_date:
            skipped_old += 1
            continue
 
        if len(summary) > 280:
            summary = summary[:277] + "..."
 
        time_str = pub_date.astimezone(
            timezone(timedelta(hours=-3))
        ).strftime("%d/%m %H:%M") if pub_date else ""
 
        processed.append({
            "title": title,
            "summary": summary,
            "link": link,
            "source": source_name,
            "time": time_str,
            "iso_date": pub_date.isoformat() if pub_date else None,
            "tickers": match_tickers(title, summary),
            "is_general": matches_general(title, summary),
        })
    return processed, skipped_old
 
 
def organize_by_ticker(news):
    """Organiza el output: news[ticker] = [lista de noticias]."""
    result = {"GENERAL": []}
    for ticker in TICKERS_KEYWORDS:
        result[ticker] = []
 
    # Por ticker primero
    seen_in_general = set()
    for n in news:
        for ticker in n["tickers"]:
            if ticker in result:
                result[ticker].append(n)
 
    # General: noticias con keyword macro O cualquier noticia con ticker matched
    # (porque si menciona un ticker, también es relevante para el panorama general)
    for n in news:
        key = n["title"]  # dedupe simple
        if key in seen_in_general:
            continue
        if n["is_general"] or n["tickers"]:
            result["GENERAL"].append(n)
            seen_in_general.add(key)
 
    # Ordenar por fecha más reciente y limitar a 30 por sección
    for ticker in result:
        result[ticker].sort(key=lambda n: n["iso_date"] or "", reverse=True)
        result[ticker] = result[ticker][:30]
 
    return result
 
 
def main():
    print("\n┌─────────────────────────────────────────┐")
    print("│   MercadoAR — Fetch noticias  v2        │")
    print(f"│   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                 │")
    print("└─────────────────────────────────────────┘")
 
    # FIX: usar timezone aware desde el principio para evitar problemas de TZ
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=48)
 
    print(f"\nAhora (UTC):     {now_utc.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cutoff (UTC):    {cutoff.strftime('%Y-%m-%d %H:%M')}  (48hs atrás)")
 
    all_news = []
    for source in SOURCES:
        entries = fetch_source(source)
        processed, skipped = process_entries(entries, source["name"], cutoff)
        all_news.extend(processed)
        print(f"     {len(processed)} dentro del rango  ({skipped} más antiguas descartadas)")
 
    print(f"\nTotal noticias en rango: {len(all_news)}")
 
    organized = organize_by_ticker(all_news)
 
    print("\nNoticias por sección:")
    print(f"  GENERAL: {len(organized['GENERAL'])}")
    for ticker in TICKERS_KEYWORDS:
        count = len(organized[ticker])
        marker = "✓" if count > 0 else "—"
        print(f"  {marker} {ticker}: {count}")
 
    output = {
        "updated_at": datetime.now().isoformat(),
        "updated_str": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "cutoff_hours": 48,
        "total_news": len(all_news),
        "news": organized,
    }
 
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
 
    print(f"\n✓ Guardado en: {output_path}")
    print("Refrescá el dashboard (Ctrl+F5) para ver las noticias.\n")
 
 
if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
