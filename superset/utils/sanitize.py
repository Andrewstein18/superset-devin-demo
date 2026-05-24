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
"""URL, SVG, and HTML sanitization utilities extracted from superset.utils.core."""

from __future__ import annotations

import re

import markdown as md
import nh3
from markupsafe import Markup


def markdown(raw: str, markup_wrap: bool | None = False) -> str:
    """Render Markdown to sanitized HTML."""
    safe_markdown_tags = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "b",
        "i",
        "strong",
        "em",
        "tt",
        "p",
        "br",
        "span",
        "div",
        "blockquote",
        "code",
        "hr",
        "ul",
        "ol",
        "li",
        "dd",
        "dt",
        "img",
        "a",
    }
    safe_markdown_attrs = {
        "img": {"src", "alt", "title"},
        "a": {"href", "alt", "title", "target"},
    }
    safe = md.markdown(
        raw or "",
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
        ],
    )
    # pylint: disable=no-member
    # nh3 preserves supported link attributes and enforces a safe rel value.
    safe = nh3.clean(safe, tags=safe_markdown_tags, attributes=safe_markdown_attrs)
    if markup_wrap:
        safe = Markup(safe)  # noqa: S704
    return safe


def sanitize_svg_content(svg_content: str) -> str:
    """Basic SVG protection - remove obvious XSS vectors, trust admin input otherwise.

    Minimal protection approach that removes scripts and javascript: URLs while
    preserving all legitimate SVG features. Assumes admin-provided content.

    Args:
        svg_content: Raw SVG content string

    Returns:
        str: SVG content with obvious XSS vectors removed
    """
    if not svg_content or not svg_content.strip():
        return ""

    # Minimal protection: remove obvious malicious content, preserve all SVG features
    content = re.sub(
        r"<script[^>]*>.*?</script>", "", svg_content, flags=re.IGNORECASE | re.DOTALL
    )
    content = re.sub(r"javascript:", "", content, flags=re.IGNORECASE)
    content = re.sub(r"data:[^;]*;[^,]*,.*javascript", "", content, flags=re.IGNORECASE)

    # Remove event handlers (simple catch-all approach)
    content = re.sub(r"\bon\w+\s*=", "", content, flags=re.IGNORECASE)

    # Remove other suspicious patterns
    content = re.sub(
        r"<iframe[^>]*>.*?</iframe>", "", content, flags=re.IGNORECASE | re.DOTALL
    )
    content = re.sub(
        r"<object[^>]*>.*?</object>", "", content, flags=re.IGNORECASE | re.DOTALL
    )
    content = re.sub(r"<embed[^>]*>", "", content, flags=re.IGNORECASE)

    return content


def sanitize_url(url: str) -> str:
    """Sanitize URL using urllib.parse to block dangerous schemes.

    Simple validation using standard library. Allows relative URLs and
    safe absolute URLs while blocking javascript: and other dangerous schemes.

    Args:
        url: Raw URL string

    Returns:
        str: Sanitized URL or empty string if dangerous
    """
    if not url or not url.strip():
        return ""

    url = url.strip()

    # Relative URLs are safe
    if url.startswith("/"):
        return url

    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)

        # Allow safe schemes only
        if parsed.scheme.lower() in {"http", "https", ""}:
            return url

        # Block everything else (javascript:, data:, etc.)
        return ""

    except Exception:
        return ""
