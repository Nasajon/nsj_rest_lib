from nsj_rest_lib.dto.dto_base import DTOBase


def _normalize_query_args(query_args):
    if query_args is None:
        return {}
    if hasattr(query_args, "to_dict"):
        return query_args.to_dict(flat=True)
    return dict(query_args)


def _filter_by_fields_tree(value, fields_tree):
    if not isinstance(value, dict):
        return value

    root_fields = fields_tree.get("root", set())
    result = {}
    for field in root_fields:
        if field not in value:
            continue
        field_value = value[field]
        subtree = fields_tree.get(field)
        if subtree and isinstance(field_value, dict):
            result[field] = _filter_by_fields_tree(field_value, subtree)
        elif subtree and isinstance(field_value, list):
            result[field] = [
                (
                    _filter_by_fields_tree(item, subtree)
                    if isinstance(item, dict)
                    else item
                )
                for item in field_value
            ]
        else:
            result[field] = field_value
    return result


def get_params_normalizados(
    query_args, body, dto_class: type[DTOBase] | None, path_args=None
):
    """
    Normaliza os parâmetros da requisição para auditoria.

    - query_args: parâmetros da query string.
    - body: corpo da requisição (dict ou lista de dicts).
    - dto_class: DTO associado à rota, usado para selecionar campos resumo.
    - path_args: argumentos da rota (kwargs).
    """
    normalized_query_args = _normalize_query_args(query_args)

    if dto_class is None or body is None or body == {}:
        normalized_body = {}
    else:
        fields_tree = dto_class._build_default_fields_tree()
        if isinstance(body, list):
            normalized_body = [
                (
                    _filter_by_fields_tree(item, fields_tree)
                    if isinstance(item, dict)
                    else item
                )
                for item in body
            ]
        elif isinstance(body, dict):
            normalized_body = _filter_by_fields_tree(body, fields_tree)
        else:
            normalized_body = {}

    return {
        "query_args": normalized_query_args,
        "body": normalized_body,
        "path_args": path_args or {},
    }
