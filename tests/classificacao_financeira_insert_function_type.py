import uuid

from nsj_rest_lib.decorator.insert_function_type import InsertFunctionType
from nsj_rest_lib.descriptor.function_field import FunctionField
from nsj_rest_lib.entity.function_type_base import InsertFunctionTypeBase


@InsertFunctionType(
    type_name="teste.tclassificacaofinanceiranovo",
    function_name="teste.api_classificacaofinanceiranovo",
)
class ClassificacaoFinanceiraInsertType(InsertFunctionTypeBase):
    id: uuid.UUID = FunctionField(type_field_name="idclassificacao")
    codigo: str = FunctionField()
    descricao_func: str = FunctionField(type_field_name="descricao")
    codigocontabil: str = FunctionField()
    resumo: str = FunctionField()
    natureza: int = FunctionField()
    paiid: uuid.UUID = FunctionField(type_field_name="classificacaopai")
    grupoempresarial: uuid.UUID = FunctionField()
    transferencia: bool = FunctionField()
    repasse_deducao: bool = FunctionField()
    rendimentos: bool = FunctionField()
