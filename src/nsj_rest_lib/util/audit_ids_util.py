from flask import request

from nsj_rest_lib.util.audit_config import AuditConfig


def _retrieve_id_from_request(
    keys: list[str],
    custom_field_name: str | None,
    query_args=None,
    body=None,
):
    search_keys = keys
    if custom_field_name and custom_field_name not in search_keys:
        search_keys = [custom_field_name, *search_keys]

    if query_args is None:
        query_args = request.args

    for key in search_keys:
        value = query_args.get(key)
        if value is not None:
            return value

    if body is None:
        body = request.get_json(force=True, silent=True)

    if isinstance(body, dict):
        for key in search_keys:
            value = body.get(key)
            if value is not None:
                return value
    elif isinstance(body, list):
        for item in body:
            if not isinstance(item, dict):
                continue
            for key in search_keys:
                value = item.get(key)
                if value is not None:
                    return value

    return None


def _get_audit_config_field(audit_config: AuditConfig | None, field_name: str):
    if audit_config is None:
        return None
    return getattr(audit_config, field_name, None)


def retrieve_tenant_id(audit_config: AuditConfig | None, query_args=None, body=None):
    """
    Recupera o tenant_id dos parâmetros da requisição, ou do corpo da requisição e o retorna.
    """

    tenant_keys = ["tenant", "tenant_id", "id_tenant", "tenantid", "idtenant"]
    return _retrieve_id_from_request(
        tenant_keys,
        _get_audit_config_field(audit_config, "tenant_field"),
        query_args=query_args,
        body=body,
    )


def retrieve_grupo_empresarial_id(
    audit_config: AuditConfig | None,
    query_args=None,
    body=None,
):
    """
    Recupera o grupo_empresarial_id dos parâmetros da requisição, ou do corpo da requisição e o retorna.
    """

    grupo_empresarial_keys = [
        "grupo_empresarial",
        "grupo_empresarial_id",
        "id_grupo_empresarial",
        "grupoempresarial",
        "grupoempresarial_id",
        "idgrupoempresarial",
    ]
    return _retrieve_id_from_request(
        grupo_empresarial_keys,
        _get_audit_config_field(audit_config, "grupo_empresarial_field"),
        query_args=query_args,
        body=body,
    )


def retrieve_area_atendimento_id(
    audit_config: AuditConfig | None,
    query_args=None,
    body=None,
):
    """
    Recupera o area_atendimento_id dos parâmetros da requisição, ou do corpo da requisição e o retorna.
    """

    area_atendimento_keys = [
        "area_atendimento",
        "area_atendimento_id",
        "id_area_atendimento",
        "areaatendimento",
        "areaatendimento_id",
        "idareaatendimento",
    ]
    return _retrieve_id_from_request(
        area_atendimento_keys,
        _get_audit_config_field(audit_config, "area_atendimento_field"),
        query_args=query_args,
        body=body,
    )
