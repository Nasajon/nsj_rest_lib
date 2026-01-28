from typing import Dict, Tuple

from nsj_rest_lib.settings import DATABASE_DRIVER, get_logger


class AuditDBModelUtil:
    _COLUMN_TYPES: Dict[str, str] = {
        "outbox_id": "uuid",
        "outbox_seq": "bigint",
        "created_at": "timestamptz",
        "tenant_id": "varchar(150)",
        "grupo_empresarial_id": "varchar(150)",
        "area_atendimento_id": "varchar(150)",
        "request_id": "uuid",
        "user_id": "text",
        "subject_user_id": "text",
        "session_id": "text",
        "action": "text",
        "resource_type": "text",
        "resource_id": "text",
        "params_normalizados": "jsonb",
        "commit_json": "jsonb",
        "payload_ref": "text",
        "payload_sha256": "text",
        "schema_version": "integer",
    }

    _CREATE_COLUMNS: Tuple[str, ...] = (
        "outbox_id uuid PRIMARY KEY",
        "outbox_seq bigserial",
        "created_at timestamptz NOT NULL DEFAULT now()",
        "tenant_id varchar(150) NULL",
        "grupo_empresarial_id varchar(150) NULL",
        "area_atendimento_id varchar(150) NULL",
        "request_id uuid NOT NULL",
        "user_id text NOT NULL",
        "subject_user_id text NULL",
        "session_id text NULL",
        "action text NOT NULL",
        "resource_type text NOT NULL",
        "resource_id text NULL",
        "params_normalizados jsonb NOT NULL DEFAULT '{}'::jsonb",
        "commit_json jsonb NULL",
        "payload_ref text NULL",
        "payload_sha256 text NULL",
        "schema_version integer NOT NULL DEFAULT 1",
    )

    _INDEXES: Tuple[str, ...] = (
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_outbox_seq ON audit_outbox (outbox_seq)",
        "CREATE INDEX IF NOT EXISTS ix_outbox_tenant_ge_request ON audit_outbox (tenant_id, grupo_empresarial_id, request_id)",
        "CREATE INDEX IF NOT EXISTS ix_outbox_tenant_ge_created ON audit_outbox (tenant_id, grupo_empresarial_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_outbox_tenant_ge_seq ON audit_outbox (tenant_id, grupo_empresarial_id, outbox_seq)",
    )

    _TYPE_MATCHERS: Dict[str, Tuple[str, ...]] = {
        "uuid": ("uuid",),
        "bigint": ("bigint", "int8"),
        "integer": ("integer", "int4"),
        "text": ("text",),
        "varchar(150)": ("character varying", "varchar"),
        "jsonb": ("jsonb",),
        "timestamptz": ("timestamp with time zone", "timestamptz"),
    }
    _NULLABLE_COLUMNS = {"tenant_id", "grupo_empresarial_id", "area_atendimento_id"}

    @classmethod
    def _is_postgres(cls, db=None) -> bool:
        detected = cls._detect_db_driver(db)
        if detected is not None:
            return detected.startswith("postgres")
        return DATABASE_DRIVER.lower().startswith("postgres")

    @classmethod
    def is_postgres(cls, db=None) -> bool:
        return cls._is_postgres(db)

    @classmethod
    def _detect_db_driver(cls, db) -> str | None:
        if db is None:
            return None

        # Direct string driver on adapter
        for attr in ("driver", "db_driver", "database_driver", "dialect_name", "db_dialect"):
            value = getattr(db, attr, None)
            if isinstance(value, str) and value:
                return value.lower()

        candidates = [db]
        for attr in (
            "_db",
            "engine",
            "_engine",
            "connection",
            "_connection",
            "conn",
            "_conn",
        ):
            obj = getattr(db, attr, None)
            if obj is not None:
                candidates.append(obj)

        for obj in candidates:
            # SQLAlchemy engine/connection: dialect.name
            dialect = getattr(obj, "dialect", None)
            if dialect is not None:
                name = getattr(dialect, "name", None)
                if isinstance(name, str) and name:
                    return name.lower()
                driver = getattr(dialect, "driver", None)
                if isinstance(driver, str) and driver:
                    return driver.lower()

            url = getattr(obj, "url", None)
            if url is not None:
                drivername = getattr(url, "drivername", None)
                if isinstance(drivername, str) and drivername:
                    return drivername.lower()
                get_backend_name = getattr(url, "get_backend_name", None)
                if callable(get_backend_name):
                    try:
                        backend = get_backend_name()
                    except Exception:
                        backend = None
                    if isinstance(backend, str) and backend:
                        return backend.lower()

            name = getattr(obj, "name", None)
            if isinstance(name, str) and name:
                return name.lower()

        return None

    @staticmethod
    def is_audit_outbox_model_error(exc: Exception) -> bool:
        message = str(exc).lower()
        if "audit_outbox" not in message:
            return False
        return any(
            token in message
            for token in (
                "does not exist",
                "undefined",
                "column",
                "relation",
                "datatype",
                "type",
            )
        )

    @classmethod
    def ensure_audit_outbox_schema(cls, db) -> None:
        if not cls._is_postgres(db):
            return

        if not cls._table_exists(db):
            cls._create_table(db)
        else:
            cls._ensure_columns(db)
            cls._ensure_types(db)
            cls._ensure_nullability(db)

        cls._ensure_indexes(db)

    @classmethod
    def _table_exists(cls, db) -> bool:
        row = db.execute_query_first_result(
            """
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = 'audit_outbox'
            """
        )
        return row is not None

    @classmethod
    def _create_table(cls, db) -> None:
        columns_sql = ",\n    ".join(cls._CREATE_COLUMNS)
        sql = f"""
        CREATE TABLE IF NOT EXISTS audit_outbox (
            {columns_sql}
        );
        """
        db.execute(sql)

    @classmethod
    def _ensure_columns(cls, db) -> None:
        rows = db.execute_query(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'audit_outbox'
            """
        )
        existing = {row["column_name"] for row in rows}

        for column_name, column_type in cls._COLUMN_TYPES.items():
            if column_name in existing:
                continue
            db.execute(
                f"ALTER TABLE audit_outbox ADD COLUMN {column_name} {column_type}"
            )

    @classmethod
    def _ensure_types(cls, db) -> None:
        rows = db.execute_query(
            """
            SELECT column_name, data_type, udt_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'audit_outbox'
            """
        )
        columns = {
            row["column_name"]: (row["data_type"], row["udt_name"]) for row in rows
        }

        for column_name, column_type in cls._COLUMN_TYPES.items():
            current = columns.get(column_name)
            if current is None:
                continue

            data_type, udt_name = current
            valid_types = cls._TYPE_MATCHERS.get(column_type, (column_type,))
            if data_type in valid_types or udt_name in valid_types:
                continue

            db.execute(
                f"ALTER TABLE audit_outbox ALTER COLUMN {column_name} "
                f"TYPE {column_type} USING {column_name}::{column_type}"
            )

    @classmethod
    def _ensure_nullability(cls, db) -> None:
        rows = db.execute_query(
            """
            SELECT column_name, is_nullable
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'audit_outbox'
            """
        )
        nullable_map = {row["column_name"]: row["is_nullable"] for row in rows}

        for column_name in cls._NULLABLE_COLUMNS:
            if nullable_map.get(column_name) == "NO":
                db.execute(
                    f"ALTER TABLE audit_outbox ALTER COLUMN {column_name} DROP NOT NULL"
                )

    @classmethod
    def _ensure_indexes(cls, db) -> None:
        for sql in cls._INDEXES:
            try:
                db.execute(sql)
            except Exception as exc:
                get_logger().warning(f"Erro criando indice de audit_outbox: {exc}")
