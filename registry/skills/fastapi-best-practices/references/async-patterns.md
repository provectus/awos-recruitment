# Async Patterns in FastAPI

## How FastAPI Handles Routes

FastAPI is async-first but supports both sync and async route handlers with different execution models.

### Sync routes (`def`)

FastAPI runs sync routes in a **threadpool**. Blocking I/O in a sync route blocks only the worker thread, not the event loop — other requests continue being processed.

```python
@router.get("/sync")
def sync_route():
    time.sleep(10)  # Blocks worker thread, NOT the event loop
    return {"done": True}
```

### Async routes (`async def`)

Async routes run directly on the event loop. If you perform blocking I/O here, the **entire event loop stalls** — no other requests can be handled until the blocking call finishes.

```python
# WRONG — blocks the entire event loop for 10 seconds
@router.get("/terrible")
async def terrible():
    time.sleep(10)
    return {"done": True}

# CORRECT — non-blocking, event loop handles other requests while waiting
@router.get("/perfect")
async def perfect():
    await asyncio.sleep(10)
    return {"done": True}
```

## Threadpool Caveats

- Threads are more expensive than coroutines — they consume more memory and have scheduling overhead.
- The threadpool has a **limited number of workers** (default: `min(32, os.cpu_count() + 4)`). If all workers are busy with slow sync routes, new requests queue up.
- For high-throughput scenarios, prefer async routes with async drivers (e.g., `asyncpg`, `aiohttp`, `httpx`).

## CPU-Intensive Tasks

Neither async routes nor threadpool offloading help with CPU-bound work:

- **Awaiting CPU work** is useless — the CPU must actively compute; there's nothing to "wait" for.
- **Threads don't help** due to the GIL — only one thread executes Python bytecode at a time.

Solutions for CPU-intensive tasks:

```python
# Option 1: run_in_executor with ProcessPoolExecutor
import asyncio
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)

@router.get("/compute")
async def compute():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, heavy_computation, data)
    return {"result": result}

# Option 2: Offload to a task queue (Celery, Dramatiq, etc.)
@router.post("/transcode")
async def transcode(video_id: UUID4):
    task = celery_app.send_task("transcode_video", args=[str(video_id)])
    return {"task_id": task.id}
```

## Using Sync Libraries in Async Routes

When you must call a sync SDK from an async route, use `run_in_threadpool` from Starlette:

```python
from fastapi.concurrency import run_in_threadpool

@router.get("/")
async def call_sync_library():
    my_data = await service.get_my_data()
    client = SyncAPIClient()
    result = await run_in_threadpool(client.make_request, data=my_data)
    return result
```

This is equivalent to `asyncio.to_thread()` but integrated with Starlette's threadpool.

## Decision Matrix

| Scenario | Route type | Why |
|---|---|---|
| Async DB driver (asyncpg, motor) | `async def` | Native async — most efficient |
| Sync DB driver (psycopg2) | `def` | Threadpool prevents event loop blocking |
| External async HTTP (httpx) | `async def` | Native async |
| Sync HTTP library in async route | `run_in_threadpool()` | Bridges sync→async safely |
| File I/O (small files) | `def` | Threadpool is fine for short blocking |
| Heavy computation | Process pool or task queue | GIL prevents thread-based parallelism |
| Async + one sync call | `async def` + `run_in_threadpool` | Keep route async, offload sync part |
