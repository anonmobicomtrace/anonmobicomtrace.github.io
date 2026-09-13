# -*- coding: utf-8 -*-
"""Static server with HTTP Range support, so video scrubbing works locally.

python -m http.server has no Range support: the browser cannot seek in a video
until the whole file is buffered, which looks exactly like a broken progress bar.
"""
import os, re, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404)
            return None
        size = os.fstat(f.fileno()).st_size
        start, end = m.group(1), m.group(2)
        start = int(start) if start else max(0, size - int(end))
        end = int(end) if end and start != 0 or (end and start == 0 and m.group(1)) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416)
            f.close()
            return None
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        f.seek(start)
        self._range_left = end - start + 1
        return _Limited(f, self._range_left)


class _Limited:
    def __init__(self, f, n):
        self.f, self.n = f, n

    def read(self, size=-1):
        if self.n <= 0:
            return b""
        if size is None or size < 0:
            size = self.n
        data = self.f.read(min(size, self.n))
        self.n -= len(data)
        return data

    def close(self):
        self.f.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    ThreadingHTTPServer(("127.0.0.1", port), RangeHandler).serve_forever()
