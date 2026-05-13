"""
D3：从法律库「检索结果页」提取「人工智能」命中次数，并汇总为省–年–三类政策口径。

你提供的分类（非法宝站点，需自行配置选择器 / 站点插件）：
  - 法律法规类：省级地方性法规、自治条例和单行条例
  - 部门规章类：地方政府规章
  - 规范性文件类：地方规范性文件、地方司法文件、地方工作文件、行政许可批复

用法概览
---------
目录约定（推荐）：data/d3_policies/<法律法规类|部门规章类|规范性文件类>/<省份>/*.html
  每个省一个文件夹，不再按年份分子目录；同一 HTML 可含 2017–2023 多条结果，脚本按「公布年份」拆到各年。

一键从 data 重算并写入 output/beijing_d3_hit_counts.csv：

   python -m src.d3_legal_hits rebuild-hit-csv

若仍有旧结构「省/年份/」页面，可先迁移到「省/」下（会重写资源目录名并更新 HTML 内引用）：

   python -m src.d3_legal_hits migrate-data-layout

其它子命令：parse-html（单目录追加 jsonl）、aggregate（从 jsonl 汇总）、playwright（需配置）。

使用前请自行确认目标网站的 robots.txt 与用户协议，控制请求频率，避免对订阅库违规批量抓取。
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import shutil
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
# data/d3_policies 下三大类文件夹名（与磁盘目录一致）
POLICY_TYPE_DIRS: tuple[str, ...] = ("法律法规类", "部门规章类", "规范性文件类")

# 大类文件夹 -> 解析时使用的效力位阶标签（用于命中解析与归类）
FOLDER_TO_EFFECTIVENESS: dict[str, str] = {
    "法律法规类": "省级地方性法规",
    "部门规章类": "地方政府规章",
    "规范性文件类": "地方规范性文件",
}

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


def _rewrite_html_asset_paths(html: str, old_stem: str, new_stem: str) -> str:
    """另存为完整网页时，资源目录名为「主 html  stem + _files」；迁移时同步替换引用。"""
    old_m = old_stem + "_files"
    new_m = new_stem + "_files"
    html = html.replace("./" + old_m + "/", "./" + new_m + "/")
    html = html.replace("./" + old_m + "\\", "./" + new_m + "\\")
    html = html.replace('"' + old_m + "/", '"' + new_m + "/")
    html = html.replace("'" + old_m + "/", "'" + new_m + "/")
    return html


def migrate_data_layout(base: Path) -> int:
    """将旧结构「类型/省/四位年/页面.html」迁到「类型/省/」，避免多份页面资源目录同名冲突。"""
    n_moved = 0
    for type_name in POLICY_TYPE_DIRS:
        td = base / type_name
        if not td.is_dir():
            continue
        for prov_dir in sorted(td.iterdir()):
            if not prov_dir.is_dir() or prov_dir.name.startswith("_"):
                continue
            prov = prov_dir.name
            for item in list(prov_dir.iterdir()):
                if not item.is_dir():
                    continue
                if not re.fullmatch(r"\d{4}", item.name):
                    continue
                year = item.name
                html_list = [
                    p
                    for p in chain(item.glob("*.html"), item.glob("*.htm"))
                    if "drag_ele" not in p.name.lower()
                ]
                if not html_list:
                    shutil.rmtree(item, ignore_errors=True)
                    continue
                seq = 0
                for hf in sorted(html_list):
                    old_stem = hf.stem
                    old_files = item / f"{old_stem}_files"
                    while True:
                        new_stem = f"{year}_{prov}_{seq}"
                        dest_html = prov_dir / f"{new_stem}.html"
                        dest_files = prov_dir / f"{new_stem}_files"
                        if not dest_html.exists() and not dest_files.exists():
                            break
                        seq += 1
                    text = hf.read_text(encoding="utf-8", errors="replace")
                    text = _rewrite_html_asset_paths(text, old_stem, new_stem)
                    dest_html.write_text(text, encoding="utf-8")
                    if old_files.is_dir():
                        shutil.copytree(old_files, dest_files, dirs_exist_ok=True)
                        shutil.rmtree(old_files, ignore_errors=True)
                    hf.unlink(missing_ok=True)
                    n_moved += 1
                    seq += 1
                shutil.rmtree(item, ignore_errors=True)
    print(f"migrate-data-layout: 已迁移 {n_moved} 个 HTML 到省目录（并删除旧年份子文件夹）")
    return 0


def collect_html_paths_in_province(prov_dir: Path) -> list[Path]:
    """省目录下顶层 html；若仍存在旧结构 省/年/*.html 也一并扫描。"""
    out: list[Path] = []
    for p in sorted(chain(prov_dir.glob("*.html"), prov_dir.glob("*.htm"))):
        if "drag_ele" in p.name.lower():
            continue
        out.append(p)
    for sub in sorted(prov_dir.iterdir()):
        if not sub.is_dir():
            continue
        if not re.fullmatch(r"\d{4}", sub.name):
            continue
        for p in sorted(chain(sub.glob("*.html"), sub.glob("*.htm"))):
            if "drag_ele" in p.name.lower():
                continue
            out.append(p)
    return out


def rebuild_hit_counts_csv(
    base: Path,
    out_csv: Path,
    *,
    item_selector: str | None = None,
) -> int:
    """扫描三类 × 各省下所有 html，按公布年份归入 2017–2023，汇总为省–年宽表。"""
    rows: list[dict[str, Any]] = []
    for type_name in POLICY_TYPE_DIRS:
        eff = FOLDER_TO_EFFECTIVENESS[type_name]
        td = base / type_name
        if not td.is_dir():
            continue
        for prov_dir in sorted(td.iterdir()):
            if not prov_dir.is_dir() or prov_dir.name.startswith("_"):
                continue
            province = prov_dir.name
            for hf in collect_html_paths_in_province(prov_dir):
                html = hf.read_text(encoding="utf-8", errors="replace")
                rows.extend(
                    parse_result_page(
                        html,
                        province=province,
                        effectiveness_label=eff,
                        item_selector=item_selector,
                        fixed_year=None,
                    )
                )
    sums: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"法律法规类": 0, "部门规章类": 0, "规范性文件类": 0}
    )
    for r in rows:
        key = (r["province"], int(r["year"]))
        sums[key][r["group"]] += int(r["hits"])
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(sums.keys(), key=lambda x: (x[0], x[1]))
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fp:
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
    print(
        f"rebuild-hit-csv: 解析 {len(rows)} 条法规级记录，"
        f"输出 {len(keys)} 行省–年 -> {out_csv}"
    )
    return 0


def cmd_migrate_data_layout(args: argparse.Namespace) -> int:
    root = Path(args.data_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    if not root.is_dir():
        raise SystemExit(f"目录不存在: {root}")
    return migrate_data_layout(root)


def cmd_rebuild_hit_csv(args: argparse.Namespace) -> int:
    root = Path(args.data_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    if not root.is_dir():
        raise SystemExit(f"目录不存在: {root}")
    out = Path(args.output)
    if not out.is_absolute():
        out = Path(__file__).resolve().parents[1] / out
    isel = (args.item_selector or "").strip() or None
    return rebuild_hit_counts_csv(root, out, item_selector=isel)


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

    p_mig = sub.add_parser(
        "migrate-data-layout",
        help="将旧目录 类型/省/年份/ 下保存的网页迁到 类型/省/（重写资源路径）",
    )
    p_mig.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/d3_policies"),
        help="D3 数据根目录，默认 data/d3_policies",
    )
    p_mig.set_defaults(func=cmd_migrate_data_layout)

    p_reb = sub.add_parser(
        "rebuild-hit-csv",
        help="扫描 data 下三类×各省全部 html，按公布年汇总并覆盖输出 CSV",
    )
    p_reb.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/d3_policies"),
        help="D3 数据根目录，默认 data/d3_policies",
    )
    p_reb.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output/beijing_d3_hit_counts.csv"),
        help="输出 CSV，默认 output/beijing_d3_hit_counts.csv",
    )
    p_reb.add_argument(
        "--item-selector",
        default="",
        help="可选：每条结果 CSS 选择器",
    )
    p_reb.set_defaults(func=cmd_rebuild_hit_csv)

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
