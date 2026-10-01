#!/usr/bin/env python3
"""Static preview restricted to public site artifacts, not .git/data/credentials.

Bind0.0.0.0 for the proxied Arena preview; all browser asset URLs stay relative.
Used by HTTP/browser QA too. No directory listing and no symlink escapes.
"""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SUFFIXES = {'.html', '.css', '.js', '.svg', '.png', '.tif', '.zip', '.json', '.csv', '.md'}


def public_path(url: str) -> Path | None:
    rel = unquote(urlsplit(url).path).lstrip('/')
    if '\\' in rel or '\x00' in rel:
        return None
    parts = rel.split('/')
    if any(p.startswith('.') or p == '..' for p in parts if p):
        return None
    if not rel or rel == 'docs/' or rel == 'docs':
        rel = 'index.html' if not rel else 'docs/index.html'
    allowed = rel == 'index.html' or rel.startswith('docs/') or rel.startswith('reports/') or rel.startswith('knowledge/')
    requested = ROOT / rel
    candidate = requested.resolve()
    if candidate != requested.absolute():
        return None  # No symlinks, including links into private in-repo data.
    if not allowed or not candidate.is_relative_to(ROOT) or not candidate.is_file() or candidate.suffix not in PUBLIC_SUFFIXES:
        return None
    return candidate


class SiteHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = public_path(path)
        return str(p) if p is not None else str(ROOT / '.nonexistent-public-site-path')

    def list_directory(self, path):
        self.send_error(403, 'Directory listing disabled')
        return None

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-cache')
        p = public_path(self.path)
        if p and p.suffix in ('.tif', '.zip'):
            self.send_header('Content-Disposition', f'attachment; filename="{p.name}"')
        super().end_headers()

    def log_message(self, fmt, *args):
        # Avoid noisy QA logs; CLI logs the listening address once.
        pass


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, default=8080)
    args = ap.parse_args()
    server = ThreadingHTTPServer(('0.0.0.0', args.port), SiteHandler)
    print(f'Site listening on0.0.0.0:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
