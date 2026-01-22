from dataclasses import dataclass

from nsj_rest_lib.util.audit_util import DBTypes


@dataclass(frozen=True, slots=True)
class AuditConfig:
    tenant_field: str | None = None
    grupo_empresarial_field: str | None = None
    area_atendimento_field: str | None = None
    db_type: DBTypes | None = None
