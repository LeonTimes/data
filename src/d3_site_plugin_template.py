"""
在目标法律库网站上完成一次「高级检索」的占位实现。

1. 复制本文件为 d3_site_plugin.py（与 config 里 plugin_module 一致）
2. 实现 apply_search：用 Playwright 的 locator / fill / click 勾选
   制定机关/地域、公布日期、效力位阶、全文关键词等
3. 不要在代码里硬编码账号密码；首次用有头浏览器登录后保存 storage_state

函数签名（同步 Playwright）：
  def apply_search(page, province: str, effectiveness_label: str, keyword: str,
                   date_start: str, date_end: str) -> None
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


def apply_search(
    page: "Page",
    province: str,
    effectiveness_label: str,
    keyword: str,
    date_start: str,
    date_end: str,
) -> None:
    raise NotImplementedError(
        "请实现 apply_search：根据你使用的网站 DOM 填写检索条件。"
        f" 当前参数 province={province!r}, effectiveness_label={effectiveness_label!r}, "
        f"keyword={keyword!r}, date_start={date_start!r}, date_end={date_end!r}"
    )
