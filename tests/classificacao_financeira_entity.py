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
        insert_type_field="idclassificacao"
    )
    codigo: str = None
    descricao: str = None
    codigocontabil: str = None
    resumo: str = None
    situacao: int = None
    versao: int = None
    natureza: int = None
    paiid: uuid.UUID = None
    grupoempresarial: uuid.UUID = None
    lastupdate: datetime.datetime = None
    resumoexplicativo: str = None
    importacao_hash: str = None
    iniciogrupo: bool = None
    apenasagrupador: bool = None
    id_erp: int = None
    padrao: bool = None
    transferencia: bool = None
    repasse_deducao: bool = None
    tenant: int = None
    rendimentos: bool = None
    categoriafinanceira: uuid.UUID = None
    grupobalancete: str = None
    atributo1: str = None
    atributo2: str = None
    atributo3: str = None
