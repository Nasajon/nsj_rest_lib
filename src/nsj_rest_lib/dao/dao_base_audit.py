import uuid

from typing import Any, Callable

from nsj_gcf_utils.json_util import json_dumps, convert_to_dumps
from nsj_rest_lib.settings import DATABASE_DRIVER, get_logger
from nsj_rest_lib.util.audit_dbmodel_util import AuditDBModelUtil


class DAOBaseAudit:
    def __init__(
        self,
        db_adapter,
        db_adapter_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._db = db_adapter
        self._db_adapter_provider = db_adapter_provider

    def insert_outbox(self, payload: dict[str, Any]) -> None:
        outbox_payload = dict(payload or {})
        outbox_payload.setdefault("outbox_id", str(uuid.uuid4()))
        outbox_payload.setdefault("schema_version", 1)

        outbox_payload["params_normalizados"] = self._normalize_json_field(
            outbox_payload.get("params_normalizados") or {}
        )
        outbox_payload["commit_json"] = self._normalize_json_field(
            outbox_payload.get("commit_json")
        )

        outbox_payload = convert_to_dumps(outbox_payload)

        sql = """
        INSERT INTO audit_outbox (
            outbox_id,
            tenant_id,
            grupo_empresarial_id,
            area_atendimento_id,
            request_id,
            user_id,
            subject_user_id,
            session_id,
            action,
            resource_type,
            resource_id,
            params_normalizados,
            commit_json,
            payload_ref,
            payload_sha256,
            schema_version
        ) VALUES (
            :outbox_id,
            :tenant_id,
            :grupo_empresarial_id,
            :area_atendimento_id,
            :request_id,
            :user_id,
            :subject_user_id,
            :session_id,
            :action,
            :resource_type,
            :resource_id,
            :params_normalizados,
            :commit_json,
            :payload_ref,
            :payload_sha256,
            :schema_version
        )
        """

        savepoint_set = False
        try:
            if self._db.in_transaction():
                self._db.execute("SAVEPOINT audit_outbox_sp")
                savepoint_set = True

            rowcount, _ = self._db.execute(sql, **outbox_payload)
            if rowcount <= 0:
                raise Exception("Erro inserindo audit_outbox no banco de dados.")
        except Exception as exc:
            if savepoint_set:
                try:
                    self._db.execute("ROLLBACK TO SAVEPOINT audit_outbox_sp")
                except Exception:
                    get_logger().warning(
                        "Erro desconhecido ao fazer rollback do savepoint de audit_outbox."
                    )
                    pass

            if DATABASE_DRIVER.lower().startswith(
                "postgres"
            ) and AuditDBModelUtil.is_audit_outbox_model_error(exc):
                self._repair_schema()
                retry_savepoint_set = False
                try:
                    if self._db.in_transaction():
                        self._db.execute("SAVEPOINT audit_outbox_sp_retry")
                        retry_savepoint_set = True
                    rowcount, _ = self._db.execute(sql, **outbox_payload)
                    if rowcount <= 0:
                        raise Exception(
                            "Erro inserindo audit_outbox no banco de dados."
                        )
                    return
                except Exception as retry_exc:
                    if retry_savepoint_set:
                        try:
                            self._db.execute(
                                "ROLLBACK TO SAVEPOINT audit_outbox_sp_retry"
                            )
                        except Exception:
                            get_logger().warning(
                                "Erro desconhecido ao fazer rollback do savepoint de audit_outbox (retry)."
                            )
                    raise Exception(
                        "Erro inserindo audit_outbox no banco de dados."
                    ) from retry_exc

            raise

    @staticmethod
    def _normalize_json_field(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json_dumps(value, ensure_ascii=False)

    def _repair_schema(self) -> None:
        if self._db_adapter_provider is None:
            AuditDBModelUtil.ensure_audit_outbox_schema(self._db)
            return

        try:
            db_adapter = self._db_adapter_provider()
        except Exception as exc:
            get_logger().warning(
                f"Erro obtendo conexão para corrigir audit_outbox: {exc}"
            )
            AuditDBModelUtil.ensure_audit_outbox_schema(self._db)
            return

        try:
            AuditDBModelUtil.ensure_audit_outbox_schema(db_adapter)
        except Exception as exc:
            get_logger().warning(f"Erro corrigindo schema de audit_outbox: {exc}")
