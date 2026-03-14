"""Database tools — connect and query any database engine.

Supports PostgreSQL, MySQL, SQLite, MongoDB, Redis, MSSQL, and MariaDB.
Users provide connection credentials; the agent can then create schemas,
run queries, migrate data, and verify deployments.

Requires the appropriate Python driver to be installed:
  - PostgreSQL: psycopg2 or psycopg
  - MySQL/MariaDB: mysql-connector-python or pymysql
  - SQLite: built-in
  - MongoDB: pymongo
  - Redis: redis
  - MSSQL: pyodbc or pymssql
"""

import json
import os
import sqlite3
from typing import Any


QUERY_TIMEOUT = 30  # seconds
MAX_ROWS = 200  # limit result rows to prevent huge outputs


def _format_rows(columns: list[str], rows: list[tuple], count: int) -> str:
    """Format query results as a readable table."""
    if not rows:
        return f"Query OK. {count} row(s) affected."

    # Build simple table
    lines = []
    col_widths = [len(str(c)) for c in columns]
    for row in rows[:MAX_ROWS]:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], min(len(str(val)), 50))

    # Header
    header = " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(columns))
    sep = "-+-".join("-" * w for w in col_widths)
    lines.append(header)
    lines.append(sep)

    # Rows
    for row in rows[:MAX_ROWS]:
        line = " | ".join(str(v)[:50].ljust(col_widths[i]) for i, v in enumerate(row))
        lines.append(line)

    if len(rows) > MAX_ROWS:
        lines.append(f"... ({len(rows) - MAX_ROWS} more rows)")

    lines.append(f"\n({len(rows)} row(s))")
    return "\n".join(lines)


def _connect_sqlite(connection_string: str) -> tuple:
    """Connect to SQLite and return (connection, cursor)."""
    # connection_string is just the file path for SQLite
    path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
    if not path or path == ":memory:":
        path = ":memory:"
    conn = sqlite3.connect(path, timeout=QUERY_TIMEOUT)
    conn.row_factory = None
    return conn, conn.cursor()


def _connect_postgres(connection_string: str, host: str, port: int, database: str,
                       username: str, password: str) -> tuple:
    """Connect to PostgreSQL."""
    try:
        import psycopg2
    except ImportError:
        try:
            import psycopg as psycopg2
        except ImportError:
            raise ImportError("Install psycopg2: pip install psycopg2-binary")

    if connection_string:
        conn = psycopg2.connect(connection_string)
    else:
        conn = psycopg2.connect(
            host=host or "localhost",
            port=port or 5432,
            dbname=database,
            user=username,
            password=password,
        )
    return conn, conn.cursor()


def _connect_mysql(connection_string: str, host: str, port: int, database: str,
                    username: str, password: str) -> tuple:
    """Connect to MySQL/MariaDB."""
    try:
        import mysql.connector
        if connection_string:
            # Parse connection string
            parts = {}
            for part in connection_string.replace("mysql://", "").split("?")[0].split("/"):
                pass
            conn = mysql.connector.connect(
                host=host or "localhost",
                port=port or 3306,
                database=database,
                user=username,
                password=password,
            )
        else:
            conn = mysql.connector.connect(
                host=host or "localhost",
                port=port or 3306,
                database=database,
                user=username,
                password=password,
            )
        return conn, conn.cursor()
    except ImportError:
        pass

    try:
        import pymysql
        conn = pymysql.connect(
            host=host or "localhost",
            port=port or 3306,
            database=database,
            user=username,
            password=password,
        )
        return conn, conn.cursor()
    except ImportError:
        raise ImportError("Install mysql driver: pip install mysql-connector-python")


