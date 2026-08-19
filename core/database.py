import psycopg2
import psycopg2.extras
from core.config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB

def get_contratos_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def get_folha_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def get_pca_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn
