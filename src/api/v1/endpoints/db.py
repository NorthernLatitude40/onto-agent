"""DB connection helper: one place for connect / commit / rollback / close."""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as psycopg2_pool
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")


# Create a connection pool for better performance
connection_pool = None

def init_connection_pool(minconn=5, maxconn=20):
    """Initialize the connection pool."""
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2_pool.SimpleConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=DATABASE_URL
        )

def close_connection_pool():
    """Close the connection pool."""
    global connection_pool
    if connection_pool is not None:
        connection_pool.closeall()
        connection_pool = None

@contextmanager
def get_cursor(commit: bool = False):
    # Initialize connection pool on first use
    if connection_pool is None:
        init_connection_pool()
    
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)
