"""
料架控灯 HTTP API 客户端。

封装所有与新智能料架的 HTTP REST 通信。
所有方法同步阻塞，由上层 async 服务在 executor 中调用。
"""

import uuid
import logging
import time
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import requests

logger = logging.getLogger(__name__)


class RackApiError(Exception):
    """控灯 API 异常"""
    pass


class RackApiClient:
    """料架控灯 HTTP API 客户端

    用法::

        client = RackApiClient(
            base_url="http://localhost:8080",
            user_id="admin",
            client_id="smes-001",
        )
        client.light_up_cell("A0010001", led_color=2)

    容错机制:
        - API 不可达: 记录 ERROR 日志，标记料架"控灯离线"，业务继续
        - 超时: 3 次指数退避（1s, 2s, 4s）
        - HTTP 错误: 抛出 RackApiError，上层捕获后降级
    """

    # 储位 LED 色值映射（字符串 → integer）
    LED_COLORS: Dict[str, int] = {
        "off": 0,
        "red": 1,
        "green": 2,
        "yellow": 3,
        "blue": 4,
        "magenta": 5,
        "cyan": 6,
        "white": 7,
    }

    # 警示灯色值映射
    INDICATOR_COLORS: Dict[str, int] = {
        "off": 0,
        "red": 1,
        "yellow": 2,
        "red_yellow": 3,
        "green": 4,
        "red_green": 5,
        "yellow_green": 6,
        "all": 7,
    }

    def __init__(
        self,
        base_url: str,
        user_id: str = "",
        client_id: str = "",
        timeout: float = 5.0,
        max_retries: int = 3,
    ):
        """
        Args:
            base_url: 料架控灯服务地址（如 http://localhost:8080）
            user_id: 操作用户 ID
            client_id: 终端设备 ID
            timeout: 请求超时秒数
            max_retries: 最大重试次数（指数退避）
        """
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.client_id = client_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    # ── 内部方法 ──────────────────────────────────────────────────────

    def _get_headers(self) -> Dict[str, str]:
        return {
            "userId": self.user_id,
            "clientId": self.client_id,
            "sessionId": str(uuid.uuid4()),
            "Content-Type": "application/json;charset=utf-8",
        }

    def _post(self, path: str, data: dict) -> dict:
        """通用 POST 请求（含重试与指数退避）"""
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                resp = self.session.post(
                    url,
                    json=data,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                result = resp.json()

                # 业务 code 校验
                code = result.get("code")
                if code is not None and code != 0:
                    raise RackApiError(
                        f"API error: code={code}, msg={result.get('message', 'unknown')}"
                    )
                return result

            except requests.Timeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    sleep_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "RackApi timeout (attempt %d/%d), retrying in %ds | %s",
                        attempt + 1, self.max_retries, sleep_time, path,
                    )
                    time.sleep(sleep_time)

            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    sleep_time = 2 ** attempt
                    logger.warning(
                        "RackApi request error (attempt %d/%d), retrying in %ds | %s: %s",
                        attempt + 1, self.max_retries, sleep_time, path, str(e),
                    )
                    time.sleep(sleep_time)

        raise RackApiError(
            f"Request failed after {self.max_retries} retries: {last_error}"
        )

    # ── 公共 API ──────────────────────────────────────────────────────

    def light_up_cell(
        self,
        cell_id: str,
        led_color: int,
        is_blink: bool = False,
        turn_on_time: int = 0,
    ) -> dict:
        """单个储位亮灯

        Args:
            cell_id: 储位号（如 "A0010001"）
            led_color: 色值（0=灭, 1=红, 2=绿, 3=黄, 4=蓝, ...）
            is_blink: 是否闪烁
            turn_on_time: 亮灯秒数（0=常亮）

        Returns:
            API 响应 dict
        """
        return self._post("/api/RackCellMgr/LightUpCellLed", {
            "cellId": cell_id,
            "ledColor": led_color,
            "blink": is_blink,
            "turnOnTime": turn_on_time,
        })

    def light_up_cells_batch(
        self,
        cells: List[Dict[str, Any]],
        turn_on_time: int = 0,
        voice_text: str = "",
    ) -> dict:
        """批量亮灯 + 语音播报

        Args:
            cells: 储位列表，每项格式::

                {"cellId": "A0010001", "ledColor": 2, "blink": False}

            turn_on_time: 亮灯秒数（0=常亮）
            voice_text: 语音播报文本

        Returns:
            API 响应 dict
        """
        return self._post("/api/RackCellMgr/LightUpCellLedList", {
            "cells": cells,
            "turnOnTime": turn_on_time,
            "voiceText": voice_text,
        })

    def set_indicator_status(
        self,
        rack_id: str,
        indicator_id: int,
        indicator_status: int,
        is_blink: bool = False,
    ) -> dict:
        """设置警示灯

        Args:
            rack_id: 料架 ID
            indicator_id: 警示灯编号
            indicator_status: 色值组合（0=关, 1=红, 2=黄, 3=红+黄, ...）
            is_blink: 是否闪烁

        Returns:
            API 响应 dict
        """
        return self._post("/api/RackCellMgr/SetWarningLed", {
            "rackId": rack_id,
            "indicatorId": indicator_id,
            "indicatorStatus": indicator_status,
            "blink": is_blink,
        })

    def rack_test(
        self,
        rack_id: str,
        test_mode: int,
        interval: int = 1000,
    ) -> dict:
        """硬件测试

        测试模式（可组合）:
            - 0: 取消测试
            - 1: RGB 灯珠测试
            - 2: 灯序测试
            - 4: 警示灯测试
            - 8: 感应传感器测试
            - 15: 全部测试（1+2+4+8）

        Args:
            rack_id: 料架 ID
            test_mode: 测试模式
            interval: 测试间隔（ms）

        Returns:
            API 响应 dict
        """
        return self._post("/api/RackMgr/RackTest", {
            "id": rack_id,
            "testMode": test_mode,
            "interval": interval,
        })

    def get_cell_list(
        self,
        rack_id: Optional[str] = None,
        cell_filter: Optional[str] = None,
        page_index: int = 1,
        page_size: int = 100,
    ) -> dict:
        """查询储位状态（分页）

        Args:
            rack_id: 料架 ID（None=全部）
            cell_filter: 储位号过滤
            page_index: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            API 响应 dict，data 中含储位列表
        """
        data: Dict[str, Any] = {
            "pageIndex": page_index,
            "pageSize": page_size,
        }
        if rack_id:
            data["rackId"] = rack_id
        if cell_filter:
            data["filter"] = cell_filter
        return self._post("/api/RackCellMgr/GetCellList", data)


# ── 辅助函数 ──────────────────────────────────────────────────────────


async def get_rack_api_config(
    db: AsyncSession,
) -> Optional[Dict[str, str]]:
    """获取全局料架控灯 API 配置（系统设置）。

    Returns:
        {"base_url": str, "user_id": str, "client_id": str} 或 None（无配置时）
    """
    from app.models import SystemSetting

    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.key.in_([
                "rack_api_base_url",
                "rack_api_user_id",
                "rack_api_client_id",
            ])
        )
    )
    settings_rows = result.scalars().all()
    sys_config = {row.key: row.value for row in settings_rows}

    base_url = sys_config.get("rack_api_base_url")
    if not base_url:
        return None

    return {
        "base_url": base_url,
        "user_id": sys_config.get("rack_api_user_id", ""),
        "client_id": sys_config.get("rack_api_client_id", ""),
    }
