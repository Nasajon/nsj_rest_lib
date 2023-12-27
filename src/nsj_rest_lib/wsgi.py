# Importando arquivos de configuração
import nsj_rest_lib.db_pool_config
from nsj_rest_lib.settings import application

# Configurando o healthcheck
from nsj_rest_lib.healthcheck_config import HealthCheckConfig

HealthCheckConfig(flask_application=application).config(True)

import tests.cliente_controller

if __name__ == "__main__":
    application.run(port=5000)