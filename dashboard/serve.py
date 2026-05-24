#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Lightweight dev server that serves the dashboard and proxies Devin API
requests to bypass CORS restrictions."""

from __future__ import annotations

import http.server
import os
import urllib.error
import urllib.request

PORT = int(os.environ.get("PORT", "8080"))
DEVIN_API = "https://api.devin.ai/v1"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/proxy/devin/"):
            self._proxy_devin()
        else:
            super().do_GET()

    def _proxy_devin(self) -> None:
        api_path = self.path.replace("/proxy/devin/", "", 1)
        url = f"{DEVIN_API}/{api_path}"
        auth = self.headers.get("Authorization", "")
        req = urllib.request.Request(  # noqa: S310
            url, headers={"Authorization": auth}
        )
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310
                body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode())

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        if "/proxy/" in str(args[0]):
            super().log_message(format, *args)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print(f"Dashboard: http://localhost:{PORT}/index.html")
        httpd.serve_forever()
