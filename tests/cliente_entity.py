import datetime

from typing import List

from nsj_rest_lib.entity.entity_base import EntityBase


class ClienteEntity(EntityBase):

    # Atributos do relacionamento
    id: str
    estabelecimento: str
    cliente: str
    # Atributos de auditoria
    criado_em: datetime.datetime
    criado_por: str
    atualizado_em: datetime.datetime
    atualizado_por: str
    apagado_em: datetime.datetime
    apagado_por: str
    # Atributos de segmentação dos dados
    grupo_empresarial: str
    tenant: int

    def __init__(self) -> None:
        # Atributos do relacionamento
        self.id: str = None
        self.estabelecimento: str = None
        self.cliente: str = None
        # Atributos de auditoria
        self.criado_em: datetime.datetime = None
        self.criado_por: str = None
        self.atualizado_em: datetime.datetime = None
        self.atualizado_por: str = None
        self.apagado_em: datetime.datetime = None
        self.apagado_por: str = None
        # Atributos de segmentação dos dados
        self.grupo_empresarial: str = None
        self.tenant: int = None

    def get_table_name(self) -> str:
        return 'teste.cliente'

    def get_pk_field(self) -> str:
        return 'id'

    def get_default_order_fields(self) -> List[str]:
        return ['estabelecimento', 'cliente', 'id']
