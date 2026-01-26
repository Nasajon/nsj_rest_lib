from redis import Redis

from nsj_rest_lib.settings import AUDIT_REDIS_URL, get_logger

redis_client = None
if AUDIT_REDIS_URL:
    redis_client = Redis.from_url(
        AUDIT_REDIS_URL,
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
    )
else:
    get_logger().warning(
        "Atenção! Redis não configurado (faltando variável AUDIT_REDIS_URL)."
    )
