"""
苗绣·识裳 — 性能管理模块
========================================================
提供：系统监控、模型管理、请求队列、并发控制
纯 Python 标准库 + /proc 文件系统，零额外依赖，riscv64 兼容
"""

import os
import time
import threading
import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 1. 系统监控器
# ============================================================
class SystemMonitor:
    """无依赖系统指标采集器（Linux /proc）"""

    def __init__(self):
        self._cpu_prev = None
        self._cpu_time = 0.0
        self._net_prev = None
        self._net_time = 0.0

    # ---- CPU ----
    def cpu_percent(self) -> float:
        """整体 CPU 使用率 (%)"""
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            if parts[0] != "cpu" or len(parts) < 5:
                return 0.0
            vals = [int(x) for x in parts[1:]]
            total = sum(vals)
            idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
            now = time.monotonic()
            if self._cpu_prev is not None and now > self._cpu_time:
                td = total - sum(self._cpu_prev)
                id = idle - (self._cpu_prev[3] + (self._cpu_prev[4] if len(self._cpu_prev) > 4 else 0))
                usage = (1.0 - id / td) * 100.0 if td > 0 else 0.0
            else:
                usage = 0.0
            self._cpu_prev = vals
            self._cpu_time = now
            return round(max(0.0, min(100.0, usage)), 1)
        except Exception:
            return 0.0

    def cpu_count(self) -> int:
        return os.cpu_count() or 1

    # ---- 内存 ----
    def memory_percent(self) -> float:
        """内存使用率 (%)"""
        try:
            info = self._parse_meminfo()
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", 0) or (
                info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)
            )
            return round((1.0 - avail / total) * 100.0, 1) if total > 0 else 0.0
        except Exception:
            return 0.0

    def memory_used_mb(self) -> float:
        """已用内存 (MB)"""
        try:
            info = self._parse_meminfo()
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", 0) or (
                info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)
            )
            return round((total - avail) / 1024.0, 1)
        except Exception:
            return 0.0

    def memory_total_mb(self) -> float:
        try:
            return round(self._parse_meminfo().get("MemTotal", 0) / 1024.0, 1)
        except Exception:
            return 0.0

    @staticmethod
    def _parse_meminfo() -> dict:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        return info

    # ---- 温度 ----
    def cpu_temp(self) -> Optional[float]:
        """CPU 温度（°C），不支持则返回 None"""
        paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]
        for p in paths:
            try:
                with open(p) as f:
                    val = int(f.read().strip())
                return round(val / 1000.0, 1) if val > 1000 else round(float(val), 1)
            except Exception:
                continue
        return None

    # ---- 进程自身 ----
    @staticmethod
    def process_rss_mb() -> float:
        """当前进程 RSS (MB)"""
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024.0, 1)
        except Exception:
            pass
        return 0.0

    # ---- 快照 ----
    def snapshot(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent(),
            "cpu_count": self.cpu_count(),
            "mem_percent": self.memory_percent(),
            "mem_used_mb": self.memory_used_mb(),
            "mem_total_mb": self.memory_total_mb(),
            "cpu_temp": self.cpu_temp(),
            "process_rss_mb": self.process_rss_mb(),
        }


# ============================================================
# 2. 推理延迟追踪器
# ============================================================
@dataclass
class LatencyTracker:
    """滑动窗口延迟统计（最近 N 次推理）"""
    window_size: int = 100
    _times: deque = field(default_factory=lambda: deque(maxlen=100))

    def record(self, ms: float):
        self._times.append(ms)

    @property
    def count(self) -> int:
        return len(self._times)

    def stats(self) -> dict:
        if not self._times:
            return {"count": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "last_ms": 0}
        import math
        sorted_t = sorted(self._times)
        n = len(sorted_t)
        return {
            "count": n,
            "avg_ms": round(sum(sorted_t) / n, 1),
            "p50_ms": round(sorted_t[int(n * 0.50)], 1),
            "p95_ms": round(sorted_t[int(n * 0.95)], 1),
            "p99_ms": round(sorted_t[int(n * 0.99)], 1),
            "last_ms": round(sorted_t[-1], 1),
        }


# ============================================================
# 3. 请求并发控制器（异步信号量）
# ============================================================
class ConcurrencyGuard:
    """
    限制同时处理的请求数，超出的请求排队等待。
    防止 Ollama / YOLO 被突发流量压垮。
    """

    def __init__(self, max_concurrent: int = 2, timeout: float = 60.0):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        self._active = 0
        self._total = 0
        self._errors = 0
        self._lock = threading.Lock()

    async def acquire(self):
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self._timeout)
        except asyncio.TimeoutError:
            raise RuntimeError("服务繁忙，请稍后重试")

    def release(self):
        self._sem.release()

    def enter(self):
        with self._lock:
            self._active += 1
            self._total += 1

    def exit(self):
        with self._lock:
            self._active -= 1

    def error(self):
        with self._lock:
            self._errors += 1

    @property
    def active(self) -> int:
        return self._active

    def stats(self) -> dict:
        with self._lock:
            return {
                "active_requests": self._active,
                "total_requests": self._total,
                "errors": self._errors,
            }


# ============================================================
# 4. 模型预热与缓存
# ============================================================
class ModelWarmup:
    """启动时用空数据跑一次推理，触发 JIT/内核预热"""

    @staticmethod
    async def warmup_yolo(detector, size: tuple = (640, 480)):
        """YOLO 预热：用纯色图跑一次推理"""
        from PIL import Image
        import numpy as np
        dummy = Image.fromarray(
            np.zeros((size[1], size[0], 3), dtype=np.uint8)
        )
        detector.detect(dummy)

    @staticmethod
    async def warmup_ollama(host: str, model: str):
        """Ollama 预热：发一条短消息"""
        import requests as http_requests
        try:
            http_requests.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "1+1=?"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
                timeout=30,
            )
        except Exception:
            pass  # 预热失败不影响启动


# ============================================================
# 全局单例
# ============================================================
monitor = SystemMonitor()
yolo_latency = LatencyTracker(window_size=100)
llm_latency = LatencyTracker(window_size=50)
yolo_guard = ConcurrencyGuard(max_concurrent=2, timeout=120)
llm_guard = ConcurrencyGuard(max_concurrent=1, timeout=180)
