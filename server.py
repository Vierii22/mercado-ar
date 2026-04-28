"""
=========================================================
  MercadoAR — server.py
  Servidor local que sirve el dashboard y permite refrescar
  precios y noticias on-demand desde el botón del dashboard.
=========================================================

USO:
    python server.py

Después abrí en el navegador:
    http://localhost:8000

Mantené esta ventana abierta mientras uses el dashboard.
Para cerrar el servidor: Ctrl+C en esta ventana.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import subprocess
import sys
import os
from datetime import datetime
import threading

PORT = 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script_name):
    """Corre un script Python y devuelve (success, stdout, stderr)."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    try:
        # En Windows el subprocess hereda CP-1252 que rompe con caracteres como ✓ →
        # Forzamos UTF-8 vía variables de entorno + io encoding
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        result = subprocess.run(
            [sys.executable, "-X", "utf8", script_path],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout: el script tardó más de 2 minutos"
    except Exception as e:
        return False, "", str(e)


def run_discord_notify():
    """Llama a notify_discord.py en background después de cada refresh exitoso."""
    script_path = os.path.join(SCRIPT_DIR, "notify_discord.py")
    if not os.path.exists(script_path):
        print("  [DISCORD] notify_discord.py no encontrado, saltando...")
        return
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", script_path],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.returncode != 0 and result.stderr:
            print(f"  [DISCORD] Error: {result.stderr[:200]}")
    except Exception as e:
        print(f"  [DISCORD] Excepción: {e}")


class DashboardHandler(SimpleHTTPRequestHandler):
    """Handler que sirve archivos + endpoint /refresh."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def log_message(self, format, *args):
        """Logs más limpios."""
        sys.stderr.write(f"  [{datetime.now().strftime('%H:%M:%S')}] {format % args}\n")

    def do_GET(self):
        # Endpoint de refresh
        if self.path.startswith("/refresh"):
            self.handle_refresh()
            return

        # Endpoint de status (chequeo de salud)
        if self.path == "/status":
            self.send_json({"status": "ok", "time": datetime.now().isoformat()})
            return

        # Redirect raíz al dashboard
        if self.path == "/" or self.path == "":
            self.send_response(302)
            self.send_header("Location", "/dashboard.html")
            self.end_headers()
            return

        # Resto: archivos estáticos
        super().do_GET()

    def handle_refresh(self):
        """Corre los 2 scripts y devuelve resultado."""
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        refresh_type = qs.get("type", ["all"])[0]

        results = {
            "started_at": datetime.now().isoformat(),
            "prices": None,
            "news": None,
        }

        if refresh_type in ("all", "prices"):
            print(f"\n  [REFRESH] Actualizando precios...")
            ok, stdout, stderr = run_script("update_prices.py")
            if not ok:
                print(f"  [REFRESH] ✗ Precios falló:")
                print(f"     stderr: {stderr[:300]}")
                print(f"     stdout: {stdout[:300]}")
            else:
                print(f"  [REFRESH] ✓ Precios OK")
            results["prices"] = {
                "success": ok,
                "summary": extract_summary(stdout) if ok else (stderr[-500:] or stdout[-500:]),
            }

        if refresh_type in ("all", "news"):
            print(f"  [REFRESH] Actualizando noticias...")
            ok, stdout, stderr = run_script("update_news.py")
            if not ok:
                print(f"  [REFRESH] ✗ Noticias falló:")
                print(f"     stderr: {stderr[:300]}")
                print(f"     stdout: {stdout[:300]}")
            else:
                print(f"  [REFRESH] ✓ Noticias OK")
            results["news"] = {
                "success": ok,
                "summary": extract_summary(stdout) if ok else (stderr[-500:] or stdout[-500:]),
            }

        results["finished_at"] = datetime.now().isoformat()
        self.send_json(results)

        # Mandar notificaciones a Discord en background (no bloquea el dashboard)
        if results.get("prices", {}) and results["prices"].get("success"):
            t = threading.Thread(target=run_discord_notify, daemon=True)
            t.start()

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def extract_summary(stdout):
    """Saca las líneas relevantes del output de los scripts para mostrar."""
    lines = stdout.strip().split("\n")
    important = [l for l in lines if "✓" in l or "✗" in l or "Promedio:" in l or "Líder:" in l or "GENERAL:" in l]
    return "\n".join(important[-15:]) if important else stdout[-500:]


def main():
    print("\n┌─────────────────────────────────────────────┐")
    print("│   MercadoAR — Servidor local                │")
    print(f"│   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                     │")
    print("└─────────────────────────────────────────────┘\n")

    print(f"📁 Carpeta: {SCRIPT_DIR}")
    print(f"🌐 Servidor en: http://localhost:{PORT}")
    print(f"📊 Dashboard:   http://localhost:{PORT}/dashboard.html\n")
    print("✓ Endpoint /refresh listo para el botón del dashboard")
    print("✓ Para detener el servidor: Ctrl+C\n")
    print("─" * 47)

    # Verificar que existan los scripts
    for script in ("update_prices.py", "update_news.py", "dashboard.html"):
        path = os.path.join(SCRIPT_DIR, script)
        marker = "✓" if os.path.exists(path) else "✗"
        print(f"  {marker} {script}")
    print("─" * 47 + "\n")

    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Servidor detenido. ¡Hasta la próxima!")
        server.server_close()


if __name__ == "__main__":
    main()
