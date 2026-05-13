"""示例：GET 页面并解析 <title>。请按目标站改 URL/选择器，并遵守 robots 与站点条款。"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DataScrapeBot/0.1; +https://example.com/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_html(url: str, timeout: float = 30.0) -> str:
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        r = client.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text


def demo_parse(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    return title


def main() -> int:
    p = argparse.ArgumentParser(description="抓取示例：GET 并打印 <title>")
    p.add_argument("url", nargs="?", default="https://example.com", help="要请求的 URL")
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https"):
        print("仅支持 http/https URL", file=sys.stderr)
        return 2

    try:
        html = fetch_html(args.url, timeout=args.timeout)
        title = demo_parse(html)
        print(title or "(无 title)")
    except httpx.HTTPStatusError as e:
        print(f"HTTP 错误: {e.response.status_code}", file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
