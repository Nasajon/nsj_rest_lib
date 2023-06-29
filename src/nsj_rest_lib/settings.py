import logging
import os

# Lendo variáveis de ambiente
DEFAULT_PAGE_SIZE = int(os.getenv('DEFAULT_PAGE_SIZE', 20))
USE_SQL_RETURNING_CLAUSE = (
    os.getenv('USE_SQL_RETURNING_CLAUSE', 'true').lower() == 'true')

DATABASE_HOST = os.getenv('DATABASE_HOST', '')
DATABASE_PASS = os.getenv('DATABASE_PASS', '')
DATABASE_PORT = os.getenv('DATABASE_PORT', '')
DATABASE_NAME = os.getenv('DATABASE_NAME', '')
DATABASE_USER = os.getenv('DATABASE_USER', '')
DATABASE_DRIVER = os.getenv('DATABASE_DRIVER', 'POSTGRES')

CLOUD_SQL_CONN_NAME = os.getenv('CLOUD_SQL_CONN_NAME', '')
ENV = os.getenv('ENV', '')

def get_logger():
    APP_NAME = os.getenv('APP_NAME', 'nsj_rest_lib')
    return logging.getLogger(APP_NAME)