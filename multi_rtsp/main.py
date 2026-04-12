"""
Example usage of the async RTSP stream processor.

This module demonstrates how to use the StreamCoordinator for processing
multiple video streams asynchronously.
"""
import asyncio
import signal
import time

import cv2
import numpy as np

from override_codes.app.coordinator import StreamCoordinator, VSIterData, process_streams
from override_codes.config import cfg


class DisplayHandler:
    """
    Handles display of video frames using OpenCV.

    Supports both individual frame preview and batch visualization.
    """

    def __init__(self, scale: float = 0.5):
        """
        Initialize the display handler.

        Args:
            scale: Scale factor for displayed frames (0.5 = half size)
        """
        self.scale = scale
        self.windows = set()

        # 帧率统计 / FPS statistics
        self._frame_count = 0
        self._start_time = time.time()
        self._last_fps = 0.0

    def get_fps(self) -> float:
        """
        获取当前帧率 / Get current FPS.

        Returns:
            当前帧率 / Current frames per second
        """
        self._frame_count += 1
        elapsed = time.time() - self._start_time

        if elapsed >= 1.0:  # 每秒更新一次 / Update every second
            self._last_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._start_time = time.time()

        return self._last_fps

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize a frame for display."""
        height, width = frame.shape[:2]
        new_height, new_width = int(height * self.scale), int(width * self.scale)
        return cv2.resize(frame, (new_width, new_height))

    def show_snapshot(self, frames: dict[str, np.ndarray]) -> None:
        """
        Show the latest frames from all streams.

        Note: cv2.waitKey must run in main thread, so this is synchronous.
        It only blocks 1ms which is negligible for video preview.

        Args:
            frames: Dictionary mapping stream names to frames
        """
        for name, frame in frames.items():
            if frame is None:
                continue

            window_name = f"Stream: {name}"
            if window_name not in self.windows:
                self.windows.add(window_name)
                cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

            resized = self._resize_frame(frame)
            cv2.imshow(window_name, resized)

        # 必须在主线程调用，1ms 阻塞可忽略 / Must run in main thread, 1ms is negligible
        cv2.waitKey(1)

    def show_batch(self, iter_data: VSIterData) -> None:
        """
        Show frames from a batch (showing the middle frame of each sequence).

        Note: cv2.waitKey must run in main thread, so this is synchronous.

        Args:
            iter_data: The iteration data containing frames
        """
        for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
            if not frames:
                continue

            # Show the middle frame of the sequence
            middle_idx = len(frames) // 2
            frame = frames[middle_idx]

            window_name = f"Stream: {name}"
            if window_name not in self.windows:
                self.windows.add(window_name)
                cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

            resized = self._resize_frame(frame)
            cv2.imshow(window_name, resized)

        cv2.waitKey(1)

    def close_all(self) -> None:
        """Close all OpenCV windows."""
        for window in self.windows:
            cv2.destroyWindow(window)
        self.windows.clear()
        cv2.destroyAllWindows()


async def preview_mode(
    streams: dict[str, str],
    scale: float = 0.5,
    fps: int = 5
) -> None:
    """
    Preview mode: Show real-time frames from all streams.

    This is useful for verifying stream connectivity before batch processing.

    Args:
        streams: Dictionary mapping stream names to RTSP URLs
        scale: Display scale factor
        fps: Target FPS for frame updates
    """
    coordinator = StreamCoordinator(streams)
    display = DisplayHandler(scale=scale)

    # 每个流的显示帧率统计 / Per-stream display FPS statistics
    stream_fps_stats: dict[str, dict] = {
        name: {"count": 0, "start_time": time.time(), "last_display_time": None}
        for name in streams
    }

    print("Starting preview mode...")
    print(f"Streams: {list(streams.keys())}")
    print("Press Ctrl+C to exit")
    print("时间戳格式: stream_name: OK(fps) @ timestamp / Timestamp format: stream_name: OK(fps) @ timestamp")

    await coordinator.initialize()

    try:
        while True:
            # 记录当前时间 / Record current time
            current_time = time.time()

            # Get latest frames of all streams (concurrent)
            vs_names, vs_frames = await coordinator.get_rt_frame()

            # Convert to dict for display
            frames = dict(zip(vs_names, vs_frames))

            # Display (cv2.waitKey must be in main thread, but only 1ms)
            display.show_snapshot(frames)

            # 打印每个流的显示时间戳 / Print display timestamp for each stream
            status_parts = []
            for name in streams.keys():
                if name in frames:
                    # 有帧显示 / Has frame to display
                    stream_fps_stats[name]["count"] += 1
                    stream_fps_stats[name]["last_display_time"] = current_time

                    # 计算帧率 / Calculate FPS
                    elapsed = current_time - stream_fps_stats[name]["start_time"]
                    if elapsed >= 1.0:
                        current_fps = stream_fps_stats[name]["count"] / elapsed
                        stream_fps_stats[name]["count"] = 0
                        stream_fps_stats[name]["start_time"] = current_time
                        stream_fps_stats[name]["last_fps"] = current_fps
                    else:
                        current_fps = stream_fps_stats[name].get("last_fps", 0.0)

                    status_parts.append(f"{name}: OK({current_fps:.1f}fps) @{current_time:.3f}")
                else:
                    # 没有帧 / No frame
                    last_time = stream_fps_stats[name].get("last_display_time")
                    if last_time:
                        time_since = current_time - last_time
                        status_parts.append(f"{name}: NO SIGNAL({time_since:.1f}s ago)")
                    else:
                        status_parts.append(f"{name}: NO SIGNAL")

            print(f"\r{', '.join(status_parts)}", end="", flush=True)

            # 控制帧率 / Control frame rate
            await asyncio.sleep(1 / fps)

    except asyncio.CancelledError:
        print("\nExiting preview mode...")
    finally:
        display.close_all()
        await coordinator.shutdown()


async def batch_processor_example(
    streams: dict[str, str]
) -> None:
    """
    Example of batch processing with a custom handler.

    Args:
        streams: Dictionary mapping stream names to RTSP URLs
    """
    display = DisplayHandler(scale=0.3)

    async def handle_batch(iter_data: VSIterData) -> None:
        """Process each batch of frames."""
        print(f"\n[Batch {len(iter_data.vs_names)} streams]")

        for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
            print(f"  {name}: {len(frames)} frames, shape: {frames[0].shape}")

        # Show middle frame from each stream
        display.show_batch(iter_data)

    print("Starting batch processing...")
    print("Press Ctrl+C to exit")

    try:
        await process_streams(streams, handler=handle_batch)
    except asyncio.CancelledError:
        print("\nStopping batch processing...")
    finally:
        display.close_all()


async def iterator_example(
    streams: dict[str, str]
) -> None:
    """
    Example of using the coordinator as an async iterator.

    Args:
        streams: Dictionary mapping stream names to RTSP URLs
    """
    coordinator = StreamCoordinator(streams)
    await coordinator.initialize()

    print(f"Initialized {len(coordinator.stream_names)} streams")
    print("Processing... Press Ctrl+C to exit\n")

    try:
        async for iter_data in coordinator:
            # Extract stream names and frames
            vs_names = iter_data.vs_names
            vs_frames = iter_data.vs_frames

            # Display data info
            print(f"视频流名称：{vs_names}")
            if vs_frames and vs_frames[0]:
                print(f"画面尺寸: {vs_frames[0][0].shape}")
            print()  # Empty line for readability

            # Your CV processing logic here
            # Example: object detection, frame analysis, etc.

    except asyncio.CancelledError:
        print("\nStopping...")
    finally:
        await coordinator.shutdown()


def setup_shutdown_handler() -> asyncio.Event:
    """Set up signal handler for graceful shutdown."""
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        print("\nShutdown signal received")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return shutdown_event


async def main_with_shutdown(coroutine, shutdown_event: asyncio.Event):
    """Run a coroutine with shutdown handling."""
    task = asyncio.create_task(coroutine)

    # Wait for either task completion or shutdown signal
    done, _ = await asyncio.wait(
        [task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED
    )

    if task not in done:
        # Task was cancelled due to shutdown
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def main():
    """Main entry point for example usage."""
    # Configure your streams here
    streams = {
        "stream_1": "rtsp://localhost:8554/video1",
        "stream_2": "rtsp://localhost:8554/video2"
    }

    # Choose which example to run:
    mode = "iterator"  # Options: "preview", "batch", "iterator"

    shutdown_event = setup_shutdown_handler()

    if mode == "preview":
        coroutine = preview_mode(streams)
    elif mode == "batch":
        coroutine = batch_processor_example(streams)
    elif mode == "iterator":
        coroutine = iterator_example(streams)
    else:
        print(f"Unknown mode: {mode}")
        return

    try:
        asyncio.run(main_with_shutdown(coroutine, shutdown_event))
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
