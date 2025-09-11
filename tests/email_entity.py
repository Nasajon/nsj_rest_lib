import datetime

from typing import List

from nsj_rest_lib.entity.entity_base import EntityBase


class EmailEntity(EntityBase):
    id: str = None
    cliente_id: str = None
    email: str = None
    criado_em: datetime.datetime = None
    criado_por: str = None
    atualizado_em: datetime.datetime = None
    atualizado_por: str = None
    apagado_em: datetime.datetime = None
    apagado_por: str = None
    grupo_empresarial: str = None
    tenant: int = None

    def __init__(self) -> None:
        self.id = None
        self.cliente_id = None
        self.email = None
        self.criado_em = None
        self.criado_por = None
        self.atualizado_em = None
        self.atualizado_por = None
        self.apagado_em = None
        self.apagado_por = None
        self.grupo_empresarial = None
        self.tenant = None

    def get_table_name(self) -> str:
        return 'teste.email'

    def get_pk_field(self) -> str:
        return 'id'

    def get_default_order_fields(self) -> List[str]:
        return ['cliente_id', 'email', 'id']
