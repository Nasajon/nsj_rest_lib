import enum
import json
import redis
import uuid

from datetime import datetime, timezone, timedelta
from typing import Any

from nsj_rest_lib.redis_config import redis_client
from nsj_rest_lib.settings import AUDIT_STREAM_KEY, get_logger


RETENTION_DAYS = 7


class DBTypes(enum.Enum):
    MULTIBANCO = "mb"
    WEB_MULTITENANT = "dbprod"
    DIARIO_UNICO = "dbdu"
    OTHER = "other"
    UNDEFINED = "undefined"


class HTTPMethods(enum.Enum):
    GET = "GET"
    LIST = "LIST"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"

    @staticmethod
    def from_value(value: str) -> "HTTPMethods":
        for method in HTTPMethods:
            if method.value == value:
                return method
        raise ValueError(f"Invalid HTTP method value: {value}")


class AuditUtil:

    def __init__(
        self,
        redis_client: redis.Redis = redis_client,
        audit_stream_key: str = AUDIT_STREAM_KEY,
    ) -> None:
        self.redis_client = redis_client
        self.stream_key = audit_stream_key

    # def _key(self, *parts: str) -> str:
    #     return ":".join(parts)

    # def get_redis(self, *args: str) -> Any:
    #     if not redis_client:
    #         get_logger().warning(
    #             "Atenção! Redis nao configurado (faltando variavel REDIS_URL)."
    #         )

    #     value = redis_client.get(self._key(*args))
    #     if value:
    #         return value.decode("utf-8")
    #     return None

    # def set_redis(self, *args) -> None:
    #     if not redis_client:
    #         get_logger().warning(
    #             "Atenção! Redis nao configurado (faltando variavel REDIS_URL)."
    #         )

    #     value = args[-1]
    #     redis_client.set(self._key(*args[:-1]), value)

    def emit_request_started(
        self,
        request_id: uuid.UUID,
        tenant_id: int,
        grupo_empresarial_id: uuid.UUID | None,
        area_atendimento_id: uuid.UUID | None,
        db_type: DBTypes,
        db_key: str,
        db_user: str,
        actor_user_id: str,
        subject_user_id: int | None,
        session_id: str | None,
        http_method: HTTPMethods,
        http_route: str,
        action: str,
        params_normalizados: dict,
        meta_human: str | None = None,
        request_raw_truncated: str | None = None,
        payload_ref: str | None = None,
    ) -> str:
        """
        Publica um evento 'request_started' no Redis Stream com retenção aproximada de 7 dias.

        Parâmetros:
        - request_id: ID da requisição
        - tenant_id: ID do tenant
        - grupo_empresarial_id: ID do grupo empresarial
        - area_atendimento_id: ID da area de atendimento
        - db_type: Tipo do banco de dados
        - db_key: Chave de identificação do banco de dados (pode ser o nome do banco)
        - db_user: Nome do usuário do banco
        - actor_user_id: ID do usuário que fez a requisição
        - subject_user_id: ID do usuário personificado nessa requisição (se houver personificação)
        - session_id: ID da sessão (se houver, e para as APIs stateless normalmente não há)
        - http_method: Método HTTP da requisição
        - http_route: Rota HTTP da requisição (endpoint)
        - action: Ação da requisição
        - params_normalizados: Parâmetros da requisição normalizados (não é a requisição completa)
        - meta_human: Metadadtos, humanizados, da requisição
        - request_raw_truncated: Conteúdo da requisição truncado
        - payload_ref: URL da requisição gravada num bucket (se houver)
        """

        try:
            now = datetime.now(timezone.utc)

            # 🔹 ID mínimo para retenção (agora - 7 dias)
            min_ts_ms = int((now - timedelta(days=RETENTION_DAYS)).timestamp() * 1000)
            min_id = f"{min_ts_ms}-0"

            event = {
                "event_id": str(uuid.uuid4()),
                "event_ts_utc": now.isoformat(timespec="milliseconds"),
                "event_type": "request_started",
                "request_id": str(request_id),
                "tenant_id": str(tenant_id),
                "grupo_empresarial_id": (
                    "" if grupo_empresarial_id is None else str(grupo_empresarial_id)
                ),
                "area_atendimento_id": (
                    "" if area_atendimento_id is None else str(area_atendimento_id)
                ),
                "db_key": f"{db_type.value}_{db_key}",
                "db_user": db_user,
                "actor_user_id": str(actor_user_id),
                "subject_user_id": (
                    "" if subject_user_id is None else str(subject_user_id)
                ),
                "session_id": "" if session_id is None else session_id,
                "http_method": http_method.value,
                "http_route": http_route,
                "action": action,
                "params_normalizados": json.dumps(
                    params_normalizados,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "is_transaction_intent": (
                    "1"
                    if http_method
                    in {
                        HTTPMethods.POST,
                        HTTPMethods.PUT,
                        HTTPMethods.PATCH,
                        HTTPMethods.DELETE,
                    }
                    else "0"
                ),
            }

            if meta_human:
                event["meta_human"] = meta_human

            if request_raw_truncated:
                event["request_raw_truncated"] = request_raw_truncated
            elif payload_ref:
                event["payload_ref"] = payload_ref

            # XADD com retenção por tempo (7 dias)
            msg_id = self.redis_client.xadd(
                self.stream_key,
                fields=event,
                minid=f"~ {min_id}",  # purge aproximado
            )

            return msg_id
        except Exception as e:
            get_logger().error(f"Erro ao publicar evento request_started: {e}")

    def emit_request_finished(
        self,
        request_id: uuid.UUID,
        tenant_id: int,
        grupo_empresarial_id: uuid.UUID | None,
        http_status: int,
        duration_ms: int,
        tx_attempted: bool,
        area_atendimento_id: uuid.UUID | None = None,
        db_user: str | None = None,
        error_normalized: dict | None = None,
        error_code: str | None = None,
        error_message_short: str | None = None,
        error_fingerprint: str | None = None,
        request_json: str | None = None,
        is_transaction_intent: bool | None = None,
    ) -> str:
        """
        Publica um evento 'request_finished' no Redis Stream com retenção aproximada de 7 dias.

        Parâmetros:
        - request_id: ID da requisição
        - tenant_id: ID do tenant
        - grupo_empresarial_id: ID do grupo empresarial
        - area_atendimento_id: ID da area de atendimento
        - db_user: Nome do usuário do banco
        - http_status: Código HTTP da resposta
        - duration_ms: Duração total da requisição
        - tx_attempted: Flag indicando tentativa de transação
        - error_normalized: Objeto com error_code, error_message_short e error_fingerprint
        - error_code: Código normalizado do erro
        - error_message_short: Mensagem curta do erro
        - error_fingerprint: Fingerprint do erro
        - request_json: JSON da requisição (somente em casos de erro)
        - is_transaction_intent: Flag de intenção transacional
        """

        try:
            now = datetime.now(timezone.utc)

            # 🔹 ID mínimo para retenção (agora - 7 dias)
            min_ts_ms = int((now - timedelta(days=RETENTION_DAYS)).timestamp() * 1000)
            min_id = f"{min_ts_ms}-0"

            event = {
                "event_id": str(uuid.uuid4()),
                "event_ts_utc": now.isoformat(timespec="milliseconds"),
                "event_type": "request_finished",
                "request_id": str(request_id),
                "tenant_id": str(tenant_id),
                "grupo_empresarial_id": (
                    "" if grupo_empresarial_id is None else str(grupo_empresarial_id)
                ),
                "area_atendimento_id": (
                    "" if area_atendimento_id is None else str(area_atendimento_id)
                ),
                "db_user": "" if db_user is None else db_user,
                "http_status": str(http_status),
                "duration_ms": str(duration_ms),
                "tx_attempted": "1" if tx_attempted else "0",
            }

            if is_transaction_intent is not None:
                event["is_transaction_intent"] = "1" if is_transaction_intent else "0"

            if error_normalized is None and (
                error_code or error_message_short or error_fingerprint
            ):
                error_normalized = {
                    "error_code": error_code or "",
                    "error_message_short": error_message_short or "",
                    "error_fingerprint": error_fingerprint or "",
                }

            if error_normalized is not None:
                event["error_normalized"] = json.dumps(
                    error_normalized,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            if error_code:
                event["error_code"] = str(error_code)
            if error_message_short:
                event["error_message_short"] = error_message_short
            if error_fingerprint:
                event["error_fingerprint"] = error_fingerprint

            if request_json:
                event["request_json"] = request_json

            # XADD com retenção por tempo (7 dias)
            msg_id = self.redis_client.xadd(
                self.stream_key,
                fields=event,
                minid=f"~ {min_id}",  # purge aproximado
            )

            return msg_id
        except Exception as e:
            get_logger().error(f"Erro ao publicar evento request_finished: {e}")
