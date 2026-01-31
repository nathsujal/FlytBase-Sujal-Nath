import psycopg2
from contextlib import contextmanager
from src.config.settings import settings


def writer_conn():
    return psycopg2.connect(
        dbname=settings.pg_database_name,
        user=settings.pg_writer,
        password=settings.pg_writer_password,
        host=settings.pg_host,
        port=settings.pg_port
    )

def reader_conn():
    return psycopg2.connect(
        dbname=settings.pg_database_name,
        user=settings.pg_reader,
        password=settings.pg_reader_password,
        host=settings.pg_host,
        port=settings.pg_port
    )


# Context managers for cleaner usage
@contextmanager
def get_writer():
    """Context manager for write operations with auto-commit/rollback."""
    conn = writer_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_reader():
    """Context manager for read operations with auto-close."""
    conn = reader_conn()
    try:
        yield conn
    finally:
        conn.close()