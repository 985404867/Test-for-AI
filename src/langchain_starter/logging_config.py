"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(log_path: Path = Path("data/logs/app.log")) -> None:
    """初始化文件日志和控制台日志。

    场景：CLI、GUI 和 Web 服务启动时调用，统一把运行信息写入文件并输出到终端。
    """

    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
