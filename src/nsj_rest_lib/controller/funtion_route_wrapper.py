import uuid

from flask import g, request
from typing import Any, Callable

from nsj_rest_lib.settings import DATABASE_NAME
from nsj_rest_lib.util.audit_ids_util import (
    retrieve_area_atendimento_id,
    retrieve_grupo_empresarial_id,
    retrieve_tenant_id,
)
from nsj_rest_lib.util.audit_util import AuditUtil, DBTypes, HTTPMethods
from nsj_rest_lib.util.user_audit_util import get_actor_user_id, get_db_user
from nsj_rest_lib.util.util_normaliza_parametros import get_params_normalizados


class FunctionRouteWrapper:
    route_ref_count = {}
    func: Callable

    def __init__(self, route_obj, func: Callable):
        super().__init__()

        self.func = func
        self.route_obj = route_obj

        # Assumindo o nome da rota como o nome da classe
        route_name = route_obj.__class__.__name__

        # Resolvendo o contador de referências dessa mesma rota
        ref_count = FunctionRouteWrapper.route_ref_count.get(route_name, 0) + 1
        FunctionRouteWrapper.route_ref_count[route_name] = ref_count

        # Guardando as propriedades
        self._route_obj = route_obj
        self.__name__ = f"{route_name}_{ref_count}"

    def __call__(self, *args: Any, **kwargs: Any):
        # Registrando auditoria da requisição
        self._record_audit(**kwargs)

        # Retorna o resultado da chamada ao método handle_request do objeto de rota associado
        response = self._route_obj.internal_handle_request(*args, **kwargs)
        return self.func(request, response)

    def _record_audit(self, **kwargs):
        # Gerando ID da requisição
        request_id = uuid.uuid4()
        self.route_obj.set_request_id(request_id)
        g.request_id = request_id

        audit_config = getattr(self.route_obj, "audit_config", None)

        # Recuperando IDs de tenant, grupo_empresarial e area_atendimento
        query_args = request.args
        body = request.get_json(force=True, silent=True)
        tenant_id = retrieve_tenant_id(
            audit_config,
            query_args=query_args,
            body=body,
        )
        grupo_empresarial_id = retrieve_grupo_empresarial_id(
            audit_config,
            query_args=query_args,
            body=body,
        )
        area_atendimento_id = retrieve_area_atendimento_id(
            audit_config,
            query_args=query_args,
            body=body,
        )

        # Montando o conteúdo truncado do body da requisição
        raw_body = request.get_data(cache=True, as_text=True) or None
        request_raw_truncated = raw_body[:255] if raw_body else None

        # Montando os parâmetros normalizados
        params_normalizados = get_params_normalizados(
            query_args=query_args,
            body=body,
            dto_class=getattr(self.route_obj, "_dto_class", None),
            path_args=kwargs,
        )

        # Chamando auditoria de eventos (AuditUtil.emit_request_started)
        audit_util = AuditUtil()
        audit_util.emit_request_started(
            request_id=request_id,
            tenant_id=tenant_id,
            grupo_empresarial_id=grupo_empresarial_id,
            area_atendimento_id=area_atendimento_id,
            db_type=(
                audit_config.db_type
                if audit_config and audit_config.db_type is not None
                else (
                    DBTypes.MULTIBANCO
                    if getattr(g, "external_database", None) is not None
                    else DBTypes.OTHER
                )
            ),
            db_key=(
                getattr(g, "external_database", {}).get("name")
                if getattr(g, "external_database", None)
                else DATABASE_NAME
            ),
            db_user=get_db_user(),
            actor_user_id=get_actor_user_id(),
            subject_user_id=None,
            session_id=None,
            http_method=HTTPMethods.from_value(request.method),
            http_route=request.path,
            action="route_called",
            params_normalizados=params_normalizados,
            request_raw_truncated=request_raw_truncated,
        )
