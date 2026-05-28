"""Runtime date and time context."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def current_datetime_context() -> str:
    """Return the current local date/time context for prompts."""

    now = datetime.now(LOCAL_TIMEZONE)
    return (
        f"当前日期：{now:%Y-%m-%d}。"
        f"当前时间：{now:%H:%M:%S}。"
        "时区：Asia/Shanghai。"
    )
