"""Runtime date and time context."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def current_datetime_context() -> str:
    """生成当前日期时间上下文，供提示词和 Agent 参考。"""

    now = datetime.now(LOCAL_TIMEZONE)
    return (
        f"当前日期：{now:%Y-%m-%d}。"
        f"当前时间：{now:%H:%M:%S}。"
        "时区：Asia/Shanghai。"
    )
