"""
Async RTSP Stream Processor

一个基于 asyncio 的现代库，用于管理多个RTSP视频流并进行同步帧批次处理。
A modern, asyncio-based library for managing multiple RTSP video streams
with synchronized frame batch processing.

Example / 使用示例:
    >>> from override_codes import StreamCoordinator, cfg
    >>>
    >>> coordinator = StreamCoordinator(cfg.vs.VS)
    >>> await coordinator.initialize()
    >>>
    >>> async for iter_data in coordinator:
    ...     for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
    ...         print(f"{name}: {len(frames)} frames")
"""

from config import cfg, Config
from override_codes.app.coordinator import StreamCoordinator, VSIterData, process_streams
from override_codes.app.stream_reader import AsyncStreamReader, StreamReaderPool
from logger import create_logger

__all__ = [
    # Settings / 配置
    "cfg",
    "Config",
    "create_logger",
    # Coordinator / 协调器
    "StreamCoordinator",
    "VSIterData",
    "process_streams",
    # Stream Reader / 流读取器
    "AsyncStreamReader",
    "StreamReaderPool",
]

__version__ = "1.0.0"
