#  Rate Limiter (rate_limiter.py)
import time
import threading


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.
    capacity: maximum tokens in the bucket
    refill_rate: tokens added per second
    """

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.refill_rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_refill = now

    def acquire(self, tokens: float = 1.0) -> None:
        """Block until enough tokens are available."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
            time.sleep(0.05)


class RateLimitedBackend:
    """
    Wraps any backend with token-bucket rate limiting and
    exponential backoff on HTTP 429 responses.
    """

    MAX_RETRIES = 5
    BASE_DELAY = 1.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(self, backend, limiter: TokenBucketRateLimiter):
        self.backend = backend
        self.limiter = limiter

    def chat(self, messages: list) -> str:
        self.limiter.acquire(tokens=1.0)
        delay = self.BASE_DELAY
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.backend.chat(messages)
            except Exception as exc:
                error_str = str(exc).lower()
                if "429" in error_str or "rate limit" in error_str:
                    print(f"[RateLimiter] 429 received. Retry {attempt+1} in {delay}s.")
                    time.sleep(delay)
                    delay *= self.BACKOFF_MULTIPLIER
                else:
                    raise
        raise RuntimeError(f"Max retries ({self.MAX_RETRIES}) exceeded.")
    