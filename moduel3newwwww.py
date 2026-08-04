# ============================================================
# Module_3_V2.py
# Part 1A
# Imports | Configuration | Logging | DB Connection | Helpers
# Business Logic : UNCHANGED
# Optimized For  : SQL Server 2019
# ============================================================

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime

import pyodbc

# ------------------------------------------------------------
# GLOBAL SETTINGS
# ------------------------------------------------------------

APP_NAME = "Module_3_V2"
VERSION = "2.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

START_TIME = time.perf_counter()


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------

LOG_DIR = os.path.join(BASE_DIR, "Logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    f"Module3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(APP_NAME)


# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

try:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

except Exception as ex:

    logger.exception("Unable to read config.json")
    raise


db = config["database"]

SERVER = db["server"]
DATABASE = db["name"]
DRIVER = db["driver"]

TRUSTED = "yes" if db["trusted_connection"] else "no"

MASTER_DATABASE = "master"

MASTER_CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={MASTER_DATABASE};"
    f"Trusted_Connection={TRUSTED};"
)

DB_CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"Trusted_Connection={TRUSTED};"
)


# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------

def create_connection(
        connection_string,
        autocommit=True,
        timeout=0):

    conn = pyodbc.connect(
        connection_string,
        autocommit=autocommit,
        timeout=timeout
    )

    return conn


def create_cursor(connection):

    cur = connection.cursor()

    cur.fast_executemany = True

    return cur


# ------------------------------------------------------------
# SAFE SQL EXECUTION
# ------------------------------------------------------------

def execute_sql(cursor, sql, params=None):

    if params:

        cursor.execute(sql, params)

    else:

        cursor.execute(sql)


def execute_many(cursor, sql, values):

    cursor.fast_executemany = True

    cursor.executemany(sql, values)


# ------------------------------------------------------------
# TIMER
# ------------------------------------------------------------

@contextmanager
def timer(title):

    start = time.perf_counter()

    logger.info("-" * 65)
    logger.info(f"START : {title}")

    try:

        yield

    finally:

        elapsed = time.perf_counter() - start

        logger.info(
            f"END   : {title} "
            f"({elapsed:.2f} sec)"
        )

        logger.info("-" * 65)


# ------------------------------------------------------------
# COMMIT
# ------------------------------------------------------------

def safe_commit(connection):

    try:

        connection.commit()

    except Exception:

        logger.exception("Commit Failed")

        raise


# ------------------------------------------------------------
# SQL EXECUTION WITH LOGGING
# ------------------------------------------------------------

def run_sql(cursor, sql, commit=False, connection=None):

    cursor.execute(sql)

    if commit:

        connection.commit()


# ------------------------------------------------------------
# DATABASE INITIALIZATION
# ------------------------------------------------------------

def initialize_master_connection():

    logger.info("Connecting to MASTER database...")

    conn = create_connection(MASTER_CONN_STR)

    cursor = create_cursor(conn)

    return conn, cursor


def initialize_staging_connection():

    logger.info(f"Connecting to {DATABASE}...")

    conn = create_connection(DB_CONN_STR)

    cursor = create_cursor(conn)

    return conn, cursor


# ------------------------------------------------------------
# RETRY WRAPPER
# ------------------------------------------------------------

def retry_sql(function, retries=3, wait=5):

    for attempt in range(retries):

        try:

            return function()

        except Exception as ex:

            logger.warning(
                f"Retry {attempt + 1}/{retries} : {ex}"
            )

            if attempt == retries - 1:
                raise

            time.sleep(wait)


# ------------------------------------------------------------
# CLEAN CLOSE
# ------------------------------------------------------------

def close_connection(connection, cursor):

    try:

        if cursor is not None:
            cursor.close()

    except Exception:
        pass

    try:

        if connection is not None:
            connection.close()

    except Exception:
        pass


logger.info("=" * 70)
logger.info(f"{APP_NAME} Started")
logger.info(f"Version : {VERSION}")
logger.info("=" * 70)


# ============================================================
# PART 1B
# Database Initialization
# (Business Logic UNCHANGED)
# ============================================================

def prepare_staging_database():
    """
    Same business logic as Module_3.py.
    Only code structure and logging are improved.
    """

    logger.info("")
    logger.info("=" * 70)
    logger.info("Preparing Staging Database...")
    logger.info("=" * 70)

    master_conn = None
    master_cursor = None

    try:

        master_conn, master_cursor = initialize_master_connection()

        with timer("Clear Database Locks"):

            master_cursor.execute(f"""
                ALTER DATABASE {DATABASE}
                SET SINGLE_USER
                WITH ROLLBACK IMMEDIATE
            """)

            master_cursor.execute(f"""
                ALTER DATABASE {DATABASE}
                SET RECOVERY SIMPLE
            """)

            master_cursor.execute(f"""
                ALTER DATABASE {DATABASE}
                MODIFY FILE
                (
                    NAME = {DATABASE}_log,
                    FILEGROWTH = 512MB,
                    MAXSIZE = UNLIMITED
                )
            """)

            master_cursor.execute(f"""
                ALTER DATABASE {DATABASE}
                SET MULTI_USER
            """)

        logger.info("Database prepared successfully.")

    except Exception as ex:

        logger.warning(
            f"Database preparation warning : {ex}"
        )

    finally:

        close_connection(master_conn, master_cursor)


# ============================================================
# STAGING CONNECTION
# ============================================================

def initialize_database():

    conn = None
    cursor = None

    try:

        conn, cursor = initialize_staging_connection()

        with timer("Initialize Staging Database"):

            cursor.execute(f"USE {DATABASE}")

            cursor.execute("CHECKPOINT")

            cursor.execute(f"""
                DBCC SHRINKFILE
                (
                    {DATABASE}_log,
                    10
                )
            """)

        logger.info("Staging database ready.")

        return conn, cursor

    except Exception:

        logger.exception(
            "Unable to initialize staging database."
        )

        close_connection(conn, cursor)

        raise


# ============================================================
# COUNTRY TABLE INITIALIZATION
# ============================================================

def ensure_country_table(cursor, conn):

    with timer("Country Table Validation"):

        cursor.execute("""

            IF OBJECT_ID('Country','U') IS NULL

            BEGIN

                CREATE TABLE Country
                (

                    tISO NVARCHAR(10) NULL,

                    tCountry NVARCHAR(100) NULL

                )

            END

        """)

        safe_commit(conn)


# ============================================================
# COUNTRY DATA CHECK
# ============================================================

def country_table_is_empty(cursor):

    cursor.execute("""

        SELECT COUNT(*)

        FROM Country

    """)

    return cursor.fetchone()[0] == 0


# ============================================================
# STARTUP
# ============================================================

logger.info("")
logger.info("Starting Module 3 Processing...")

prepare_staging_database()

conn, cursor = initialize_database()

ensure_country_table(cursor, conn)

global_start = time.perf_counter()
