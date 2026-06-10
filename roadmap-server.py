"""
Servidor mínimo para el Roadmap de Inteliaudit.
Persiste el estado en roadmap-state.json.

Uso:  python roadmap-server.py
      (abre automáticamente http://localhost:4900)
"""
import http.server
import json
import os
import sys
import webbrowser
from pathlib import Path

PORT = 4900
ROOT = Path(__file__).parent
STATE_FILE = ROOT / "roadmap-state.json"
ROADMAP_HTML = ROOT / "ROADMAP.html"


class RoadmapHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/roadmap":
            self._serve_file(ROADMAP_HTML, "text/html")
        elif self.path == "/api/roadmap-state":
            self._serve_json_state()
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path == "/api/roadmap-state":
            self._save_json_state()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _serve_file(self, path, content_type):
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _serve_json_state(self):
        if STATE_FILE.exists():
            data = STATE_FILE.read_bytes()
        else:
            data = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _save_json_state(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            state = json.loads(body)
            STATE_FILE.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            response = b'{"ok":true}'
            self.send_response(200)
        except (json.JSONDecodeError, Exception) as e:
            response = json.dumps({"error": str(e)}).encode()
            self.send_response(400)

        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(response)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        if "/api/roadmap-state" in str(args[0]):
            return  # silenciar los saves automáticos
        super().log_message(format, *args)


if __name__ == "__main__":
    os.chdir(ROOT)
    server = http.server.HTTPServer(("0.0.0.0", PORT), RoadmapHandler)
    url = f"http://localhost:{PORT}"
    print(f"\n  Inteliaudit Roadmap")
    print(f"  -------------------")
    print(f"  Servidor:  {url}")
    print(f"  Estado:    {STATE_FILE}")
    print(f"  Ctrl+C para detener\n")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()