def _connect_mssql(connection_string: str, host: str, port: int, database: str,
                    username: str, password: str) -> tuple:
    """Connect to Microsoft SQL Server."""
    try:
        import pymssql
        conn = pymssql.connect(
            server=host or "localhost",
            port=str(port or 1433),
            database=database,
            user=username,
            password=password,
        )
        return conn, conn.cursor()
    except ImportError:
        pass

    try:
        import pyodbc
        if connection_string:
            conn = pyodbc.connect(connection_string)
        else:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={host or 'localhost'},{port or 1433};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password}"
            )
            conn = pyodbc.connect(conn_str)
        return conn, conn.cursor()
    except ImportError:
        raise ImportError("Install MSSQL driver: pip install pymssql")


def _query_mongodb(action: str, host: str, port: int, database: str,
                    username: str, password: str, connection_string: str,
                    query: str) -> str:
    """Handle MongoDB operations (NoSQL, different API)."""
    try:
        import pymongo
    except ImportError:
        return "Error: Install pymongo: pip install pymongo"

    try:
        if connection_string:
            client = pymongo.MongoClient(connection_string, serverSelectionTimeoutMS=QUERY_TIMEOUT * 1000)
        else:
            uri = f"mongodb://"
            if username and password:
                uri += f"{username}:{password}@"
            uri += f"{host or 'localhost'}:{port or 27017}"
            if database:
                uri += f"/{database}"
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=QUERY_TIMEOUT * 1000)

        db = client[database] if database else client.get_default_database()

        if action == "list-tables":
            collections = db.list_collection_names()
            return "Collections:\n" + "\n".join(f"  - {c}" for c in collections) if collections else "No collections."

        elif action == "query":
            # Parse JSON query: {"collection": "users", "filter": {"age": {"$gt": 25}}}
            try:
                q = json.loads(query)
            except json.JSONDecodeError:
                return "Error: MongoDB query must be JSON. Example: {\"collection\": \"users\", \"filter\": {\"age\": {\"$gt\": 25}}}"

            collection_name = q.get("collection", "")
            if not collection_name:
                return "Error: 'collection' key required in query JSON"

            coll = db[collection_name]
            op = q.get("operation", "find")

            if op == "find":
                cursor = coll.find(q.get("filter", {})).limit(MAX_ROWS)
                docs = list(cursor)
                for doc in docs:
                    doc["_id"] = str(doc["_id"])
                return json.dumps(docs, indent=2, default=str) if docs else "No documents found."

            elif op == "insert":
                data = q.get("document") or q.get("documents", [])
                if isinstance(data, list):
                    result = coll.insert_many(data)
                    return f"Inserted {len(result.inserted_ids)} document(s)."
                else:
                    result = coll.insert_one(data)
                    return f"Inserted document with _id: {result.inserted_id}"

            elif op == "update":
                result = coll.update_many(q.get("filter", {}), q.get("update", {}))
                return f"Matched: {result.matched_count}, Modified: {result.modified_count}"

            elif op == "delete":
                result = coll.delete_many(q.get("filter", {}))
                return f"Deleted {result.deleted_count} document(s)."

            elif op == "count":
                count = coll.count_documents(q.get("filter", {}))
                return f"Count: {count}"

            elif op == "aggregate":
                pipeline = q.get("pipeline", [])
                results = list(coll.aggregate(pipeline))
                for doc in results:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                return json.dumps(results, indent=2, default=str)

            else:
                return f"Error: Unknown operation '{op}'. Use: find, insert, update, delete, count, aggregate"

        elif action == "info":
            server_info = client.server_info()
            return json.dumps({
                "version": server_info.get("version"),
                "database": database,
                "collections": db.list_collection_names(),
            }, indent=2)

        else:
            return "Error: For MongoDB, supported actions: query, list-tables, info"

    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        try:
            client.close()
        except Exception:
            pass


