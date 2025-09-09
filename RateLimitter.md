# Algorithms: Fixed Window, Sliding Window (log & counter), Token Bucket, Leaky Bucket

Reference: [ByteByteGo → System Design → Rate Limiter](https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter)

In a network system, a rate limiter is used to control the rate of traffic sent by a client or a service. In the HTTP world, a rate limiter limits the number of client requests allowed to be sent over a specified period. If the API request count exceeds the threshold defined by the rate limiter, all the excess calls are blocked.The HTTP 429 response status code indicates a user has sent too many requests.

Prevent resource starvation caused by Denial of Service (DoS) attack [1].

 Almost all APIs published by large tech companies enforce some form of rate limiting. For example, Twitter limits the number of tweets to 300 per 3 hours [2].

 Google Docs APIs have the following default limit: 300 per user per 60 seconds for read requests [3].

A rate limiter prevents DoS attacks, either intentional or unintentional, by blocking the excess calls

## Algorithms for rate limiting

list of popular algorithms:

* Token bucket

* Leaking bucket

* Fixed window counter

* Sliding window log

* Sliding window counter

Building your own rate limiting service takes time. If you do not have enough engineering resources to implement a rate limiter, a commercial API gateway is a better option

* Sync/Async APIs: allow() / retry_after() / acquire() and aallow() / aretry_after() / aacquire().

* Thread-safe in-memory implementations via locks.

* Per-key limits (e.g., per user, IP, route) by passing key.

* Decorators @rate_limited and @arate_limited with optional blocking or drop handlers.

* Retry-After helpers for polite backoff.

* Redis implementation for distributed/process-safe sliding window (optional).

## Quick picks

Need bursts + smooth average → TokenBucketRateLimiter.

Need exact sliding window → SlidingWindowLogRateLimiter.

Need low memory, smooth edges → SlidingWindowCounterRateLimiter.

Need simple & fast → FixedWindowRateLimiter.

Need constant outflow / queueing → LeakyBucketRateLimiter

