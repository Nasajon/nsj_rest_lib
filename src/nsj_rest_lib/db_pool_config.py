from nsj_rest_lib.settings import DATABASE_HOST
from nsj_rest_lib.settings import DATABASE_PASS
from nsj_rest_lib.settings import DATABASE_PORT
from nsj_rest_lib.settings import DATABASE_NAME
from nsj_rest_lib.settings import DATABASE_USER
from nsj_rest_lib.settings import DATABASE_DRIVER
from nsj_rest_lib.settings import CLOUD_SQL_CONN_NAME
from nsj_rest_lib.settings import ENV
from nsj_rest_lib.settings import DB_POOL_SIZE

import sqlalchemy

from sqlalchemy.engine import URL

def create_pool(database_conn_url):
    # Creating database connection pool
    db_pool = sqlalchemy.create_engine(
        database_conn_url,
        # pool_size=DB_POOL_SIZE,
        # max_overflow=2,
        # pool_timeout=30,
        # pool_recycle=1800,
        poolclass=sqlalchemy.pool.NullPool,
    )
    return db_pool


if DATABASE_DRIVER.upper() in ["SINGLE_STORE", "MYSQL"]:
    database_conn_url = URL.create(
                            "mysql+pymysql", 
                            username=DATABASE_USER,
                            password=DATABASE_PASS,
                            host=DATABASE_HOST, 
                            database=DATABASE_NAME,
                            port=DATABASE_PORT,
                        )  
else:
    if ENV.upper() == "GCP":
        database_conn_url = f"postgresql+pg8000://{DATABASE_USER}:{DATABASE_PASS}@/{DATABASE_NAME}?unix_sock=/cloudsql/{CLOUD_SQL_CONN_NAME}/.s.PGSQL.{DATABASE_PORT}"
    else:
        database_conn_url = URL.create(
                                "postgresql+pg8000", 
                                username=DATABASE_USER,
                                password=DATABASE_PASS,
                                host=DATABASE_HOST, 
                                database=DATABASE_NAME,
                                port=DATABASE_PORT,
                            )            

def default_create_pool():
    return create_pool(database_conn_url)


# db_pool = create_pool(database_conn_url)
