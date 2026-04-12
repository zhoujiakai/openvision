# Architecture Comparison

## Original Implementation (Threaded)

```
┌─────────────────────────────────────────────────────────────────┐
│                      MultiCameraManager                         │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  CameraStream 1 │    │  CameraStream 2 │    ...            │
│  │  ┌───────────┐  │    │  ┌───────────┐  │                    │
│  │  │  Thread  │  │    │  │  Thread  │  │                    │
│  │  │ _decode  │──┼───┬┼──│ _decode  │──┼───┬                │
│  │  └───────────┘  │   ││  └───────────┘  │   │                │
│  │  ┌───────────┐  │   ││  ┌───────────┐  │   │                │
│  │  │  Thread  │  │   ││  │  Thread  │  │   │                │
│  │  │_queue    │──┼───┼┼──│_queue    │──┼───┼──> Queue       │
│  │  └───────────┘  │   ││  └───────────┘  │   │                │
│  │  [deque buffer] │   ││  [deque buffer] │   │                │
│  └─────────────────┘   ││  └─────────────────┘   │                │
│                        ││                        │                │
│                  ┌─────┼────────────────────────┼────┐           │
│                  │     │      Iterator          │    │           │
│                  │     │   (synchronous)        │    │           │
│                  └─────┼────────────────────────┼────┘           │
└────────────────────────┼────────────────────────┼────────────────┘
                         │                        │
                    Blocking I/O              Blocking I/O
```

**Key Characteristics:**
- Dual-thread per stream (decode + queue)
- Synchronous iteration (`__next__`)
- `deque` for frame buffering
- `threading.Lock` for synchronization
- Blocking OpenCV calls

## New Implementation (Async)

```
┌────────────────────────────────────────────────────────────────────┐
│                       StreamCoordinator                            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    StreamReaderPool                           │ │
│  │                                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐      ┌──────────────┐   │ │
│  │  │AsyncStream 1 │  │AsyncStream 2 │  ... │AsyncStream N │   │ │
│  │  │              │  │              │      │              │   │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │      │  ┌────────┐  │   │ │
│  │  │  │  Task  │──┼──┼──│  Task  │──┼──────┼──│  Task  │──┼───┼──> FrameBatch
│  │  │  │_read   │  │  │  │_read   │  │      │  │_read   │  │   │ │
│  │  │  └────────┘  │  │  └────────┘  │      │  └────────┘  │   │ │
│  │  │  [list buffer]│  │[list buffer]│      │[list buffer]│   │ │
│  │  └──────────────┘  └──────────────┘      └──────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                        ┌─────┴─────┐                               │
│                        │  Async    │                               │
│                        │ Iterator  │                               │
│                        │(__anext__)│                               │
│                        └───────────┘                               │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                            Non-blocking I/O
                            (asyncio.to_thread)
```

**Key Characteristics:**
- Single async task per stream (decode + rate-limited buffering)
- Asynchronous iteration (`__anext__`)
- List for frame buffering
- `asyncio.Lock` for synchronization
- Non-blocking OpenCV calls (via `asyncio.to_thread`)

## Architectural Differences Summary

| Aspect | Threaded Version | Async Version |
|--------|------------------|---------------|
| **Concurrency Model** | `threading.Thread` | `asyncio.Task` |
| **Tasks per Stream** | 2 threads (decode + queue) | 1 async task |
| **Iteration** | Synchronous `__next__` | Asynchronous `__anext__` |
| **I/O Handling** | Blocking OpenCV calls | Non-blocking via `asyncio.to_thread` |
| **Synchronization** | `threading.Lock` | `asyncio.Lock` |
| **Buffer Type** | `collections.deque` | `list` with trimming |
| **Context Switching** | OS-level (expensive) | Event loop (cheap) |
| **Memory Profile** | Higher (thread stacks) | Lower (tasks) |
| **CPU Utilization** | Can cause contention | Efficient for I/O-bound |

## Data Flow Comparison

### Threaded Version
```
OpenCV.read() → Thread 1 → self.image
                              ↓
                     Thread 2 (rate-limited)
                              ↓
                        self.frame_queue (deque)
                              ↓
                        get_frames() clears queue
```

### Async Version
```
OpenCV.read() → asyncio.to_thread → self._latest_frame
                                            ↓
                                    Single Task (rate-limited)
                                            ↓
                                      self._buffer (list)
                                            ↓
                                  get_buffered_frames() clears buffer
```

## Benefits of Async Architecture

1. **Lower Resource Overhead**: Single task vs dual threads per stream
2. **Better Scalability**: Can handle more streams concurrently
3. **Cleaner Error Handling**: Async/await pattern for exception propagation
4. **Type Safety**: Modern Python type hints throughout
5. **Easier Testing**: Async patterns are more testable with async mocks
6. **Modern Practices**: Aligns with current Python async ecosystem