```python
# ratelimit.py
# Python 3.9+

from __future__ import annotations
import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional, Tuple, Any, Iterable, Union

try:
    import asyncio
except Exception:  # pragma: no cover
    asyncio = None  # type: ignore


# ---------------------------
# Common types / base class
# ---------------------------

@dataclass(frozen=True)
class Limit:
    """A limit of 'n' events per 'per' seconds."""
    n: int
    per: float

class RateLimiter:
    """Base interface for all limiters."""
    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        raise NotImplementedError

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        """Seconds until the next event is allowed (0 if allowed now)."""
        raise NotImplementedError

    def acquire(self, key: str = "global") -> None:
        """Block until allowed (synchronous)."""
        while True:
            if self.allow(key):
                return
            time.sleep(min(0.1, max(0.0, self.retry_after(key))))

    async def aallow(self, key: str = "global", now: Optional[float] = None) -> bool:
        """Async equivalent of allow (default: wrap sync)."""
        return self.allow(key, now)

    async def aretry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        return self.retry_after(key, now)

    async def aacquire(self, key: str = "global") -> None:
        """Async block until allowed."""
        while True:
            if await self.aallow(key):
                return
            wait = await self.aretry_after(key)
            await asyncio.sleep(min(0.1, max(0.0, wait)))


# ---------------------------
# Fixed Window
# ---------------------------

class FixedWindowRateLimiter(RateLimiter):
    """
    Allows up to Limit.n events per Limit.per seconds using fixed windows.
    Pros: simple, fast. Cons: bursty at window boundaries.
    """
    def __init__(self, limit: Limit):
        self.limit = limit
        self._lock = threading.Lock()
        self._window_start: Dict[str, float] = defaultdict(float)
        self._count: Dict[str, int] = defaultdict(int)

    def _current_window(self, now: float) -> float:
        return now - (now % self.limit.per)

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            w = self._current_window(now)
            if self._window_start[key] != w:
                self._window_start[key] = w
                self._count[key] = 0
            if self._count[key] < self.limit.n:
                self._count[key] += 1
                return True
            return False

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        with self._lock:
            w = self._current_window(now)
            if self._window_start[key] != w or self._count[key] < self.limit.n:
                return 0.0
            return (self._window_start[key] + self.limit.per) - now


# ---------------------------
# Sliding Window (Log)
# ---------------------------

class SlidingWindowLogRateLimiter(RateLimiter):
    """
    Exact sliding window using timestamps.
    Pros: precise. Cons: memory O(requests in window).
    """
    def __init__(self, limit: Limit):
        self.limit = limit
        self._lock = threading.Lock()
        self._events: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            q = self._events[key]
            # drop old
            cutoff = now - self.limit.per
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) < self.limit.n:
                q.append(now)
                return True
            return False

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        with self._lock:
            q = self._events[key]
            if not q or len(q) < self.limit.n:
                return 0.0
            # when the oldest event falls out of window
            return max(0.0, (q[0] + self.limit.per) - now)


# ---------------------------
# Sliding Window (Counter)
# ---------------------------

class SlidingWindowCounterRateLimiter(RateLimiter):
    """
    Approximate sliding window using two adjacent fixed windows (smooths boundary bursts).
    Pros: O(1) space per key. Cons: off by up to one window's interpolation.
    """
    def __init__(self, limit: Limit):
        self.limit = limit
        self._lock = threading.Lock()
        self._win_start: Dict[str, float] = defaultdict(float)
        self._counts: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))  # (cur, prev)

    def _win(self, now: float) -> float:
        return now - (now % self.limit.per)

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            cur_start = self._win(now)
            start = self._win_start[key]
            cur, prev = self._counts[key]
            if start != cur_start:
                # shift windows
                prev = cur if start == cur_start - self.limit.per else 0
                cur = 0
                start = cur_start
                self._win_start[key] = start
            # effective count (interpolated)
            elapsed = (now - start) / self.limit.per
            effective = cur + prev * (1 - elapsed)
            if effective < self.limit.n:
                cur += 1
                self._counts[key] = (cur, prev)
                return True
            return False

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        with self._lock:
            start = self._win_start[key]
            cur, prev = self._counts[key]
            if start == 0:
                return 0.0
            elapsed = (now - start) / self.limit.per
            effective = cur + prev * (1 - elapsed)
            if effective < self.limit.n:
                return 0.0
            # numerical solve: when effective drops below n
            # prev*(1 - e) + cur = n  -> e = 1 - (n - cur)/prev
            if prev <= 0:
                # must wait until next window starts
                return max(0.0, (start + self.limit.per) - now)
            e = 1 - (self.limit.n - cur) / max(prev, 1e-9)
            e = max(e, elapsed)
            target = start + e * self.limit.per
            return max(0.0, target - now)


# ---------------------------
# Token Bucket
# ---------------------------

class TokenBucketRateLimiter(RateLimiter):
    """
    Tokens accumulate at rate=n/per up to capacity (burst). One event consumes 1 token.
    Pros: smooth average rate, supports bursts.
    """
    def __init__(self, rate: Limit, capacity: Optional[int] = None):
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate.n
        self._lock = threading.Lock()
        self._tokens: Dict[str, float] = defaultdict(lambda: float(self.capacity))
        self._ts: Dict[str, float] = defaultdict(time.time)

    def _refill(self, key: str, now: float) -> None:
        last = self._ts[key]
        if now > last:
            delta = now - last
            self._tokens[key] = min(self.capacity, self._tokens[key] + delta * (self.rate.n / self.rate.per))
            self._ts[key] = now

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            self._refill(key, now)
            if self._tokens[key] >= 1.0:
                self._tokens[key] -= 1.0
                return True
            return False

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        with self._lock:
            self._refill(key, now)
            need = 1.0 - self._tokens[key]
            if need <= 0:
                return 0.0
            rate_per_sec = self.rate.n / self.rate.per
            return max(0.0, need / rate_per_sec)


# ---------------------------
# Leaky Bucket (Queue)
# ---------------------------

class LeakyBucketRateLimiter(RateLimiter):
    """
    Queue of pending events drained at constant rate (n/per).
    Pros: smooth output. Cons: can queue (adds latency).
    allow() returns True if admitted to queue, False if queue at capacity.
    """
    def __init__(self, rate: Limit, max_queue: int = 1000):
        self.rate = rate
        self.interval = rate.per / rate.n
        self.max_queue = max_queue
        self._lock = threading.Lock()
        self._next_free: Dict[str, float] = defaultdict(lambda: 0.0)
        self._size: Dict[str, int] = defaultdict(int)

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        with self._lock:
            if self._size[key] >= self.max_queue:
                return False
            nf = self._next_free[key]
            schedule = max(now, nf)
            self._next_free[key] = schedule + self.interval
            self._size[key] += 1
            return True

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        with self._lock:
            nf = self._next_free[key]
            return max(0.0, nf - now)

    def drain_notice(self, key: str = "global") -> float:
        """Approximate time until one queued event finishes (useful for Retry-After)."""
        with self._lock:
            return self.interval


# ---------------------------
# Decorators / helpers
# ---------------------------

def rate_limited(
    limiter: RateLimiter,
    key_fn: Optional[Callable[..., str]] = None,
    block: bool = False,
    on_dropped: Optional[Callable[..., Any]] = None,
):
    """
    Decorate a function to rate limit calls.
    - key_fn(*args, **kwargs)->str controls per-key limiting (default 'global').
    - block=True will sleep until allowed; else, if denied and on_dropped given, call it.
    """
    def decorator(fn: Callable):
        def wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs) if key_fn else "global"
            if block:
                limiter.acquire(k)
                return fn(*args, **kwargs)
            else:
                if limiter.allow(k):
                    return fn(*args, **kwargs)
                if on_dropped:
                    return on_dropped(*args, **kwargs)
                raise RuntimeError("Rate limited")
        return wrapper
    return decorator


def arate_limited(
    limiter: RateLimiter,
    key_fn: Optional[Callable[..., str]] = None,
    block: bool = False,
    on_dropped: Optional[Callable[..., Any]] = None,
):
    """
    Async decorator variant. Works with limiter.aallow/aacquire.
    """
    def decorator(fn: Callable):
        async def wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs) if key_fn else "global"
            if block:
                await limiter.aacquire(k)
                return await fn(*args, **kwargs)
            else:
                if await limiter.aallow(k):
                    return await fn(*args, **kwargs)
                if on_dropped:
                    return await on_dropped(*args, **kwargs)  # type: ignore
                raise RuntimeError("Rate limited")
        return wrapper
    return decorator


# ---------------------------
# Redis backend (distributed)
# ---------------------------

class RedisSlidingWindowCounter(RateLimiter):
    """
    Distributed sliding window counter using Redis.
    Requires 'redis' (pip install redis). Keys are namespaced.
    Uses Lua to atomically update counts.
    """
    LUA = """
    -- KEYS[1]=cur_key, KEYS[2]=prev_key
    -- ARGV[1]=now_start, ARGV[2]=prev_start, ARGV[3]=expire, ARGV[4]=limit_n
    local cur = redis.call('INCR', KEYS[1])
    if cur == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[3]) end
    local prev = tonumber(redis.call('GET', KEYS[2]) or '0')
    local now_start = tonumber(ARGV[1])
    local prev_start = tonumber(ARGV[2])
    local elapsed = (redis.call('PTTL', KEYS[1]) and 1.0 - (redis.call('PTTL', KEYS[1]) / tonumber(ARGV[3]))) or 0
    -- effective = cur + prev*(1 - elapsed)
    local effective = cur + prev * (1 - elapsed)
    if effective <= tonumber(ARGV[4]) then
        return {1, 0}  -- allowed
    else
        return {0, 1}  -- denied
    end
    """

    def __init__(self, redis_client, limit: Limit, namespace: str = "rl"):
        self.r = redis_client
        self.limit = limit
        self.ns = namespace
        self._script = self.r.register_script(self.LUA)

    def _keys(self, key: str, start_ms: int) -> Tuple[str, str]:
        cur_key = f"{self.ns}:{key}:{start_ms}"
        prev_key = f"{self.ns}:{key}:{start_ms - int(self.limit.per * 1000)}"
        return cur_key, prev_key

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        now = now or time.time()
        start = int((now - (now % self.limit.per)) * 1000)
        cur_key, prev_key = self._keys(key, start)
        expire = int(self.limit.per * 1000 * 2)
        allowed, _ = self._script(keys=[cur_key, prev_key],
                                  args=[start, start - int(self.limit.per * 1000), expire, self.limit.n])
        return bool(allowed)

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        now = now or time.time()
        start = int((now - (now % self.limit.per)) * 1000)
        cur_key = f"{self.ns}:{key}:{start}"
        ttl = self.r.pttl(cur_key)
        if ttl is None or ttl < 0:
            return 0.0
        # best-effort: wait until window advances
        return ttl / 1000.0


# ---------------------------
# Convenience factories
# ---------------------------

def fixed(n: int, per: float) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(Limit(n, per))

def sliding_log(n: int, per: float) -> SlidingWindowLogRateLimiter:
    return SlidingWindowLogRateLimiter(Limit(n, per))

def sliding_counter(n: int, per: float) -> SlidingWindowCounterRateLimiter:
    return SlidingWindowCounterRateLimiter(Limit(n, per))

def token_bucket(n: int, per: float, capacity: Optional[int] = None) -> TokenBucketRateLimiter:
    return TokenBucketRateLimiter(Limit(n, per), capacity=capacity)

def leaky_bucket(n: int, per: float, max_queue: int = 1000) -> LeakyBucketRateLimiter:
    return LeakyBucketRateLimiter(Limit(n, per), max_queue=max_queue)


# ---------------------------
# Examples (usage)
# ---------------------------

if __name__ == "__main__":
    # Choose an algorithm
    rl = token_bucket(10, 1.0, capacity=20)  # 10 rps average, burst up to 20

    # Per-user keying
    def user_key(user_id: str, *_args, **_kwargs) -> str:
        return f"user:{user_id}"

    # Decorate a function
    @rate_limited(rl, key_fn=lambda user_id, *_: user_key(user_id), block=False)
    def handle_request(user_id: str) -> str:
        return f"Handled for {user_id}"

    # Drive a quick demo
    ok, dropped = 0, 0
    for i in range(50):
        uid = "42"
        try:
            handle_request(uid)
            ok += 1
        except RuntimeError:
            dropped += 1
        time.sleep(0.02)  # 50 Hz calls

    print("OK:", ok, "DROPPED:", dropped)

    # Async usage
    async def main():
        arl = sliding_log(5, 1.0)
        @arate_limited(arl, key_fn=lambda uid: f"user:{uid}", block=True)
        async def work(uid: str):
            return "ok"

        for _ in range(7):
            # with block=True, the 6th/7th call will await until allowed
            print(await work("7"))

    if asyncio:
        asyncio.run(main())

```

