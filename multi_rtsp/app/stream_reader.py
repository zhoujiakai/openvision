"""
Async RTSP stream reader using asyncio and OpenCV.

This module provides an asynchronous interface for reading RTSP streams,
distinct from threaded implementations.
"""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, AsyncIterator

import cv2
import numpy as np

from logger import create_logger
from override_codes.config import cfg

logger = create_logger("stream_reader")


@dataclass
class StreamStats:
    """Runtime statistics for a stream."""

    frames_read: int = 0
    """Total frames successfully read from camera."""

    frames_buffered: int = 0
    """Total frames added to buffer."""

    last_update: Optional[datetime] = None
    """Timestamp of the last successful frame read."""

    reconnects: int = 0
    """Number of times the stream reconnected."""

    frames_at_last_iter: int = 0
    """Frame count at last iteration for tracking new frames."""

    buffered_at_last_iter: int = 0
    """Buffered frame count at last iteration."""

    # 帧率统计 / FPS statistics
    _fps_start_time: float = 0.0
    """Start time for FPS calculation."""

    _fps_frame_count: int = 0
    """Frame count for FPS calculation."""

    last_fps: float = 0.0
    """Last calculated FPS."""


class AsyncStreamReader:
    """
    Asynchronously reads frames from an RTSP stream.

    This class uses a single async task for both decoding and buffering,
    differing from the dual-thread approach of traditional implementations.

    Usage:
        reader = AsyncStreamReader(stream_config)
        await reader.start()

        # Get buffered frames
        frames = await reader.get_buffered_frames()

        # Or iterate over individual frames
        async for frame in reader.stream_frames():
            process(frame)

        await reader.stop()
    """

    def __init__(self, rtsp_url: str, vs_name: str,
                 frame_queue_size: Optional[int] = None):
        """
        初始化AsyncStreamReader类 / Initialize the AsyncStreamReader class.

        Args:
            rtsp_url: RTSP URL for connecting to video stream / RTSP视频流地址
            vs_name: Stream name for identifying this stream / 视频流名称
            frame_queue_size: Maximum frame queue size / 帧队列的最大大小
        """
        self.rtsp_url = rtsp_url
        self.vs_name = vs_name
        self.frame_queue_size = frame_queue_size or cfg.vs.SEQ
        self._capture: Optional[cv2.VideoCapture] = None
        self._buffer: list[np.ndarray] = []
        self._latest_frame: Optional[np.ndarray] = None
        self._running = False
        self._task_read: Optional[asyncio.Task] = None
        self._task_buffer: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._stats = StreamStats()

    @property
    def name(self) -> str:
        """获取视频流名称 / Get the stream name."""
        return self.vs_name

    @property
    def buffer_size(self) -> int:
        """获取所需缓冲区大小 / Get the required buffer size."""
        return self.frame_queue_size

    @property
    def stats(self) -> StreamStats:
        """Get stream statistics."""
        return self._stats

    @property
    def is_running(self) -> bool:
        """Check if the stream is currently running."""
        return self._running

    @property
    def is_stale(self) -> bool:
        """
        检查视频流是否最近没有收到帧 / Check if stream hasn't received new frames recently.

        如果在配置的 frame_timeout 时间内没有收到帧，则认为流是 stale 的。
        A stream is considered stale if no frames have been received
        within the configured frame_timeout period.
        """
        if self._stats.last_update is None:
            return True
        elapsed = (datetime.now() - self._stats.last_update).total_seconds()
        return elapsed > cfg.rtsp.frame_timeout

    def get_fps(self) -> float:
        """
        获取当前读取帧率 / Get current read FPS.

        Returns:
            当前帧率 / Current frames per second
        """
        return self._stats.last_fps

    async def start(self) -> bool:
        """
        启动视频流读取 / Start reading the RTSP stream.

        Returns:
            成功返回 True，否则返回 False / True if started successfully, False otherwise
        """
        if self._running:
            return True

        self._capture = cv2.VideoCapture(self.rtsp_url)
        if not self._capture.isOpened():
            logger.error(f"视频流 {self.vs_name} 无法打开，RTSP URL: {self.rtsp_url}")
            return False

        self._running = True
        self._buffer = []
        self._task_read = asyncio.create_task(self._read_loop())
        self._task_buffer = asyncio.create_task(self._buffer_loop())
        logger.info(f"视频流 {self.name} 已启动")
        return True

    async def stop(self) -> None:
        """Stop reading the stream and release resources."""
        self._running = False
        if self._task_read:
            self._task_read.cancel()
            try:
                await self._task_read
            except asyncio.CancelledError:
                pass
        if self._task_buffer:
            self._task_buffer.cancel()
            try:
                await self._task_buffer
            except asyncio.CancelledError:
                pass
        if self._capture:
            self._capture.release()
            self._capture = None
        logger.info(f"视频流 {self.name} 已停止")

    async def _read_loop(self) -> None:
        """
        主读取循环 / Main reading loop that runs asynchronously.

        This method mimics the threaded behavior:
        1. 持续读取帧（保持解码器健康）/ Continuously reads frames (keeps decoder healthy)
        2. 更新最新帧引用 / Updates the latest frame reference
        3. 通过单独任务按控制速率添加帧到缓冲区 / Adds frames to buffer at controlled rate via separate task
        """
        while self._running:
            # 读取帧（阻塞操作，在线程池执行）/ Read frame (blocking, runs in executor)
            ret, frame = await asyncio.to_thread(self._capture.read)

            if not ret:
                # 连接丢失，尝试重连 / Connection lost, attempt reconnect
                await asyncio.sleep(cfg.rtsp.retry_interval)
                self._capture.release()
                self._capture = cv2.VideoCapture(self.rtsp_url)
                self._stats.reconnects += 1
                continue

            # 验证帧 / Validate frame
            if not self._validate_frame(frame):
                continue

            # 更新最新帧 / Update latest frame (与原始版本一致，不加锁 / Same as original, no lock)
            self._latest_frame = frame
            self._stats.frames_read += 1
            self._stats.last_update = datetime.now()

            # 更新帧率统计 / Update FPS statistics
            self._stats._fps_frame_count += 1
            if self._stats._fps_start_time == 0:
                self._stats._fps_start_time = time.time()
            elapsed = time.time() - self._stats._fps_start_time
            if elapsed >= 1.0:  # 每秒更新一次 / Update every second
                self._stats.last_fps = self._stats._fps_frame_count / elapsed
                self._stats._fps_frame_count = 0
                self._stats._fps_start_time = time.time()

            # 小延迟以防止阻塞事件循环 / Small yield to prevent blocking event loop
            # 但保持足够快的读取以保持解码器健康 / but keep reading fast for decoder health
            await asyncio.sleep(0.001)

    async def _buffer_loop(self) -> None:
        """ 单独的循环，按控制的FPS添加帧到缓冲区 / Separate loop adding frames to buffer at controlled FPS. """
        target_interval = 1.0 / cfg.vs.FPS
        last_buffer_time = time.time()

        while self._running:
            current_time = time.time()
            elapsed = current_time - last_buffer_time

            if elapsed < target_interval:
                # 等待下一个缓冲时间 / Wait until next buffer time
                await asyncio.sleep(target_interval - elapsed)
                last_buffer_time = time.time()
            else:
                last_buffer_time = current_time

            # 检查是否有有效帧可缓冲 / Check if we have a valid frame to buffer
            if self._validate_frame(self._latest_frame):
                await self._add_to_buffer(self._latest_frame)

    async def _add_to_buffer(self, frame: np.ndarray) -> None:
        """Add a frame to the buffer, maintaining max size."""
        async with self._lock:
            self._buffer.append(frame)
            self._stats.frames_buffered += 1
            # Trim to max size
            if len(self._buffer) > self.buffer_size:
                self._buffer = self._buffer[-self.buffer_size:]

    def _validate_frame(self, frame: Optional[np.ndarray]) -> bool:
        """Validate that a frame is usable."""
        if frame is None:
            return False
        if frame.ndim != 3:
            return False
        if frame.size == 0:
            return False
        return True

    async def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame without removing it from buffer.

        Returns:
            The latest frame or None if no frame is available.
        """
        if self._latest_frame is None:
            return None
        return self._latest_frame.copy()

    async def get_buffered_frames(self) -> list[np.ndarray]:
        """
        Get and clear all currently buffered frames.

        Returns:
            List of buffered frames, cleared after retrieval.
        """
        async with self._lock:
            frames = self._buffer.copy()
            self._buffer.clear()

        # Log frames retrieved this iteration
        buffered_this_iter = len(frames)
        frames_read_since_last = self._stats.frames_read - self._stats.frames_at_last_iter
        logger.info(f"{self.name}在迭代期间存储{buffered_this_iter}/{self.buffer_size}帧 (摄像头读取{frames_read_since_last}帧)")
        self._stats.frames_at_last_iter = self._stats.frames_read

        return frames

    async def has_enough_frames(self) -> bool:
        """Check if the buffer has at least the required number of frames."""
        async with self._lock:
            return len(self._buffer) >= self.buffer_size

    async def stream_frames(self) -> AsyncIterator[np.ndarray]:
        """
        Iterate over frames as they arrive.

        Yields:
            Individual frames from the stream.
        """
        while self._running:
            frame = await self.get_latest_frame()
            if frame is not None:
                yield frame
            await asyncio.sleep(0.1)


class StreamReaderPool:
    """
    管理多个AsyncStreamReader实例 / Manages a pool of AsyncStreamReader instances.

    提供批量操作来并发管理多个视频流 / Provides batch operations for managing multiple streams concurrently.
    """

    def __init__(self, streams: dict[str, str]):
        """
        初始化流池 / Initialize the stream pool.

        Args:
            streams: 视频流名称到RTSP URL的映射 / Mapping of stream names to RTSP URLs
        """
        self._readers: dict[str, AsyncStreamReader] = {}
        for vs_name, rtsp_url in streams.items():
            self._readers[vs_name] = AsyncStreamReader(rtsp_url, vs_name)

    async def start_all(self) -> dict[str, bool]:
        """
        并发启动所有视频流 / Start all streams concurrently.

        Returns:
            视频流名称到启动状态的映射 / Mapping of stream names to start success status
        """
        results = {}
        tasks = {
            name: reader.start()
            for name, reader in self._readers.items()
        }
        started = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (name, _), result in zip(tasks.items(), started):
            results[name] = result if not isinstance(result, Exception) else False

        return results

    async def stop_all(self) -> None:
        """并发停止所有视频流 / Stop all streams concurrently."""
        tasks = [reader.stop() for reader in self._readers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_reader(self, name: str) -> Optional[AsyncStreamReader]:
        """通过名称获取特定的读取器 / Get a specific reader by name."""
        return self._readers.get(name)

    def get_all_readers(self) -> dict[str, AsyncStreamReader]:
        """获取所有读取器 / Get all readers."""
        return self._readers.copy()

    @property
    def stream_names(self) -> list[str]:
        """获取所有视频流名称 / Get all stream names."""
        return list(self._readers.keys())

    def get_all_fps(self) -> dict[str, float]:
        """
        获取所有视频流的当前帧率 / Get current FPS for all streams.

        Returns:
            视频流名称到帧率的映射 / Mapping of stream names to their FPS
        """
        return {name: reader.get_fps() for name, reader in self._readers.items()}

    async def get_all_latest_frames(self) -> dict[str, Optional[np.ndarray]]:
        """
        Get the latest frame from all streams concurrently.

        Returns:
            Dictionary mapping stream names to their latest frames.
        """
        results = {}
        tasks = {
            name: reader.get_latest_frame()
            for name, reader in self._readers.items()
        }
        frames = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (name, _), frame in zip(tasks.items(), frames):
            results[name] = frame if not isinstance(frame, Exception) else None

        return results
