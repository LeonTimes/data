"""
D3：从法律库「检索结果页」提取「人工智能」命中次数，并汇总为省–年–三类政策口径。

你提供的分类（非法宝站点，需自行配置选择器 / 站点插件）：
  - 法律法规类：省级地方性法规、自治条例和单行条例
  - 部门规章类：地方政府规章
  - 规范性文件类：地方规范性文件、地方司法文件、地方工作文件、行政许可批复

用法概览
---------
1) 推荐（合规、可复现）：在浏览器中完成检索后，将「每一页结果」另存为 .html，
   再批量解析：

   python -m src.d3_legal_hits parse-html \\
     --html-dir path/to/上海/法律法规类/省级地方性法规 \\
     --province 上海 \\
     --effectiveness 省级地方性法规 \\
     --append-jsonl data/d3_policies/_合并目录表/hits_raw.jsonl

   对每种「效力位阶」子类各存一批页面，重复上述命令（换 --effectiveness 与目录）。

2) 汇总为「各省各年三种政策类型的命中次数」（宽表）：

   python -m src.d3_legal_hits aggregate \\
     --jsonl data/d3_policies/_合并目录表/hits_raw.jsonl \\
     -o output/d3_province_year_hit_counts.csv

3) 全自动 Playwright：需在 data/d3_scraper_config.json 中填写 selectors，
   并实现 src/d3_site_plugin.py 中的 apply_search（见 d3_site_plugin_template.py）。

使用前请自行确认目标网站的 robots.txt 与用户协议，控制请求频率，避免对订阅库违规批量抓取。
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
from itertools import chain
from collections import defaultdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound

# 效力位阶子类 -> 清单中的三大类（与当前课题划分一致）
EFFECTIVENESS_TO_GROUP: dict[str, str] = {
    "省级地方性法规": "法律法规类",
    "自治条例和单行条例": "法律法规类",
    "地方政府规章": "部门规章类",
    "地方规范性文件": "规范性文件类",
    "地方司法文件": "规范性文件类",
    "地方工作文件": "规范性文件类",
    "行政许可批复": "规范性文件类",
}

# 每类包含的子检索（用于提示 / 文档）；实际检索在浏览器或插件中完成
GROUP_SUBFILTERS: dict[str, tuple[str, ...]] = {
    "法律法规类": ("省级地方性法规", "自治条例和单行条例"),
    "部门规章类": ("地方政府规章",),
    "规范性文件类": (
        "地方规范性文件",
        "地方司法文件",
        "地方工作文件",
        "行政许可批复",
    ),
}

_HIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"全文命中次数[：:\s]*人工智能\s*[（(]?\s*(\d+)\s*[）)]?"),
    re.compile(r"人工智能\s*[（(]\s*(\d+)\s*[）)]"),
    re.compile(r"人工智能[^\d]{0,12}?(\d+)\s*次"),
]

_YEAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"公布日期\s*[：:]\s*(\d{4})[./年]"),
    re.compile(r"发布日期\s*[：:]\s*(\d{4})[./年]"),
    re.compile(r"(\d{4})\s*[./年]\s*\d{1,2}\s*[./月]\s*\d{1,2}\s*日?\s*(?:公布|发布)"),
]


def extract_hit_count(text: str) -> int:
    for pat in _HIT_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return 0


def extract_pub_year(text: str) -> int | None:
    for pat in _YEAR_PATTERNS:
        m = pat.search(text)
        if m:
            y = int(m.group(1))
            if 1990 <= y <= 2100:
                return y
    return None


def split_blocks_html(html: str, item_selector: str | None) -> list[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")
    if item_selector:
        els = soup.select(item_selector)
        if els:
            return [el.get_text("\n", strip=True) for el in els]
    # 常见检索结果容器（如法宝保存网页）
    default_selectors = [
        ".searchList-container",
        ".fb-common-article",
        ".el-table__body .el-table__row",
    ]
    for sel in default_selectors:
        els = soup.select(sel)
        if len(els) >= 1:
            return [el.get_text("\n", strip=True) for el in els]
    text = soup.get_text("\n", strip=False)
    # 常见：结果以「数字. 标题」起行
    parts = re.split(r"(?=^\s*\d+\.\s*\S)", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def parse_result_page(
    html: str,
    *,
    province: str,
    effectiveness_label: str,
    item_selector: str | None = None,
    fixed_year: int | None = None,
) -> list[dict[str, Any]]:
    group = EFFECTIVENESS_TO_GROUP.get(effectiveness_label)
    if group is None:
        raise ValueError(
            f"未知的效力位阶标签 {effectiveness_label!r}；"
            f"允许: {list(EFFECTIVENESS_TO_GROUP)}"
        )
    rows: list[dict[str, Any]] = []
    for block in split_blocks_html(html, item_selector):
        year = extract_pub_year(block)
        hits = extract_hit_count(block)
        if year is None or not (2017 <= year <= 2023):
            continue
        if fixed_year is not None and year != fixed_year:
            continue
        if hits <= 0:
            continue
        rows.append(
            {
                "province": province,
                "year": year,
                "group": group,
                "hits": hits,
                "effectiveness": effectiveness_label,
            }
        )
    return rows


def cmd_parse_html(args: argparse.Namespace) -> int:
    d = Path(args.html_dir)
    if not d.is_dir():
        raise SystemExit(f"不是目录: {d}")
    item_sel = args.item_selector or None
    all_rows: list[dict[str, Any]] = []
    for p in sorted(chain(d.glob("*.html"), d.glob("*.htm"))):
        html = p.read_text(encoding="utf-8", errors="replace")
        all_rows.extend(
            parse_result_page(
                html,
                province=args.province,
                effectiveness_label=args.effectiveness,
                item_selector=item_sel,
                fixed_year=args.fixed_year,
            )
        )
    out_path = Path(args.append_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"从 {d} 解析出 {len(all_rows)} 条记录，已追加到 {out_path}")
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    path = Path(args.jsonl)
    sums: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"法律法规类": 0, "部门规章类": 0, "规范性文件类": 0}
    )
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            key = (r["province"], int(r["year"]))
            g = r["group"]
            sums[key][g] += int(r["hits"])
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(sums.keys(), key=lambda x: (x[0], x[1]))
    with out.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(
            [
                "省份",
                "年份",
                "法律法规类_命中次数",
                "部门规章类_命中次数",
                "规范性文件类_命中次数",
            ]
        )
        for prov, year in keys:
            g = sums[(prov, year)]
            w.writerow(
                [
                    prov,
                    year,
                    g["法律法规类"],
                    g["部门规章类"],
                    g["规范性文件类"],
                ]
            )
    print(f"已写入 {len(keys)} 行 -> {out}")
    return 0


def _load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_playwright(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "未安装 playwright。请执行: pip install playwright && playwright install chromium"
        ) from e
    cfg_path = Path(args.config)
    cfg = _load_config(cfg_path)
    sel = cfg.get("selectors") or {}
    item_sel = (sel.get("result_item") or "").strip()
    next_sel = (sel.get("next_page") or "").strip()
    plugin_mod = (cfg.get("plugin_module") or "").strip()
    plugin_fn = (cfg.get("plugin_callable") or "apply_search").strip()
    if not plugin_mod:
        raise SystemExit(
            "全自动模式需要在配置 JSON 中设置 plugin_module（例如 src.d3_site_plugin），"
            "并实现 apply_search；或改用 parse-html 子命令处理另存为的 HTML。"
        )

    mod = importlib.import_module(plugin_mod)
    apply_search = getattr(mod, plugin_fn)
    site = cfg.get("site") or {}
    start_url = site.get("start_url") or ""
    if not start_url:
        raise SystemExit("配置中 site.start_url 不能为空")

    search_cfg = cfg.get("search") or {}
    keyword = search_cfg.get("keyword") or "人工智能"
    d0 = search_cfg.get("date_start") or "2017-01-01"
    d1 = search_cfg.get("date_end") or "2023-12-31"
    provinces = cfg.get("provinces") or []
    storage = cfg.get("playwright_storage_state") or ""
    timeout = int(site.get("navigation_timeout_ms") or 90000)

    out_jsonl = Path(args.output_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    filters = list(EFFECTIVENESS_TO_GROUP.keys())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        ctx_kw: dict[str, Any] = {}
        if storage and Path(storage).is_file():
            ctx_kw["storage_state"] = storage
        context = browser.new_context(**ctx_kw)
        page = context.new_page()
        page.set_default_timeout(timeout)
        page.goto(start_url)

        for prov in provinces:
            for eff in filters:
                apply_search(page, prov, eff, keyword, d0, d1)
                page.wait_for_timeout(2000)
                while True:
                    html = page.content()
                    rows = parse_result_page(
                        html,
                        province=prov,
                        effectiveness_label=eff,
                        item_selector=item_sel or None,
                    )
                    with out_jsonl.open("a", encoding="utf-8") as f:
                        for r in rows:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    if not next_sel:
                        break
                    nxt = page.locator(next_sel).first
                    if not nxt.count() or not nxt.is_enabled():
                        break
                    nxt.click()
                    page.wait_for_load_state("networkidle")
        browser.close()

    print(f"已追加写入 {out_jsonl}；请运行 aggregate 生成宽表。")
    return 0


def cmd_list_filters(_: argparse.Namespace) -> int:
    print("效力位阶子类 -> 三大类：")
    for k, v in EFFECTIVENESS_TO_GROUP.items():
        print(f"  {k} -> {v}")
    print("\n三大类包含的子类：")
    for g, subs in GROUP_SUBFILTERS.items():
        print(f"  {g}: {', '.join(subs)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="D3 命中次数：解析 HTML 或 Playwright 脚手架")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-filters", help="打印效力位阶与三大类对应关系")
    p_list.set_defaults(func=cmd_list_filters)

    p_parse = sub.add_parser("parse-html", help="从保存的结果页 HTML 解析并追加 jsonl")
    p_parse.add_argument("--html-dir", type=Path, required=True)
    p_parse.add_argument("--province", required=True, help="本目录结果对应的省，如 上海")
    p_parse.add_argument(
        "--effectiveness",
        required=True,
        help="本批页面使用的效力位阶子类，如 省级地方性法规",
    )
    p_parse.add_argument(
        "--item-selector",
        default="",
        help="可选：每条结果对应的 CSS 选择器，提高解析准确率",
    )
    p_parse.add_argument(
        "--append-jsonl",
        type=Path,
        default=Path("data/d3_policies/_合并目录表/hits_raw.jsonl"),
    )
    p_parse.add_argument(
        "--fixed-year",
        type=int,
        default=None,
        help="可选：仅统计该年份（建议与你检索页的发布年份一致，例如 2022）",
    )
    p_parse.set_defaults(func=cmd_parse_html)

    p_agg = sub.add_parser("aggregate", help="将 jsonl 汇总为省-年-三类命中宽表")
    p_agg.add_argument(
        "--jsonl",
        type=Path,
        default=Path("data/d3_policies/_合并目录表/hits_raw.jsonl"),
    )
    p_agg.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output/d3_province_year_hit_counts.csv"),
    )
    p_agg.set_defaults(func=cmd_aggregate)

    p_pw = sub.add_parser(
        "playwright",
        help="全自动（需配置 plugin + selectors；请先确认站点条款）",
    )
    p_pw.add_argument(
        "--config",
        type=Path,
        default=Path("data/d3_scraper_config.json"),
    )
    p_pw.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("data/d3_policies/_合并目录表/hits_raw.jsonl"),
    )
    p_pw.add_argument("--headed", action="store_true", help="有头浏览器，便于调试与登录")
    p_pw.set_defaults(func=cmd_playwright)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