## HTTP-style response (with status code 429 Too Many Requests) whenever a request is denied

Add http_response() helper to the base RateLimiter that returns a dict with:

status → HTTP status code (200 if allowed, 429 if limited)

allowed → bool

retry_after → seconds to wait before retrying (RFC 6585)

body → message string (optional)

This works for all algorithms (Fixed Window, Sliding Window, Token Bucket, Leaky Bucket, Redis).

Here’s the patch you can add to the previous big ratelimit.py file

```python
from http import HTTPStatus


class RateLimiter:
    """Base interface for all limiters."""

    def allow(self, key: str = "global", now: Optional[float] = None) -> bool:
        raise NotImplementedError

    def retry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        raise NotImplementedError

    def acquire(self, key: str = "global") -> None:
        while True:
            if self.allow(key):
                return
            time.sleep(min(0.1, max(0.0, self.retry_after(key))))

    async def aallow(self, key: str = "global", now: Optional[float] = None) -> bool:
        return self.allow(key, now)

    async def aretry_after(self, key: str = "global", now: Optional[float] = None) -> float:
        return self.retry_after(key, now)

    async def aacquire(self, key: str = "global") -> None:
        while True:
            if await self.aallow(key):
                return
            wait = await self.aretry_after(key)
            await asyncio.sleep(min(0.1, max(0.0, wait)))

    # ---------------------------
    # New HTTP helper
    # ---------------------------
    def http_response(self, key: str = "global", now: Optional[float] = None) -> dict:
        """
        Return HTTP-style response for integration with web servers.
        - 200 OK if allowed
        - 429 Too Many Requests if denied
        """
        allowed = self.allow(key, now)
        if allowed:
            return {
                "status": HTTPStatus.OK,
                "allowed": True,
                "retry_after": 0.0,
                "body": "Request allowed"
            }
        else:
            wait = self.retry_after(key, now)
            return {
                "status": HTTPStatus.TOO_MANY_REQUESTS,
                "allowed": False,
                "retry_after": wait,
                "headers": {"Retry-After": str(int(wait))},
                "body": f"Rate limit exceeded. Retry after {wait:.2f}s"
            }
```

