"""Probe the camera HTTP surface without printing credentials or raw bodies.

Writes findings to .runtime/verify/http_probe.json and prints only safe summaries.
"""
import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

HOST = "192.168.0.15"
USER = "admin"
PASSWORD = "admin"

OUT = Path(".runtime/verify")
OUT.mkdir(parents=True, exist_ok=True)


def fetch(path, timeout=6):
    url = f"http://{HOST}{path}"
    request = urllib.request.Request(url)
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096)
            return {
                "path": path,
                "status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "server": response.headers.get("Server"),
                "www_authenticate": response.headers.get("WWW-Authenticate"),
                "bytes_read": len(body),
                "starts_with_jpeg": body[:2] == b"\xff\xd8",
                "body_preview": body[:200].decode("utf-8", "replace") if "text" in (response.headers.get("Content-Type") or "") or "json" in (response.headers.get("Content-Type") or "") else None,
            }
    except urllib.error.HTTPError as exc:
        return {"path": path, "status": exc.code, "reason": exc.reason,
                "www_authenticate": exc.headers.get("WWW-Authenticate") if exc.headers else None}
    except Exception as exc:
        return {"path": path, "error": type(exc).__name__}


results = []
for probe_path in ["/", "/cgi-bin/magicBox.cgi?action=getDeviceType",
                   "/cgi-bin/magicBox.cgi?action=getSystemInfo",
                   "/cgi-bin/snapshot.cgi", "/snapshot.jpg", "/image.jpg"]:
    result = fetch(probe_path)
    results.append(result)
    print(json.dumps({k: v for k, v in result.items() if k != "body_preview"}, ensure_ascii=False))
    if result.get("body_preview"):
        print("   preview:", result["body_preview"][:120].replace("\r\n", " | "))

(OUT / "http_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