def _query_redis(action: str, host: str, port: int, password: str,
                  connection_string: str, query: str) -> str:
    """Handle Redis operations."""
    try:
        import redis
    except ImportError:
        return "Error: Install redis: pip install redis"

    try:
        if connection_string:
            client = redis.from_url(connection_string, socket_timeout=QUERY_TIMEOUT)
        else:
            client = redis.Redis(
                host=host or "localhost",
                port=port or 6379,
                password=password or None,
                socket_timeout=QUERY_TIMEOUT,
                decode_responses=True,
            )

        if action == "info":
            info = client.info()
            return json.dumps({
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": sum(info.get(f"db{i}", {}).get("keys", 0) for i in range(16)),
            }, indent=2)

        elif action == "query":
            # Parse command: "GET mykey" or "SET mykey myvalue"
            parts = query.strip().split(None, 2)
            if not parts:
                return "Error: Provide a Redis command, e.g. 'GET mykey', 'SET mykey value', 'KEYS *'"

            cmd = parts[0].upper()
            cmd_args = parts[1:] if len(parts) > 1 else []

            result = client.execute_command(cmd, *cmd_args)

            if isinstance(result, (list, set)):
                items = [str(r) for r in result]
                return "\n".join(items[:MAX_ROWS]) if items else "(empty)"
            elif isinstance(result, dict):
                return json.dumps({str(k): str(v) for k, v in result.items()}, indent=2)
            elif result is None:
                return "(nil)"
            else:
                return str(result)

        elif action == "list-tables":
            keys = client.keys("*")
            if not keys:
                return "No keys found."
            lines = []
            for key in keys[:MAX_ROWS]:
                key_type = client.type(key)
                lines.append(f"  {key} ({key_type})")
            result = f"Keys ({len(keys)} total):\n" + "\n".join(lines)
            if len(keys) > MAX_ROWS:
                result += f"\n... ({len(keys) - MAX_ROWS} more)"
            return result

        else:
            return "Error: For Redis, supported actions: query, list-tables, info"

    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        try:
            client.close()
        except Exception:
            pass