### Example usage with any limiter

```python
if __name__ == "__main__":
    rl = token_bucket(5, 1.0, capacity=10)  # 5 req/s avg, burst up to 10

    for i in range(12):
        resp = rl.http_response("user:42")
        print(resp)
        time.sleep(0.1)
```

### Sample output

```bash
{'status': <HTTPStatus.OK: 200>, 'allowed': True, 'retry_after': 0.0, 'body': 'Request allowed'}
{'status': <HTTPStatus.OK: 200>, 'allowed': True, 'retry_after': 0.0, 'body': 'Request allowed'}
...
{'status': <HTTPStatus.TOO_MANY_REQUESTS: 429>, 'allowed': False, 'retry_after': 0.8, 'headers': {'Retry-After': '1'}, 'body': 'Rate limit exceeded. Retry after 0.80s'}
```

note:
Now all algorithms (
    FixedWindowRateLimiter,
    SlidingWindowLogRateLimiter,
    SlidingWindowCounterRateLimiter,
    TokenBucketRateLimiter,
    LeakyBucketRateLimiter,
    RedisSlidingWindowCounter) automatically gain this HTTP 429 integration.

### Flask/FastAPI middleware example that plugs these responses directly into a real HTTP server

#### 🔹 Flask Middleware Example

```python
# app_flask.py
from flask import Flask, request, jsonify, make_response
from ratelimit import token_bucket

app = Flask(__name__)

# Create a token bucket limiter: 5 req/s, burst 10
rl = token_bucket(5, 1, capacity=10)

def get_client_ip() -> str:
    """Use client IP as key (basic example)."""
    return request.remote_addr or "unknown"

@app.before_request
def check_rate_limit():
    key = f"ip:{get_client_ip()}"
    resp = rl.http_response(key)
    if not resp["allowed"]:
        response = make_response(
            jsonify({"error": resp["body"]}), resp["status"]
        )
        response.headers["Retry-After"] = str(int(resp["retry_after"]))
        return response  # abort request
    # else continue to route handler

@app.route("/")
def home():
    return jsonify({"message": "Welcome, request allowed"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

Requests beyond the limit get 429 Too Many Requests with a proper Retry-After header.

#### 🔹 Flask Example (Global + Per-Endpoint)

```python
# app_flask_combo.py
from flask import Flask, request, jsonify, make_response
from ratelimit import token_bucket

