"""HTTP request tools — make API calls with GET/POST/PUT/PATCH/DELETE.

Uses httpx (already a project dependency) for robust HTTP with
timeout, redirect following, and JSON support. No external curl needed.
"""

import json
import time
from typing import Any

import httpx

REQUEST_TIMEOUT = 30


def http_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str = "",
    json_body: dict[str, Any] | None = None,
    query_params: dict[str, str] | None = None,
    auth_token: str = "",
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    """Make an HTTP request and return the response.

    Args:
        method: HTTP method: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
        url: Full URL to request
        headers: Optional dict of HTTP headers
        body: Raw request body string
        json_body: JSON body (auto-sets Content-Type: application/json)
        query_params: URL query parameters dict
        auth_token: Bearer token (added as Authorization header)
        timeout: Request timeout in seconds (default: 30)
    """
    method = method.upper().strip()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        return f"Error: Invalid method '{method}'. Use: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS"

    if not url:
        return "Error: 'url' is required"

    # Build headers
    req_headers = dict(headers or {})
    req_headers.setdefault("User-Agent", "PyOz/1.0")
    if auth_token:
        req_headers["Authorization"] = f"Bearer {auth_token}"

    start = time.time()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": req_headers,
            }
            if query_params:
                kwargs["params"] = query_params
            if json_body:
                kwargs["json"] = json_body
            elif body:
                kwargs["content"] = body

            response = client.request(**kwargs)

        elapsed = time.time() - start

        # Format response
        lines = [
            f"HTTP {response.status_code} {response.reason_phrase}",
            f"Time: {elapsed:.2f}s",
            "",
            "Response Headers:",
        ]

        # Show important headers
        important_headers = [
            "content-type", "content-length", "server", "date",
            "x-request-id", "x-ratelimit-remaining", "location",
            "set-cookie", "cache-control", "etag",
        ]
        for key, value in response.headers.items():
            if key.lower() in important_headers:
                lines.append(f"  {key}: {value}")

        # Body
        lines.append("")
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                data = response.json()
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
                # Truncate very long responses
                if len(formatted) > 5000:
                    formatted = formatted[:5000] + "\n... (truncated)"
                lines.append("Body (JSON):")
                lines.append(formatted)
            except (json.JSONDecodeError, ValueError):
                body_text = response.text[:5000]
                lines.append("Body:")
                lines.append(body_text)
        elif "text/" in content_type or "xml" in content_type or "html" in content_type:
            body_text = response.text[:5000]
            if len(response.text) > 5000:
                body_text += "\n... (truncated)"
            lines.append("Body:")
            lines.append(body_text)
        else:
            size = len(response.content)
            lines.append(f"Body: <binary data, {size} bytes>")

        return "\n".join(lines)

    except httpx.ConnectError as e:
        return f"Error: Connection failed — {e}"
    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout}s"
    except httpx.TooManyRedirects:
        return "Error: Too many redirects"
    except httpx.HTTPError as e:
        return f"Error: HTTP error — {e}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
