# Async RTSP Stream Processor

异步 RTSP 视频流处理器 - 基于 asyncio 的现代库，用于管理多个 RTSP 视频流并进行同步帧批次处理。

A modern, asyncio-based library for managing multiple RTSP video streams with synchronized frame batch processing.

## Features / 特性

- **Async/Await Architecture**: Built on Python's `asyncio` for efficient concurrent I/O / 基于 asyncio 的异步架构
- **Synchronized Batch Processing**: Collects frame batches from multiple streams simultaneously / 同步批次处理
- **Flexible Configuration**: YAML-based configuration with type safety / 灵活的配置系统
- **Automatic Reconnection**: Handles RTSP stream disconnections gracefully / 自动重连
- **Frame Validation**: Built-in frame quality checking / 帧验证

## Installation / 安装

```bash
# 使用 uv (推荐) / Using uv (recommended)
uv sync

# 或使用 pip / Or using pip
pip install -r requirements.txt
```

## Quick Start / 快速开始

### Simple Example / 简单示例

```python
import asyncio
from override_codes.app.coordinator import StreamCoordinator
from config import cfg

async def main():
    # 使用配置文件中的视频流 / Use streams from config file
    coordinator = StreamCoordinator(cfg.vs.VS)
    await coordinator.initialize()

    try:
        async for iter_data in coordinator:
            # iter_data.vs_names: 视频流名称列表 / List of stream names
            # iter_data.vs_frames: 对应的帧序列列表 / Corresponding frame sequences
            for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
                print(f"{name}: {len(frames)} frames")
                # 你的 CV 处理代码 / Your CV processing code here
    finally:
        await coordinator.shutdown()

asyncio.run(main())
```

### Preview Mode - Real-time Frame Display / 预览模式

```python
import asyncio
from override_codes.app.coordinator import StreamCoordinator
from config import cfg

async def preview():
    coordinator = StreamCoordinator(cfg.vs.VS)
    await coordinator.initialize()

    try:
        while True:
            # 获取所有流的最新帧 / Get latest frames from all streams
            vs_names, vs_frames = await coordinator.get_rt_frame()
            # 处理或显示帧 / Process or display frames
            await asyncio.sleep(0.1)
    finally:
        await coordinator.shutdown()

asyncio.run(preview())
```

### Using the Convenience Function / 使用便捷函数

```python
import asyncio
from override_codes.app.coordinator import process_streams
from config import cfg

async def handler(iter_data):
    """Called for each batch of frames / 为每批帧调用"""
    for name, frames in zip(iter_data.vs_names, iter_data.vs_frames):
        print(f"{name}: {len(frames)} frames")

async def main():
    await process_streams(cfg.vs.VS, handler=handler)

asyncio.run(main())
```

## Configuration / 配置

配置通过 YAML 文件 (`config.yaml`) 加载：

```yaml
# Video Stream Settings / 视频流设置
vs:
  FPS: 5                # 每个视频流保存的帧率 / Frames per second
  ITER_SEC: 6           # 缓冲帧的持续时间（秒）/ Buffer duration in seconds
  SEQ: 30               # 需要缓冲的帧数 (FPS × ITER_SEC)
  ITER_RATE: 1.0        # 迭代缓冲系数 / Iteration buffer factor

  # 视频流配置 / Stream configuration
  VS:
    rtsp1: "rtsp://localhost:8554/video1"
    rtsp2: "rtsp://localhost:8554/video2"

# RTSP Connection Settings / RTSP 连接设置
rtsp:
  iteration_timeout: 10.0  # 等待所有流的最大秒数
  frame_timeout: 5.0       # 无新帧认为流过时的秒数
  retry_interval: 1.0      # 重试失败连接的等待秒数
```

### Accessing Configuration / 访问配置

```python
from config import cfg

# 访问配置值 / Access configuration values
print(cfg.vs.FPS)            # 5
print(cfg.vs.ITER_SEC)       # 6
print(cfg.vs.VS)             # {'rtsp1': 'rtsp://...', ...}
print(cfg.rtsp.frame_timeout)  # 5.0
```

## Architecture / 架构

### Design Principles / 设计原则

1. **Async-First**: Uses async/await throughout / 异步优先
2. **Type-Safe**: Leverages Python type hints / 类型安全
3. **Modular**: Separation of concerns / 模块化设计
4. **Resource-Safe**: Proper cleanup with async context management / 资源安全

### Module Structure / 模块结构

```
override_codes/
├── __init__.py           # Package exports / 包导出
├── config.py             # Configuration management / 配置管理
├── logger.py             # Logging utilities / 日志工具
├── app/
│   ├── coordinator.py    # StreamCoordinator and VSIterData
│   └── stream_reader.py  # AsyncStreamReader and StreamReaderPool
├── main.py               # Advanced examples / 高级示例
├── example_simple.py     # Simple example / 简单示例
├── ARCHITECTURE.md       # Architecture documentation / 架构文档
└── requirements.txt      # Dependencies / 依赖
```

### Key Differences from Threaded Implementations / 与线程实现的区别

| Aspect / 方面 | This Implementation | Traditional |
|---------------|---------------------|-------------|
| Concurrency / 并发 | asyncio | threading |
| Frame Collection / 帧收集 | Dual async tasks | Dual threads |
| Iteration / 迭代 | Async iterator (`__anext__`) | Sync iterator |
| Resource Management / 资源管理 | Async cleanup | Manual cleanup |

## API Reference / API 参考

### StreamCoordinator

Main class for managing multiple streams / 管理多个视频流的主类。

**Methods / 方法:**

| Method | Description |
|--------|-------------|
| `await initialize()` | 启动所有视频流 / Start all streams |
| `await shutdown()` | 停止所有视频流 / Stop all streams |
| `async for iter_data in coordinator` | 迭代帧批次 / Iterate over frame batches |
| `await get_snapshot()` | 获取所有流的最新帧（字典形式）/ Get latest frames as dict |
| `await get_rt_frame()` | 获取所有流的最新帧（元组形式）/ Get latest frames as tuple |

### VSIterData

Data container for frame batches / 帧批次数据容器。

**Properties / 属性:**

| Property | Type | Description |
|----------|------|-------------|
| `vs_names` | `list[str]` | 视频流名称列表 |
| `vs_frames` | `list[list[np.ndarray]]` | 对应的帧序列 |
| `timestamp` | `datetime` | 批次收集时间 |

### AsyncStreamReader

Single stream reader / 单流读取器。

**Properties / 属性:**

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | 流名称 |
| `buffer_size` | `int` | 缓冲区大小 |
| `is_running` | `bool` | 是否运行中 |
| `is_stale` | `bool` | 是否超时无新帧 |
| `stats` | `StreamStats` | 流统计信息 |

**Methods / 方法:**

| Method | Description |
|--------|-------------|
| `await start()` | 启动流读取 |
| `await stop()` | 停止流读取 |
| `await get_buffered_frames()` | 获取并清空缓冲帧 |
| `await get_latest_frame()` | 获取最新帧 |

## License

MIT License
