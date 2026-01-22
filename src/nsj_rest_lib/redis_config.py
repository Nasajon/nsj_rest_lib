import os

from redis import Redis
from typing import Any

from nsj_rest_lib.settings import get_logger

REDIS_URL = os.getenv("REDIS_URL")

redis_client = None
if REDIS_URL:
    redis_client = Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
    )
else:
    get_logger().warning(
        "Atenção! Redis não configurado (faltando variável REDIS_URL)."
    )
