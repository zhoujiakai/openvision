"""
协程 vs 线程性能对比测试
Async vs Threading Performance Benchmark
"""
import asyncio
import psutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np

# 添加路径以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入异步版本
from override_codes.app.coordinator import StreamCoordinator as AsyncStreamCoordinator

# 导入线程版本
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.rtsp_client import RtspClient
from app.vs_manager import VSManager

from config import cfg


class PerformanceMonitor:
    """性能监控器 / Performance Monitor"""

    def __init__(self):
        self.process = psutil.Process()
        self.start_cpu = 0
        self.start_memory = 0
        self.start_time = 0

    def start(self):
        """开始监控 / Start monitoring"""
        self.start_time = time.time()
        self.start_cpu = self.process.cpu_percent()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB

    def stop(self):
        """停止监控并返回结果 / Stop and return results"""
        elapsed = time.time() - self.start_time
        cpu_percent = self.process.cpu_percent()
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        cpu_delta = cpu_percent - self.start_cpu
        memory_delta = memory_mb - self.start_memory

        return {
            "elapsed": elapsed,
            "cpu_percent": cpu_percent,
            "cpu_delta": cpu_delta,
            "memory_mb": memory_mb,
            "memory_delta_mb": memory_delta,
            "fps": self._calc_fps(elapsed)
        }

    def _calc_fps(self, elapsed: float) -> float:
        """计算FPS（将在测试中设置）"""
        return 0.0

    def set_frame_count(self, count: int):
        """设置帧数用于计算FPS / Set frame count for FPS calculation"""
        self.frame_count = count

    def _calc_fps(self, elapsed: float) -> float:
        return self.frame_count / elapsed if elapsed > 0 else 0.0


async def benchmark_async(
    streams: dict[str, str],
    duration: float = 10.0
) -> dict:
    """
    测试异步版本 / Benchmark async version

    Args:
        streams: 视频流配置
        duration: 测试时长（秒）

    Returns:
        性能指标字典
    """
    print("\n=== 测试异步版本 / Testing Async Version ===")
    monitor = PerformanceMonitor()
    monitor.start()

    coordinator = AsyncStreamCoordinator(streams)
    await coordinator.initialize()

    frame_count = 0
    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            vs_names, vs_frames = await coordinator.get_rt_frame()
            frame_count += len(vs_names)
            await asyncio.sleep(0.2)  # 模拟处理延迟
    finally:
        await coordinator.shutdown()

    monitor.set_frame_count(frame_count)
    results = monitor.stop()
    results["version"] = "async"
    results["frames_processed"] = frame_count

    return results


def benchmark_threading(
    streams: dict[str, str],
    duration: float = 10.0
) -> dict:
    """
    测试线程版本 / Benchmark threading version

    Args:
        streams: 视频流配置
        duration: 测试时长（秒）

    Returns:
        性能指标字典
    """
    print("\n=== 测试线程版本 / Testing Threading Version ===")

    # 使用线程池执行异步测试
    def run_benchmark():
        return asyncio.run(benchmark_async(streams, duration))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_benchmark)
        results = future.result()

    results["version"] = "threading"
    return results


def benchmark_vs_manager(
    streams: dict[str, str],
    duration: float = 10.0
) -> dict:
    """
    测试原始 VSManager (线程版本) / Benchmark original VSManager (threading)

    Args:
        streams: 视频流配置
        duration: 测试时长（秒）

    Returns:
        性能指标字典
    """
    print("\n=== 测试 VSManager (原始线程版本) / Testing VSManager (Original Threading) ===")

    monitor = PerformanceMonitor()
    monitor.start()

    vs_manager = VSManager(streams)

    frame_count = 0
    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            vs_names, vs_frames = vs_manager.get_rt_frame()
            frame_count += len(vs_names)
            time.sleep(0.2)  # 模拟处理延迟
    finally:
        vs_manager.stop_all_vs()

    monitor.set_frame_count(frame_count)
    results = monitor.stop()
    results["version"] = "vs_manager (threading)"
    results["frames_processed"] = frame_count

    return results


def print_comparison(results_list: list[dict]):
    """打印对比结果 / Print comparison results"""
    print("\n" + "=" * 80)
    print("性能对比结果 / Performance Comparison Results")
    print("=" * 80)

    print(f"{'指标 / Metric':<25} {'Async':<15} {'Threading':<15}")
    print("-" * 80)

    async_result = next((r for r in results_list if "async" in r["version"]), {})
    threading_result = next((r for r in results_list if "threading" in r["version"]), {})

    metrics = [
        ("FPS", "fps"),
        ("处理帧数 / Frames", "frames_processed"),
        ("CPU使用率 / CPU %", "cpu_percent"),
        ("内存使用 / Memory (MB)", "memory_mb"),
        ("耗时 / Elapsed (s)", "elapsed"),
    ]

    for label, key in metrics:
        async_val = async_result.get(key, 0)
        threading_val = threading_result.get(key, 0)

        # 格式化输出
        if key == "frames_processed":
            async_str = f"{async_val}"
            threading_str = f"{threading_val}"
        elif key == "memory_mb":
            async_str = f"{async_val:.1f}"
            threading_str = f"{threading_val:.1f}"
        else:
            async_str = f"{async_val:.2f}"
            threading_str = f"{threading_val:.2f}"

        print(f"{label:<25} {async_str:<15} {threading_str:<15}")

    print("=" * 80)


async def main():
    """主测试函数"""
    # 视频流配置
    streams = {
        "rtsp1": "rtsp://localhost:8554/video1",
        "rtsp2": "rtsp://localhost:8554/video2"
    }

    # 测试时长
    duration = 10.0

    print(f"性能测试配置 / Benchmark Config:")
    print(f"  测试时长 / Duration: {duration}秒")
    print(f"  视频流 / Streams: {list(streams.keys())}")
    print(f"  提示 / Tip: 请确保 mediamtx 和 ffmpeg 推流正在运行")

    input("\n按回车开始测试... / Press Enter to start...")

    # 运行测试
    results = []

    # 测试异步版本
    try:
        async_result = await benchmark_async(streams, duration)
        results.append(async_result)
    except Exception as e:
        print(f"异步版本测试失败 / Async version failed: {e}")

    # 测试 VSManager (原始线程版本)
    try:
        threading_result = benchmark_vs_manager(streams, duration)
        results.append(threading_result)
    except Exception as e:
        print(f"线程版本测试失败 / Threading version failed: {e}")

    # 打印对比
    if len(results) >= 2:
        print_comparison(results)
    else:
        print("\n测试失败，无法对比 / Tests failed, cannot compare")


if __name__ == "__main__":
    asyncio.run(main())
