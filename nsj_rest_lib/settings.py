import os

# Lendo variáveis de ambiente
DEFAULT_PAGE_SIZE = int(os.getenv('DEFAULT_PAGE_SIZE', 20))
USE_SQL_RETURNING_CLAUSE = (
    os.getenv('USE_SQL_RETURNING_CLAUSE', 'true').lower == 'true')
