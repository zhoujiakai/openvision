"""
Stream coordination module for synchronized multi-stream processing.

多流同步处理协调模块，提供异步迭代器协调多个RTSP流，
产出同步的帧批次用于处理。
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Optional, List

import numpy as np

from override_codes.config import cfg
from override_codes.app.stream_reader import StreamReaderPool, AsyncStreamReader
from logger import create_logger

logger = create_logger("coordinator")


@dataclass
class VSIterData:
    """
    视频流的迭代数据格式 / Video stream iteration data format.

    这是迭代过程中产出的主要数据结构，包含来自所有活跃视频流的同步帧
    This is the primary data structure yielded during iteration,
    containing synchronized frames from all active streams.
    """

    vs_names: List[str] = field(default_factory=list)
    """视频流名称列表 / List of stream names."""

    vs_frames: List[List[np.ndarray]] = field(default_factory=list)
    """对应的帧序列列表 / Corresponding frame sequences for each stream."""

    timestamp: datetime = field(default_factory=datetime.now)
    """批次收集的时间戳 / When this batch was collected."""


class StreamCoordinator:
    """
    管理多个RTSP视频流以进行同步帧处理 / Coordinates multiple RTSP streams for synchronized frame processing.

    这个类管理多个视频流的生命周期，并提供异步迭代器接口来消费同步的帧批次
    This class manages the lifecycle of multiple streams and provides
    an async iterator interface for consuming synchronized frame batches.

    与传统的基于线程的实现不同，这里全程使用async/await模式
    Unlike traditional thread-based implementations, this uses async/await
    patterns throughout for efficient concurrent I/O.

    Usage / 使用示例:
        coordinator = StreamCoordinator(cfg.vs.VS)
        await coordinator.initialize()

        async for iter_data in coordinator:
            # 处理所有视频流的同步帧 / Process synchronized frames from all streams
            for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
                print(f"{name}: {len(frames)} frames")

        await coordinator.shutdown()
    """

    def __init__(self, vs: dict[str, str]):
        """
        初始化协调器 / Initialize the coordinator.

        Args:
            vs: 视频流名称到RTSP URL的映射 / Mapping of stream names to RTSP URLs
        """
        self.vs = vs
        self._pool = StreamReaderPool(vs)
        self.cnt_iter = -1
        self.time_iter = time.time()
        self.is_running = False

    async def initialize(self) -> dict[str, bool]:
        """
        初始化并启动所有管理的视频流 / Initialize and start all managed streams.

        Returns:
            视频流名称到初始化状态的映射 / Mapping of stream names to their initialization status
        """
        if self.is_running:
            return {}

        results = await self._pool.start_all()
        self.is_running = True
        self.time_iter = time.time()
        return results

    async def shutdown(self) -> None:
        """停止所有视频流并释放资源 / Stop all streams and release resources."""
        self.is_running = False
        await self._pool.stop_all()

    def __iter__(self):
        """返回迭代器 / Return the iterator (for compatibility)."""
        self.cnt_iter = -1
        self.time_iter = time.time()
        return self

    def __aiter__(self) -> AsyncIterator:
        """返回异步迭代器 / Return the async iterator."""
        self.cnt_iter = -1
        self.time_iter = time.time()
        return self

    async def __anext__(self) -> VSIterData:
        """
        获取下一批同步帧 / Get the next batch of synchronized frames.

        This method:
        1. 等待配置的迭代间隔 / Waits for the configured iteration interval
        2. 等待所有视频流有足够的帧（带超时）/ Waits for all streams to have enough frames (with timeout)
        3. 收集并返回帧批次 / Collects and returns the frame batch

        Returns:
            VSIterData 包含来自所有视频流的同步帧 / VSIterData containing synchronized frames from all streams

        Raises:
            StopAsyncIteration: 如果协调器未运行 / If the coordinator is not running
        """
        if not self.is_running:
            raise StopAsyncIteration

        # 迭代频率控制，指定时间间隔取一次 / Iteration rate control
        time_delta = time.time() - self.time_iter
        target_interval = cfg.vs.ITER_RATE * cfg.vs.ITER_SEC
        if time_delta < target_interval:
            await asyncio.sleep(target_interval - time_delta)

        # 取出帧 / Collect frames
        vs_names = []
        vs_frames = []
        start_wait = time.time()
        timeout = cfg.rtsp.iteration_timeout

        # 等待所有视频流都准备好，或超时 / Wait for all streams to be ready, or timeout
        readers = self._pool.get_all_readers()
        ready_streams = []

        while time.time() - start_wait < timeout:
            ready_tasks = {
                name: reader.has_enough_frames()
                for name, reader in readers.items()
            }
            results = await asyncio.gather(*ready_tasks.values())

            ready_streams = [
                name for name, is_ready in zip(ready_tasks.keys(), results)
                if is_ready
            ]

            # 等待所有视频流都准备好 / Wait for ALL streams to be ready
            if len(ready_streams) == len(readers):
                break

            # 等待一小段时间再检查 / Wait a bit before checking again
            await asyncio.sleep(0.1)

        # 记录超时的视频流 / Log timed out streams
        not_ready = [name for name in readers if name not in ready_streams]
        if not_ready:
            logger.warning(f"等待超时，跳过未准备好的视频流: {not_ready}")

        # 读取每个已准备好的视频流的帧 / Read frames from each ready stream
        for vs_name in ready_streams:
            reader = readers[vs_name]
            a_vs_frames = await reader.get_buffered_frames()
            vs_names.append(vs_name)
            vs_frames.append(a_vs_frames)

        # 记录迭代时间 / Log iteration timing
        wait = time.time() - self.time_iter
        logger.info(f"内部迭代操作 {wait:.2f}/{cfg.vs.ITER_SEC}秒")

        self.cnt_iter += 1
        self.time_iter = time.time()

        # 返回帧数据 / Return frame data
        vs_iter_data = VSIterData(vs_names=vs_names, vs_frames=vs_frames)
        return vs_iter_data

    async def get_snapshot(self) -> dict[str, Optional[np.ndarray]]:
        """
        获取所有视频流的最新一帧（不使用缓冲）/ Get latest frame from all streams without buffering.

        用于实时预览或监控 / Useful for real-time preview or monitoring.

        Returns:
            视频流名称到最新帧的映射 / Dictionary mapping stream names to their latest frames
        """
        results = {}
        readers = self._pool.get_all_readers()

        tasks = {
            name: reader.get_latest_frame()
            for name, reader in readers.items()
        }
        frames = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (name, _), frame in zip(tasks.items(), frames):
            results[name] = frame if not isinstance(frame, Exception) else None

        return results

    async def get_rt_frame(self) -> tuple[list[str], list[np.ndarray]]:
        """
        获取所有视频流的最新一帧 / Get the latest frame from all streams.

        Returns:
            (通道名列表, 通道帧列表) / (channel names list, channel frames list)
        """
        readers = self._pool.get_all_readers()

        # 并发获取所有流的帧 / Concurrently get frames from all streams
        tasks = {
            name: reader.get_latest_frame()
            for name, reader in readers.items()
        }
        frames = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # 按原始顺序组装结果 / Assemble results in original order
        vs_names = []
        vs_frames = []
        for (name, _), frame in zip(tasks.items(), frames):
            if frame is not None and not isinstance(frame, Exception):
                vs_names.append(name)
                vs_frames.append(frame)

        return vs_names, vs_frames

        return vs_names, vs_frames

    @property
    def stream_names(self) -> list[str]:
        """获取所有管理的视频流名称 / Get all managed stream names."""
        return self._pool.stream_names

    @property
    def iteration_count(self) -> int:
        """获取完成的迭代总数 / Get total iterations completed."""
        return self.cnt_iter

    def get_all_streams_fps(self) -> dict[str, float]:
        """
        获取所有视频流的当前读取帧率 / Get current read FPS for all streams.

        Returns:
            视频流名称到帧率的映射 / Mapping of stream names to their FPS
        """
        return self._pool.get_all_fps()


async def process_streams(
    streams: dict[str, str],
    handler=None,
    **kwargs
) -> None:
    """
    便捷函数：使用处理器处理视频流 / Convenience function to process streams with a handler.

    Args:
        streams: 视频流名称到RTSP URL的映射 / Mapping of stream names to RTSP URLs
        handler: 接收VSIterData对象的异步可调用对象 / Async callable that receives VSIterData objects
        **kwargs: 额外的配置选项（预留）/ Additional configuration options (reserved)
    """
    coordinator = StreamCoordinator(streams)
    await coordinator.initialize()

    try:
        async for iter_data in coordinator:
            if handler:
                await handler(iter_data)
    finally:
        await coordinator.shutdown()


def main():
    """主函数示例 / Main function example."""
    import asyncio

    async def run():
        coordinator = StreamCoordinator(cfg.vs.VS)
        await coordinator.initialize()

        async for iter_data in coordinator:
            vs_names = iter_data.vs_names
            vs_frames = iter_data.vs_frames
            print(f"视频流名称：{vs_names}")
            if vs_frames and vs_frames[0]:
                print(f"画面尺寸: {vs_frames[0][0].shape}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
