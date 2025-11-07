import datetime
import uuid

from nsj_rest_lib.entity.entity_base import EntityBase
from nsj_rest_lib.decorator.entity import Entity
from nsj_rest_lib.descriptor.entity_field import EntityField


@Entity(
    table_name="teste.classificacoesfinanceiras",
    pk_field="classificacaofinanceira",
    default_order_fields=["codigo"],
    insert_function="teste.api_classificacaofinanceiranovo",
    insert_type="teste.tclassificacaofinanceiranovo",
)
class ClassificacaoFinanceiraEntity(EntityBase):

    classificacaofinanceira: uuid.UUID = EntityField(
        insert_type_field="idclassificacao",
        insert_by_function=True,
    )
    codigo: str = EntityField(insert_by_function=True)
    descricao: str = EntityField(insert_by_function=True)
    codigocontabil: str = EntityField(insert_by_function=True)
    resumo: str = EntityField(insert_by_function=True)
    situacao: int = None
    versao: int = None
    natureza: int = EntityField(insert_by_function=True)
    paiid: uuid.UUID = EntityField(
        insert_type_field="classificacaopai",
        insert_by_function=True,
    )
    grupoempresarial: uuid.UUID = EntityField(insert_by_function=True)
    lastupdate: datetime.datetime = None
    resumoexplicativo: str = None
    importacao_hash: str = None
    iniciogrupo: bool = None
    apenasagrupador: bool = None
    id_erp: int = None
    padrao: bool = None
    transferencia: bool = EntityField(insert_by_function=True)
    repasse_deducao: bool = EntityField(insert_by_function=True)
    tenant: int = None
    rendimentos: bool = EntityField(insert_by_function=True)
    categoriafinanceira: uuid.UUID = None
    grupobalancete: str = None
    atributo1: str = None
    atributo2: str = None
    atributo3: str = None
