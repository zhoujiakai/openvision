"""
协程 vs 线程性能对比测试 (简化版)
Async vs Threading Performance Benchmark (Simplified)

分别运行两个版本，记录性能数据
Run both versions separately and record performance data
"""
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入异步版本
from override_codes.app.coordinator import StreamCoordinator


@dataclass
class BenchmarkResult:
    """性能测试结果"""
    version: str
    duration: float
    total_frames: int
    avg_fps: float
    streams_count: int


class PreviewBenchmark:
    """预览模式性能测试"""

    def __init__(self, streams: dict[str, str], duration: float = 10.0):
        self.streams = streams
        self.duration = duration
        self.results = []

    async def run_async(self) -> BenchmarkResult:
        """运行异步版本测试"""
        print(f"\n{'='*60}")
        print("测试异步版本 / Testing Async Version")
        print(f"{'='*60}")

        from override_codes.app.coordinator import StreamCoordinator

        coordinator = StreamCoordinator(self.streams)
        await coordinator.initialize()

        start_time = time.time()
        total_frames = 0
        iteration = 0

        print("开始测试... / Starting test...")

        try:
            while time.time() - start_time < self.duration:
                vs_names, vs_frames = await coordinator.get_rt_frame()
                total_frames += len(vs_names)
                iteration += 1

                # 每2秒打印一次状态
                if iteration % 10 == 0:
                    elapsed = time.time() - start_time
                    current_fps = total_frames / elapsed if elapsed > 0 else 0
                    print(f"  [{iteration}] 已运行/Elapsed: {elapsed:.1f}s, "
                          f"帧数/Frames: {total_frames}, FPS: {current_fps:.1f}")

                await asyncio.sleep(0.2)

        finally:
            await coordinator.shutdown()

        elapsed = time.time() - start_time
        avg_fps = total_frames / elapsed if elapsed > 0 else 0

        result = BenchmarkResult(
            version="Async (协程)",
            duration=elapsed,
            total_frames=total_frames,
            avg_fps=avg_fps,
            streams_count=len(self.streams)
        )

        self._print_result(result)
        return result

    def run_threading(self) -> BenchmarkResult:
        """运行线程版本测试"""
        print(f"\n{'='*60}")
        print("测试线程版本 / Testing Threading Version")
        print(f"{'='*60}")

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from app.vs_manager import VSManager

        vs_manager = VSManager(self.streams)

        start_time = time.time()
        total_frames = 0
        iteration = 0

        print("开始测试... / Starting test...")

        try:
            while time.time() - start_time < self.duration:
                vs_names, vs_frames = vs_manager.get_rt_frame()
                total_frames += len(vs_names)
                iteration += 1

                # 每2秒打印一次状态
                if iteration % 10 == 0:
                    elapsed = time.time() - start_time
                    current_fps = total_frames / elapsed if elapsed > 0 else 0
                    print(f"  [{iteration}] 已运行/Elapsed: {elapsed:.1f}s, "
                          f"帧数/Frames: {total_frames}, FPS: {current_fps:.1f}")

                time.sleep(0.2)

        finally:
            vs_manager.stop_all_vs()

        elapsed = time.time() - start_time
        avg_fps = total_frames / elapsed if elapsed > 0 else 0

        result = BenchmarkResult(
            version="Threading (线程)",
            duration=elapsed,
            total_frames=total_frames,
            avg_fps=avg_fps,
            streams_count=len(self.streams)
        )

        self._print_result(result)
        return result

    def _print_result(self, result: BenchmarkResult):
        """打印单个结果"""
        print(f"\n结果 / Results:")
        print(f"  版本 / Version:        {result.version}")
        print(f"  时长 / Duration:        {result.duration:.2f} 秒")
        print(f"  处理帧数 / Total Frames: {result.total_frames}")
        print(f"  平均FPS / Avg FPS:      {result.avg_fps:.2f}")
        print(f"  流数量 / Stream Count:  {result.streams_count}")

    def compare(self, result1: BenchmarkResult, result2: BenchmarkResult):
        """对比两个结果"""
        print(f"\n{'='*60}")
        print("性能对比 / Performance Comparison")
        print(f"{'='*60}")

        print(f"{'指标 / Metric':<20} {'Async':<15} {'Threading':<15} {'差异 / Diff'}")
        print("-" * 65)

        # FPS 对比
        fps_diff = result1.avg_fps - result2.avg_fps
        fps_diff_pct = (fps_diff / result2.avg_fps * 100) if result2.avg_fps > 0 else 0
        print(f"{'FPS (帧率)':<20} {result1.avg_fps:<15.2f} {result2.avg_fps:<15.2f} "
              f"{fps_diff:+.2f} ({fps_diff_pct:+.1f}%)")

        # 总帧数对比
        frames_diff = result1.total_frames - result2.total_frames
        frames_diff_pct = (frames_diff / result2.total_frames * 100) if result2.total_frames > 0 else 0
        print(f"{'总帧数 / Total Frames':<20} {result1.total_frames:<15} {result2.total_frames:<15} "
              f"{frames_diff:+d} ({frames_diff_pct:+.1f}%)")

        # 结论
        print("\n结论 / Conclusion:")
        if abs(fps_diff_pct) < 5:
            print("  两者性能接近 / Both versions have similar performance")
        elif fps_diff_pct > 0:
            print(f"  Async 版本快 {fps_diff_pct:.1f}% / Async version is {fps_diff_pct:.1f}% faster")
        else:
            print(f"  Threading 版本快 {abs(fps_diff_pct):.1f}% / Threading version is {abs(fps_diff_pct):.1f}% faster")


def main():
    """主函数"""
    streams = {
        "rtsp1": "rtsp://localhost:8554/video1",
        "rtsp2": "rtsp://localhost:8554/video2"
    }

    duration = 15.0

    print("=" * 60)
    print("协程 vs 线程性能对比测试")
    print("Async vs Threading Performance Benchmark")
    print("=" * 60)
    print(f"\n配置 / Config:")
    print(f"  测试时长 / Duration: {duration}秒")
    print(f"  视频流 / Streams: {list(streams.keys())}")
    print(f"\n请确保 / Ensure:")
    print(f"  1. mediamtx 正在运行")
    print(f"  2. ffmpeg 正在推流到 video1 和 video2")

    input("\n按回车开始测试 Async 版本... / Press Enter to test Async version...")

    benchmark = PreviewBenchmark(streams, duration)

    # 测试异步版本
    try:
        async_result = asyncio.run(benchmark.run_async())
    except Exception as e:
        print(f"Async 版本测试失败 / Async version failed: {e}")
        import traceback
        traceback.print_exc()
        async_result = None

    input("\n按回车开始测试 Threading 版本... / Press Enter to test Threading version...")

    # 测试线程版本
    try:
        threading_result = benchmark.run_threading()
    except Exception as e:
        print(f"Threading 版本测试失败 / Threading version failed: {e}")
        import traceback
        traceback.print_exc()
        threading_result = None

    # 对比结果
    if async_result and threading_result:
        benchmark.compare(async_result, threading_result)


if __name__ == "__main__":
    main()
