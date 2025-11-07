import datetime
import uuid

from nsj_rest_lib.decorator.dto import DTO
from nsj_rest_lib.descriptor.dto_field import DTOField, DTOFieldFilter
from nsj_rest_lib.descriptor.dto_field_validators import DTOFieldValidators
from nsj_rest_lib.descriptor.filter_operator import FilterOperator
from nsj_rest_lib.dto.dto_base import DTOBase


@DTO()
class ClassificacaoFinanceiraDTO(DTOBase):

    classificacaofinanceira: uuid.UUID = DTOField(
        pk=True,
        resume=True,
        not_null=True,
        default_value=uuid.uuid4,
        strip=True,
        min=36,
        max=36,
        validator=DTOFieldValidators().validate_uuid,
    )

    codigo: str = DTOField(resume=True, not_null=True, strip=True, min=1, max=30)
    descricao: str = DTOField(strip=True, min=1, max=150)
    codigocontabil: str = DTOField(strip=True, min=1, max=20)
    resumo: str = DTOField(strip=True, min=1, max=30)
    situacao: int = DTOField(not_null=True, default_value=0)
    versao: int = DTOField(default_value=1)
    natureza: int = DTOField(default_value=0)
    paiid: uuid.UUID = DTOField()
    grupoempresarial: uuid.UUID = DTOField()
    resumoexplicativo: str = DTOField()
    importacao_hash: str = DTOField()
    iniciogrupo: bool = DTOField(default_value=False)
    apenasagrupador: bool = DTOField(default_value=False)
    id_erp: int = DTOField()
    padrao: bool = DTOField(default_value=False)
    transferencia: bool = DTOField(default_value=False)
    repasse_deducao: bool = DTOField(default_value=False)
    tenant: int = DTOField()
    rendimentos: bool = DTOField(default_value=False)
    categoriafinanceira: uuid.UUID = DTOField()
    grupobalancete: str = DTOField(strip=True, min=1, max=150)
    atributo1: str = DTOField(strip=True, min=1, max=50)
    atributo2: str = DTOField(strip=True, min=1, max=50)
    atributo3: str = DTOField(strip=True, min=1, max=50)

    # Auditoria
    atualizado_em: datetime.datetime = DTOField(
        resume=True,
        filters=[
            DTOFieldFilter("atualizado_apos", FilterOperator.GREATER_THAN),
            DTOFieldFilter("atualizado_antes", FilterOperator.LESS_THAN),
        ],
        default_value=datetime.datetime.now,
        entity_field="lastupdate",
    )
