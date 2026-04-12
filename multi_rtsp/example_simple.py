"""
Simple example demonstrating the async RTSP processor.

演示异步RTSP处理器的简单示例。
"""
import asyncio
from override_codes.app.coordinator import StreamCoordinator
from override_codes.config import cfg
from logger import create_logger

logger = create_logger("main")


async def main():
    """简单使用示例 / Simple usage example."""

    # 创建并初始化协调器 / Create and initialize coordinator
    coordinator = StreamCoordinator(cfg.vs.VS)
    results = await coordinator.initialize()

    print(f"初始化结果 / Initialization results: {results}")
    print(f"活跃视频流 / Active streams: {coordinator.stream_names}")
    print("\n开始迭代... 按 Ctrl+C 停止 / Starting iteration... Press Ctrl+C to stop\n")

    try:
        async for iter_data in coordinator:
            # 提取视频流名称和帧 / Extract stream names and frames
            vs_names = iter_data.vs_names
            vs_frames = iter_data.vs_frames

            # 显示数据信息 / Display data info
            print(f"视频流名称 / Stream names：{vs_names}")
            if vs_frames and vs_frames[0]:
                print(f"画面尺寸 / Frame shape: {vs_frames[0][0].shape}")

            # 你的CV处理代码放在这里 / Your CV processing code goes here
            # 示例：对每一帧运行目标检测 / Example: run object detection on each frame

    except KeyboardInterrupt:
        print("\n\n停止中 / Stopping...")
    finally:
        await coordinator.shutdown()
        print("关闭完成 / Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
