"""
Utility functions for database interactions (connection setup, reusable queries).

Connection management (get_db_connection).
Low-level database operations (execute_query).
"""

from typing import Generator
from contextlib import contextmanager
import psycopg
from psycopg.connection import Connection
from config import POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
from utils.logging import configure_logging

logger = configure_logging(__name__)


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """
    Establish a connection to the Postgres database and ensure cleanup.

    Yields:
        Connection: A psycopg Connection object.
    """
    connection = None
    try:
        connection = psycopg.connect(
            host=POSTGRES_HOST,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        yield connection
    except Exception as e:
        logger.error("Error establishing database connection: %s", e)
        raise
    finally:
        if connection and not connection.closed:
            connection.close()
            logger.debug("Database connection closed.")


def build_insert_query(table_name, columns, values):
    """
    Build a parameterized SQL INSERT query.

    Parameters:
    - table_name (str): Name of the target database table.
    - columns (list): List of column names to insert values into.
    - values (list): List of corresponding values to insert.

    Returns:
    - tuple: (query, values) where `query` is the constructed SQL string
             and `values` is the list of values for parameterized execution.
    """
    query = f"""
        INSERT INTO {table_name} ({', '.join(columns)})
        VALUES ({', '.join(['%s'] * len(values))})
    """
    return query, values


def execute_query(cursor, query, values):
    """
    Execute a SQL query with the given values.
    """
    try:
        resolved_query = query % tuple(values)
        logger.debug("Executing query: %s", resolved_query)
        cursor.execute(query, values)
    except psycopg.errors.DatabaseError as e:
        logger.error("Database error: %s", e)
        raise
