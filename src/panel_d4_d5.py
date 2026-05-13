"""
根据《数据补充清单.md》中的规则，生成省级面板：D4（AI 试验区虚拟变量）、D5（东中西东北分组代码）。

说明：D4/D5 由官方名单与统计分区规则确定，不依赖网页爬取；本脚本可重复运行，便于与主数据按「省份-年份」合并。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

# 31 个省级行政区（不含港澳台），名称与常见统计年鉴简称一致
PROVINCES = [
    "北京",
    "天津",
    "河北",
    "山西",
    "内蒙古",
    "辽宁",
    "吉林",
    "黑龙江",
    "上海",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "海南",
    "重庆",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
]

# D5：国家统计局四大板块（东部=1，中部=2，西部=3，东北=4）
D5_REGION: dict[str, int] = {}
for p in ["北京", "天津", "河北", "上海", "江苏", "浙江", "福建", "山东", "广东", "海南"]:
    D5_REGION[p] = 1
for p in ["山西", "安徽", "江西", "河南", "湖北", "湖南"]:
    D5_REGION[p] = 2
for p in [
    "内蒙古",
    "广西",
    "重庆",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
]:
    D5_REGION[p] = 3
for p in ["辽宁", "吉林", "黑龙江"]:
    D5_REGION[p] = 4

# D4：工信部 AI 创新发展试验区 — 城市名单映射到省，设立当年及以后=1
# 2019 首批：北京、上海
# 2020 第二批：杭州→浙江，广州/深圳→广东，天津，长沙→湖南，合肥→安徽
# 2021 第三批：成都→四川，重庆，西安→陕西，武汉→湖北，南京/苏州→江苏，济南→山东
D4_FIRST_YEAR: dict[str, int] = {
    "北京": 2019,
    "上海": 2019,
    "浙江": 2020,
    "广东": 2020,
    "天津": 2020,
    "湖南": 2020,
    "安徽": 2020,
    "四川": 2021,
    "重庆": 2021,
    "陕西": 2021,
    "湖北": 2021,
    "江苏": 2021,
    "山东": 2021,
}


def d4_value(province: str, year: int) -> int:
    first = D4_FIRST_YEAR.get(province)
    if first is None:
        return 0
    return 1 if year >= first else 0


def generate_rows(start_year: int, end_year: int) -> list[tuple[str, int, int, int]]:
    rows: list[tuple[str, int, int, int]] = []
    for year in range(start_year, end_year + 1):
        for province in PROVINCES:
            d5 = D5_REGION[province]
            d4 = d4_value(province, year)
            rows.append((province, year, d4, d5))
    return rows


def write_csv(path: Path, rows: list[tuple[str, int, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["省份", "年份", "D4_AI试验区", "D5_区域分组"])
        for province, year, d4, d5 in rows:
            w.writerow([province, year, d4, d5])


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 D4、D5 省-年面板 CSV")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2010,
        help="起始年份（含），默认 2010",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2023,
        help="结束年份（含），默认 2023",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output/panel_d4_d5.csv"),
        help="输出 CSV 路径，默认 output/panel_d4_d5.csv",
    )
    args = parser.parse_args()
    if args.end_year < args.start_year:
        raise SystemExit("end-year 必须 >= start-year")

    rows = generate_rows(args.start_year, args.end_year)
    out = args.output
    if not out.is_absolute():
        out = Path(__file__).resolve().parents[1] / out
    write_csv(out, rows)
    print(f"已写入 {len(rows)} 行 -> {out}")


if __name__ == "__main__":
    main()
