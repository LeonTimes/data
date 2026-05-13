"""
将「每条政策一行」的清单汇总为省–年 D3 政策强度（加权求和）。

清单口径（与《数据补充清单.md》一致）：
  - 法律法规类（省级人大立法）：权重 3
  - 部门规章类（省政府/厅局文件）：权重 2  ← 实务中多为「地方政府规章」
  - 规范性文件类（通知、意见、方案）：权重 1

输入 CSV 默认列：省份,年份,政策类型
「政策类型」可为简写三类名，或法宝常见「效力位阶」用语（脚本自动映射）。
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

# 显式三类（推荐你在整理导出结果时归到这三类之一）
EXPLICIT_WEIGHT = {
    "法律法规类": 3,
    "部门规章类": 2,
    "规范性文件类": 1,
    "法律法规": 3,
    "部门规章": 2,
    "规范性文件": 1,
}

# 北大法宝等导出里常见的「效力位阶 / 文献类型」→ 权重（先匹配长的再匹配短的）
# 若一条匹配多条规则，以列表中靠前的为准（下面按特异性大致排序）
PKULAW_PATTERNS: list[tuple[str, int]] = [
    ("地方性法规", 3),
    ("自治条例", 3),
    ("单行条例", 3),
    ("地方政府规章", 2),
    ("部门规章", 2),
    ("规章", 2),  # 可能含「地方政府规章」已先匹配
    ("规范性文件", 1),
    ("行政规范性文件", 1),
    ("通知", 1),
    ("意见", 1),
    ("方案", 1),
    ("办法", 1),  # 多为规范 —— 若与规章冲突需人工复核
]


def weight_for_type_cell(cell: str) -> int | None:
    s = (cell or "").strip()
    if not s:
        return None
    if s in EXPLICIT_WEIGHT:
        return EXPLICIT_WEIGHT[s]
    for pat, w in PKULAW_PATTERNS:
        if pat in s:
            return w
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="D3：政策清单 → 省–年加权强度")
    parser.add_argument(
        "input_csv",
        type=Path,
        help="每条政策一行的 CSV（UTF-8 或带 BOM）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output/d3_policy_intensity.csv"),
        help="输出：省份,年份,D3_AI政策强度",
    )
    parser.add_argument(
        "--type-col",
        default="政策类型",
        help="政策类型列名（默认 政策类型）；也可用法宝导出的列名",
    )
    args = parser.parse_args()

    inp = args.input_csv
    if not inp.is_absolute():
        inp = Path.cwd() / inp

    sums: dict[tuple[str, int], float] = defaultdict(float)
    skipped = 0
    with inp.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if args.type_col not in (reader.fieldnames or []):
            raise SystemExit(
                f"找不到列 {args.type_col!r}，实际列名：{reader.fieldnames}"
            )
        for row in reader:
            prov = (row.get("省份") or "").strip()
            year_s = (row.get("年份") or "").strip()
            if not prov or not year_s:
                skipped += 1
                continue
            try:
                year = int(float(year_s))
            except ValueError:
                skipped += 1
                continue
            w = weight_for_type_cell(row.get(args.type_col, ""))
            if w is None:
                skipped += 1
                continue
            sums[(prov, year)] += w

    out = args.output
    if not out.is_absolute():
        out = Path(__file__).resolve().parents[1] / out
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_out = sorted(sums.keys(), key=lambda x: (x[0], x[1]))
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["省份", "年份", "D3_AI政策强度"])
        for (prov, year) in rows_out:
            w.writerow([prov, year, int(sums[(prov, year)])])

    print(f"已写入 {len(rows_out)} 行省–年汇总 -> {out}")
    if skipped:
        print(f"提示：跳过 {skipped} 行（缺字段或无法识别政策类型）")


if __name__ == "__main__":
    main()
