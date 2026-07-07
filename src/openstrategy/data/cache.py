"""
数据缓存管理
"""

import hashlib
import json
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """
    数据缓存管理器

    支持内存缓存和磁盘缓存，避免重复请求API

    Examples:
        >>> cache = DataCache(cache_dir="~/.cache/openstrategy")
        >>> df = cache.get("AAPL_1y") or fetch_and_cache()
    """

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        ttl_hours: float = 24.0,  # 默认缓存24小时
        max_memory_items: int = 100,
    ):
        """
        初始化缓存

        Args:
            cache_dir: 磁盘缓存目录
            ttl_hours: 缓存有效期（小时）
            max_memory_items: 内存缓存最大条目数
        """
        self.ttl = timedelta(hours=ttl_hours)
        self.max_memory_items = max_memory_items

        # 内存缓存
        self._memory_cache: dict = {}
        self._access_times: dict = {}

        # 磁盘缓存
        if cache_dir:
            self.cache_dir = Path(cache_dir).expanduser()
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.cache_dir = None

    def _get_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Optional[Path]:
        """获取磁盘缓存路径"""
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{key}.pkl"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """
        获取缓存数据

        Args:
            key: 缓存键

        Returns:
            DataFrame 或 None（如果缓存不存在或已过期）
        """
        # 先检查内存缓存
        if key in self._memory_cache:
            cached_time = self._access_times.get(key)
            if cached_time and datetime.now() - cached_time < self.ttl:
                logger.debug(f"Memory cache hit: {key}")
                return self._memory_cache[key]
            else:
                # 过期，清理内存
                del self._memory_cache[key]
                del self._access_times[key]

        # 检查磁盘缓存
        if self.cache_dir:
            cache_path = self._get_cache_path(key)
            if cache_path and cache_path.exists():
                try:
                    with open(cache_path, "rb") as f:
                        cached = pickle.load(f)

                    cached_time = cached.get("timestamp")
                    if cached_time and datetime.now() - cached_time < self.ttl:
                        logger.debug(f"Disk cache hit: {key}")
                        # 加载到内存
                        self._set_memory(key, cached["data"])
                        return cached["data"]
                    else:
                        # 过期，删除
                        cache_path.unlink()

                except Exception as e:
                    logger.warning(f"Failed to load cache {key}: {e}")

        return None

    def set(self, key: str, data: pd.DataFrame) -> None:
        """
        设置缓存

        Args:
            key: 缓存键
            data: 要缓存的数据
        """
        # 内存缓存
        self._set_memory(key, data)

        # 磁盘缓存
        if self.cache_dir:
            cache_path = self._get_cache_path(key)
            if cache_path:
                try:
                    with open(cache_path, "wb") as f:
                        pickle.dump(
                            {
                                "timestamp": datetime.now(),
                                "data": data,
                            },
                            f,
                        )
                    logger.debug(f"Saved to disk cache: {key}")
                except Exception as e:
                    logger.warning(f"Failed to save cache {key}: {e}")

    def _set_memory(self, key: str, data: pd.DataFrame) -> None:
        """设置内存缓存（带LRU清理）"""
        # 如果达到上限，清理最旧的
        if len(self._memory_cache) >= self.max_memory_items:
            oldest_key = min(self._access_times, key=self._access_times.get)
            del self._memory_cache[oldest_key]
            del self._access_times[oldest_key]

        self._memory_cache[key] = data
        self._access_times[key] = datetime.now()

    def clear(self, memory_only: bool = False) -> None:
        """
        清理缓存

        Args:
            memory_only: 只清理内存缓存
        """
        self._memory_cache.clear()
        self._access_times.clear()

        if not memory_only and self.cache_dir:
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
            logger.info("Cleared all cache")

    def clean_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的文件数量
        """
        count = 0
        if self.cache_dir:
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    with open(cache_file, "rb") as f:
                        cached = pickle.load(f)

                    cached_time = cached.get("timestamp")
                    if cached_time and datetime.now() - cached_time >= self.ttl:
                        cache_file.unlink()
                        count += 1

                except Exception:
                    pass

        # 清理内存中的过期项
        now = datetime.now()
        expired_keys = [k for k, t in self._access_times.items() if now - t >= self.ttl]
        for key in expired_keys:
            del self._memory_cache[key]
            del self._access_times[key]

        logger.info(f"Cleaned {count} expired cache files")
        return count

    def stats(self) -> dict:
        """
        获取缓存统计

        Returns:
            统计信息字典
        """
        disk_count = 0
        disk_size = 0

        if self.cache_dir:
            for cache_file in self.cache_dir.glob("*.pkl"):
                disk_count += 1
                disk_size += cache_file.stat().st_size

        return {
            "memory_items": len(self._memory_cache),
            "disk_items": disk_count,
            "disk_size_mb": round(disk_size / 1024 / 1024, 2),
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }
