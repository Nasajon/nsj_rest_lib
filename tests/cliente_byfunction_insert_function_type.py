from nsj_rest_lib.decorator.insert_function_type import InsertFunctionType
from nsj_rest_lib.descriptor.insert_function_field import InsertFunctionField
from nsj_rest_lib.descriptor.insert_function_relation_field import (
    InsertFunctionRelationField,
)
from nsj_rest_lib.entity.insert_function_type_base import InsertFunctionTypeBase


@InsertFunctionType(
    type_name="teste.tendereco",
    function_name="teste.api_endereco",
)
class ClienteByfunctionEnderecoInsertType(InsertFunctionTypeBase):
    tipologradouro: str = InsertFunctionField()
    logradouro: str = InsertFunctionField()
    numero: str = InsertFunctionField()
    complemento: str = InsertFunctionField()
    cep: str = InsertFunctionField()
    bairro: str = InsertFunctionField()
    tipo: int = InsertFunctionField(type_field_name="tipo")
    enderecopadrao: int = InsertFunctionField()
    referencia: str = InsertFunctionField()
    uf: str = InsertFunctionField()
    cidade: str = InsertFunctionField()


@InsertFunctionType(
    type_name="teste.tclientenovo",
    function_name="teste.api_clientenovo",
)
class ClienteByfunctionInsertType(InsertFunctionTypeBase):
    codigo: str = InsertFunctionField()
    nome: str = InsertFunctionField()
    nomefantasia: str = InsertFunctionField()
    identidade: str = InsertFunctionField()
    documento: str = InsertFunctionField()
    inscricaoestadual: str = InsertFunctionField()
    retemiss: bool = InsertFunctionField()
    retemir: bool = InsertFunctionField()
    retempis: bool = InsertFunctionField()
    retemcofins: bool = InsertFunctionField()
    retemcsll: bool = InsertFunctionField()
    reteminss: bool = InsertFunctionField()
    enderecos: list[ClienteByfunctionEnderecoInsertType] = (
        InsertFunctionRelationField(type_field_name="endereco")
    )
