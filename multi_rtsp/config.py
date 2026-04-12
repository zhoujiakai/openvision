"""
Configuration settings for async RTSP stream processor.

Uses the same pattern as the original app: Config class with nested
configuration sections loaded from YAML.
"""
from pathlib import Path
from typing import Optional
import yaml


class Config:
    """Global configuration class."""

    BASE_DIR: Path = Path(__file__).resolve().parent

    def __init__(self) -> None:
        """Initialize configuration and load from YAML file."""
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from config.yaml file."""
        config_file_path = self.BASE_DIR / "config.yaml"
        if not config_file_path.exists():
            return

        with open(config_file_path, encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        for k, v in raw.items():
            if not isinstance(v, dict):
                continue
            section_cls = getattr(self.__class__, k, None)
            if section_cls is None or not isinstance(section_cls, type):
                continue
            for k2, v2 in v.items():
                setattr(section_cls, k2, v2)

    class vs:
        """视频流配置 / Video stream configuration."""

        # 每个视频流需要保存进视频队列的帧率
        # Frames per second to save for each video stream
        FPS: int = 5

        # 单位：秒，每个视频流凑够这么长时间的帧作为处理序列
        # Duration in seconds to buffer frames for processing
        ITER_SEC: int = 6

        # FPS * ITER_SEC，每个视频流凑够这么多帧作为处理序列
        # Number of frames to buffer for processing sequence
        SEQ: int = 30

        # 视频流配置：名称 -> RTSP URL
        # Stream configuration: name -> RTSP URL
        VS: dict = {
            "rtsp1": "rtsp://localhost:8554/video1",
            "rtsp2": "rtsp://localhost:8554/video2"
        }

        # 迭代缓冲系数，1表示不缓冲
        # Iteration buffer factor, 1 means no buffer
        ITER_RATE: float = 1

    class rtsp:
        """RTSP 连接配置 / RTSP connection configuration."""

        # 迭代超时时间（秒）
        # Maximum seconds to wait for all streams to be ready
        iteration_timeout: float = 10.0

        # 帧超时时间（秒），多久没有新帧认为流 stale
        # Seconds without new frames before considering stream stale
        frame_timeout: float = 5.0

        # 重试间隔（秒）
        # Seconds to wait before retrying failed connection
        retry_interval: float = 1.0


# Global configuration instance
cfg = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return cfg