def database_tool(
    action: str,
    engine: str = "sqlite",
    query: str = "",
    host: str = "",
    port: int = 0,
    database: str = "",
    username: str = "",
    password: str = "",
    connection_string: str = "",
) -> str:
    """Connect to and query any database engine.

    Args:
        action: One of:
          query: Execute SQL query (SELECT, INSERT, UPDATE, DELETE, CREATE, etc.)
          list-tables: List all tables/collections in the database
          describe: Describe a table's schema (target = table name in query param)
          info: Get database server info and version
        engine: Database engine — sqlite, postgres, mysql, mariadb, mssql, mongodb, redis
        query: SQL query string, or JSON for MongoDB, or Redis command
        host: Database host (default: localhost)
        port: Database port (default: engine-specific)
        database: Database name (or file path for SQLite)
        username: Database username
        password: Database password
        connection_string: Full connection string (overrides individual params)
    """
    action = action.lower().strip()
    engine = engine.lower().strip()

    # --- MongoDB (NoSQL) ---
    if engine == "mongodb" or engine == "mongo":
        return _query_mongodb(action, host, port, database, username, password, connection_string, query)

    # --- Redis (key-value) ---
    if engine == "redis":
        return _query_redis(action, host, port, password, connection_string, query)

    # --- SQL engines ---
    conn = None
    cursor = None
    try:
        if engine == "sqlite":
            conn, cursor = _connect_sqlite(connection_string or database or ":memory:")
        elif engine in ("postgres", "postgresql", "pg"):
            conn, cursor = _connect_postgres(connection_string, host, port, database, username, password)
        elif engine in ("mysql", "mariadb"):
            conn, cursor = _connect_mysql(connection_string, host, port, database, username, password)
        elif engine in ("mssql", "sqlserver"):
            conn, cursor = _connect_mssql(connection_string, host, port, database, username, password)
        else:
            return (
                f"Error: Unknown engine '{engine}'. Supported engines:\n"
                "  SQL: sqlite, postgres, mysql, mariadb, mssql\n"
                "  NoSQL: mongodb, redis"
            )

        # --- Execute action ---
        if action == "query":
            if not query:
                return "Error: 'query' parameter required"

            cursor.execute(query)

            # Check if query returns rows
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return _format_rows(columns, rows, len(rows))
            else:
                conn.commit()
                affected = cursor.rowcount if cursor.rowcount >= 0 else 0
                return f"Query OK. {affected} row(s) affected."

        elif action == "list-tables":
            if engine == "sqlite":
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            elif engine in ("postgres", "postgresql", "pg"):
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            elif engine in ("mysql", "mariadb"):
                cursor.execute("SHOW TABLES")
            elif engine in ("mssql", "sqlserver"):
                cursor.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
                )

            rows = cursor.fetchall()
            if not rows:
                return "No tables found."
            tables = [row[0] for row in rows]
            return "Tables:\n" + "\n".join(f"  - {t}" for t in tables)

        elif action == "describe":
            if not query:
                return "Error: 'query' parameter should contain the table name to describe"
            table_name = query.strip()

            if engine == "sqlite":
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                rows = cursor.fetchall()
                if not rows:
                    return f"Table '{table_name}' not found."
                lines = [f"Table: {table_name}", ""]
                for row in rows:
                    # cid, name, type, notnull, dflt_value, pk
                    nullable = "NOT NULL" if row[3] else "NULL"
                    pk = " PRIMARY KEY" if row[5] else ""
                    default = f" DEFAULT {row[4]}" if row[4] is not None else ""
                    lines.append(f"  {row[1]:30s} {row[2]:15s} {nullable}{pk}{default}")
                return "\n".join(lines)

            elif engine in ("postgres", "postgresql", "pg"):
                cursor.execute(
                    "SELECT column_name, data_type, is_nullable, column_default "
                    "FROM information_schema.columns WHERE table_name = %s "
                    "ORDER BY ordinal_position", (table_name,)
                )
            elif engine in ("mysql", "mariadb"):
                cursor.execute(f"DESCRIBE `{table_name}`")
            elif engine in ("mssql", "sqlserver"):
                cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                    "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? "
                    "ORDER BY ORDINAL_POSITION", (table_name,)
                )

            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return f"Table: {table_name}\n\n" + _format_rows(columns, rows, len(rows))
            return f"Table '{table_name}' not found."

        elif action == "info":
            if engine == "sqlite":
                cursor.execute("SELECT sqlite_version()")
                version = cursor.fetchone()[0]
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                db_path = connection_string or database or ":memory:"
                return json.dumps({
                    "engine": "SQLite",
                    "version": version,
                    "database": db_path,
                    "tables": len(tables),
                }, indent=2)

            elif engine in ("postgres", "postgresql", "pg"):
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                cursor.execute("SELECT current_database()")
                db_name = cursor.fetchone()[0]
                return json.dumps({
                    "engine": "PostgreSQL",
                    "version": version.split(",")[0],
                    "database": db_name,
                    "host": host or "localhost",
                    "port": port or 5432,
                }, indent=2)

            elif engine in ("mysql", "mariadb"):
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                cursor.execute("SELECT DATABASE()")
                db_name = cursor.fetchone()[0]
                return json.dumps({
                    "engine": "MySQL" if engine == "mysql" else "MariaDB",
                    "version": version,
                    "database": db_name,
                    "host": host or "localhost",
                    "port": port or 3306,
                }, indent=2)

            elif engine in ("mssql", "sqlserver"):
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                return json.dumps({
                    "engine": "Microsoft SQL Server",
                    "version": version.split("\n")[0],
                    "host": host or "localhost",
                    "port": port or 1433,
                }, indent=2)

        else:
            return (
                "Error: Unknown action. Available actions:\n"
                "  query        — Execute SQL/NoSQL query\n"
                "  list-tables  — List all tables or collections\n"
                "  describe     — Describe table schema (pass table name in 'query')\n"
                "  info         — Get database server info"
            )

    except ImportError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
