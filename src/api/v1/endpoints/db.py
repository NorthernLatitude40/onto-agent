"""DB connection helper: one place for connect / commit / rollback / close."""
import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")


@contextmanager
def get_cursor(commit: bool = False):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
