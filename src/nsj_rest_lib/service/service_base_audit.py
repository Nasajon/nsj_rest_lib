import hashlib
import json
import uuid

from typing import Any, Dict

from flask import g, has_request_context, request

from nsj_rest_lib.dao.dao_base_audit import DAOBaseAudit
from nsj_rest_lib.settings import AUDIT_OUTBOX_TRANSACTION
from nsj_rest_lib.util.audit_ids_util import (
    retrieve_area_atendimento_id,
    retrieve_grupo_empresarial_id,
    retrieve_tenant_id,
)
from nsj_rest_lib.util.audit_dto_util import convert_dto_full
from nsj_rest_lib.util.user_audit_util import get_actor_user_id
from nsj_rest_lib.util.util_normaliza_parametros import get_params_normalizados


class ServiceBaseAudit:
    def _should_record_audit_outbox(self) -> bool:
        if not AUDIT_OUTBOX_TRANSACTION:
            return False
        if not has_request_context():
            return False
        return getattr(g, "request_id", None) is not None

    def _record_audit_outbox(
        self,
        action: str,
        dto: Any | None,
        resource_id: Any | None,
        params_normalizados: Dict[str, Any] | None = None,
        commit_json: Any | None = None,
        old_dto: Any | None = None,
        route_resource_id: Any | None = None,
    ) -> None:
        if not AUDIT_OUTBOX_TRANSACTION:
            return
        if not has_request_context():
            return

        request_id = getattr(g, "request_id", None)
        if request_id is None:
            return

        audit_payload = self._build_audit_payload(
            action=action,
            dto=dto,
            resource_id=resource_id,
            params_normalizados=params_normalizados,
            commit_json=commit_json,
            old_dto=old_dto,
            route_resource_id=route_resource_id,
        )
        if audit_payload is None:
            return

        db_provider = None
        injector_factory = getattr(self, "_injector_factory", None)
        if injector_factory is not None and hasattr(injector_factory, "db_adapter"):
            db_provider = injector_factory.db_adapter

        audit_dao = DAOBaseAudit(
            self._dao._db,
            db_adapter_provider=db_provider,
        )
        audit_dao.insert_outbox(audit_payload)

    def _build_audit_payload(
        self,
        action: str,
        dto: Any | None,
        resource_id: Any | None,
        params_normalizados: Dict[str, Any] | None,
        commit_json: Any | None,
        old_dto: Any | None,
        route_resource_id: Any | None,
    ) -> Dict[str, Any] | None:
        request_id = getattr(g, "request_id", None)
        if request_id is None:
            return None

        query_args = request.args
        body = request.get_json(force=True, silent=True)

        tenant_id = getattr(g, "audit_tenant_id", None) or retrieve_tenant_id(
            None,
            query_args=query_args,
            body=body,
        )
        grupo_empresarial_id = getattr(
            g, "audit_grupo_empresarial_id", None
        ) or retrieve_grupo_empresarial_id(
            None,
            query_args=query_args,
            body=body,
        )
        area_atendimento_id = getattr(
            g, "audit_area_atendimento_id", None
        ) or retrieve_area_atendimento_id(
            None,
            query_args=query_args,
            body=body,
        )

        user_id = get_actor_user_id()
        subject_user_id = self._resolve_subject_user_id()
        session_id = self._resolve_session_id()

        params_normalizados = params_normalizados or getattr(
            g, "audit_params_normalizados", None
        )
        if params_normalizados is None:
            params_normalizados = get_params_normalizados(
                query_args=query_args,
                body=body,
                dto_class=getattr(self, "_dto_class", None),
                path_args=getattr(request, "view_args", None),
            )

        resource_id = resource_id or self._resolve_resource_id(dto)
        if commit_json is None:
            commit_json = self._build_commit_json(old_dto, dto, resource_id)
        commit_json = self._add_table_name_to_commit_json(commit_json)

        resource_type = self._resolve_resource_type(route_resource_id)
        payload_sha256 = self._build_payload_sha256(body, query_args)

        return {
            "tenant_id": self._normalize_audit_id_value(tenant_id),
            "grupo_empresarial_id": self._normalize_audit_id_value(
                grupo_empresarial_id
            ),
            "area_atendimento_id": self._normalize_audit_id_value(
                area_atendimento_id
            ),
            "request_id": request_id,
            "user_id": user_id,
            "subject_user_id": subject_user_id,
            "session_id": session_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "params_normalizados": params_normalizados or {},
            "commit_json": commit_json,
            "payload_ref": None,
            "payload_sha256": payload_sha256,
            "schema_version": 1,
        }

    def _add_table_name_to_commit_json(self, commit_json: Any | None) -> Any | None:
        if not isinstance(commit_json, dict):
            return commit_json

        table_name = None
        entity_class = getattr(self, "_entity_class", None)
        if entity_class is not None:
            try:
                table_name = entity_class().get_table_name()
            except Exception:
                table_name = None

        if table_name:
            commit_json.setdefault("table_name", table_name)

        return commit_json

    @staticmethod
    def _normalize_audit_id_value(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def _build_commit_json(
        self,
        old_dto: Any | None,
        new_dto: Any | None,
        resource_id: Any | None,
    ) -> Any:
        if old_dto is not None and new_dto is not None:
            old_values = convert_dto_full(old_dto)
            new_values = convert_dto_full(new_dto)
            if not isinstance(old_values, dict) or not isinstance(new_values, dict):
                return new_values
            diff = self._diff_values(old_values, new_values)
            return diff if diff else None

        if new_dto is None:
            if resource_id is None:
                return None
            return {"id": resource_id}

        return convert_dto_full(new_dto)

    @staticmethod
    def _diff_values(
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        diff: Dict[str, Any] = {}
        for key in set(old_values.keys()) | set(new_values.keys()):
            old_value = old_values.get(key)
            new_value = new_values.get(key)
            if old_value != new_value:
                diff[key] = {"old": old_value, "new": new_value}
        return diff

    @staticmethod
    def _build_payload_sha256(body: Any, query_args: Any) -> str | None:
        if body:
            try:
                payload = json.dumps(
                    body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            except TypeError:
                payload = str(body)
        else:
            if hasattr(query_args, "to_dict"):
                payload_source = query_args.to_dict(flat=True)
            else:
                payload_source = dict(query_args or {})
            payload = json.dumps(
                payload_source,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )

        if not payload:
            return None

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _resolve_resource_type(self, resource_id: Any | None) -> str:
        if has_request_context():
            resource = self._resource_from_path(request.path or "", resource_id)
            if resource:
                return resource

        dto_class = getattr(self, "_dto_class", None)
        if dto_class is not None:
            return dto_class.__name__

        return ""

    def _resolve_resource_id(self, dto: Any | None) -> Any | None:
        if dto is None:
            return None
        pk_field = getattr(dto, "pk_field", None)
        if pk_field and hasattr(dto, pk_field):
            return getattr(dto, pk_field)
        return None


    @staticmethod
    def _resource_from_path(path: str, resource_id: Any | None) -> str | None:
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            return None

        if resource_id is not None:
            if len(segments) > 1:
                return segments[-2]
            return None

        return segments[-1]

    @staticmethod
    def _resolve_subject_user_id() -> None:
        return None

    def _resolve_session_id(self) -> str | None:
        profile = getattr(g, "profile", None)
        if isinstance(profile, dict):
            for key in ("session_id", "session", "sessao"):
                value = profile.get(key)
                if value:
                    return str(value)
        return None
