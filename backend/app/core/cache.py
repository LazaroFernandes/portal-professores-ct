from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            cached = self._items.get(key)
            if cached and cached[0] > now:
                return cached[1]
        value = loader()
        with self._lock:
            self._items[key] = (now + ttl, value)
        return value

    def invalidate(self, *prefixes: str) -> None:
        with self._lock:
            if not prefixes:
                self._items.clear()
                return
            for key in list(self._items):
                if any(key.startswith(prefix) for prefix in prefixes):
                    self._items.pop(key, None)


cache = TTLCache()
