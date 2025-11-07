import uuid

from nsj_rest_lib.decorator.insert_function_type import InsertFunctionType
from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase


@InsertFunctionType(
    type_name="teste.tclassificacaofinanceiranovo",
    function_name="teste.api_classificacaofinanceiranovo",
)
class ClassificacaoFinanceiraInsertType(InsertFunctionTypeBase):
    id: uuid.UUID = InsertFunctionField(type_field_name="idclassificacao")
    codigo: str = InsertFunctionField()
    descricao_func: str = InsertFunctionField(type_field_name="descricao")
    codigocontabil: str = InsertFunctionField()
    resumo: str = InsertFunctionField()
    natureza: int = InsertFunctionField()
    paiid: uuid.UUID = InsertFunctionField(type_field_name="classificacaopai")
    grupoempresarial: uuid.UUID = InsertFunctionField()
    transferencia: bool = InsertFunctionField()
    repasse_deducao: bool = InsertFunctionField()
    rendimentos: bool = InsertFunctionField()