app = Flask(__name__)

# Global per-client: 100 requests/minute, burst 200
global_rl = token_bucket(100, 60, capacity=200)

# Endpoint-specific: /upload max 20 requests/minute
upload_rl = token_bucket(20, 60, capacity=40)

def get_client_id() -> str:
    """Could be IP, API key, or user ID."""
    return request.remote_addr or "unknown"

def check_limiter(limiter, key: str):
    """Check any limiter and return Flask response if blocked."""
    resp = limiter.http_response(key)
    if not resp["allowed"]:
        response = make_response(
            jsonify({"error": resp["body"]}), resp["status"]
        )
        response.headers["Retry-After"] = str(int(resp["retry_after"]))
        return response
    return None

@app.before_request
def check_global_limit():
    key = f"client:{get_client_id()}"
    blocked = check_limiter(global_rl, key)
    if blocked:
        return blocked

@app.route("/search")
def search():
    return jsonify({"message": "search endpoint OK"})

@app.route("/upload")
def upload():
    key = f"client:{get_client_id()}:upload"
    blocked = check_limiter(upload_rl, key)
    if blocked:
        return blocked
    return jsonify({"message": "upload endpoint OK"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

#### 🔹 FastAPI Middleware Example

```python
# app_fastapi.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ratelimit import sliding_log

app = FastAPI()

# Sliding window: 10 requests per 5 seconds
rl = sliding_log(10, 5)

def get_client_ip(request: Request) -> str:
    return request.client.host

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    key = f"ip:{get_client_ip(request)}"
    resp = rl.http_response(key)

    if not resp["allowed"]:
        return JSONResponse(
            content={"error": resp["body"]},
            status_code=resp["status"],
            headers={"Retry-After": str(int(resp["retry_after"]))}
        )

    return await call_next(request)

@app.get("/")
async def home():
    return {"message": "Welcome, request allowed"}

```

### 🔹 Curl Test

```bash
# Hit the server repeatedly
for i in {1..15}; do curl -i http://localhost:8000/; done
```

You’ll start seeing responses like

```bash
HTTP/1.1 200 OK
Content-Type: application/json

{"message": "Welcome, request allowed"}

HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 2

{"error":"Rate limit exceeded. Retry after 2.00s"}
```

#### 🔹 FastAPI Example (Global + Per-Endpoint)

```python
# app_fastapi_combo.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ratelimit import sliding_counter

app = FastAPI()

# Global per-client: 100/min

global_rl = sliding_counter(100, 60)

# Endpoint-specific: /upload stricter at 20/min

upload_rl = sliding_counter(20, 60)

def get_client_id(request: Request) -> str:
    return request.client.host

def make_response(resp: dict):
    return JSONResponse(
        content={"error": resp["body"]},
        status_code=resp["status"],
        headers={"Retry-After": str(int(resp["retry_after"]))}
    )

@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    key = f"client:{get_client_id(request)}"
    resp = global_rl.http_response(key)
    if not resp["allowed"]:
        return make_response(resp)
    return await call_next(request)

@app.get("/search")
async def search():
    return {"message": "search endpoint OK"}

@app.get("/upload")
async def upload(request: Request):
    key = f"client:{get_client_id(request)}:upload"
    resp = upload_rl.http_response(key)
    if not resp["allowed"]:
        return make_response(resp)
    return {"message": "upload endpoint OK"}

```
