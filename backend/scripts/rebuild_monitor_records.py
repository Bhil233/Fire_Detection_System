from __future__ import annotations

import argparse
import os
from datetime import datetime
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import load_dotenv


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backup old monitor_records table and rebuild with new schema."
    )
    parser.add_argument(
        "--env-file",
        default=os.path.join(os.path.dirname(__file__), "..", ".env"),
        help="Path to .env file (default: backend/.env).",
    )
    parser.add_argument(
        "--table-name",
        default="monitor_records",
        help="Target table name (default: monitor_records).",
    )
    return parser.parse_args()


def _build_db_config() -> dict:
    mysql_url = (os.getenv("MYSQL_URL") or "").strip()
    if mysql_url:
        parsed = urlparse(mysql_url)
        if not parsed.scheme.startswith("mysql"):
            raise ValueError(f"Unsupported MYSQL_URL scheme: {parsed.scheme}")
        database = parsed.path.lstrip("/")
        if not database:
            raise ValueError("MYSQL_URL must include database name.")
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or "root"),
            "password": unquote(parsed.password or ""),
            "database": database,
            "charset": "utf8mb4",
            "autocommit": False,
        }

    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fire_detection"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "autocommit": False,
    }


def _table_exists(cursor: pymysql.cursors.Cursor, table_name: str) -> bool:
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _rebuild_table(cursor: pymysql.cursors.Cursor, table_name: str) -> str | None:
    backup_table = None
    if _table_exists(cursor, table_name):
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_table = f"{table_name}_backup_{suffix}"
        cursor.execute(f"RENAME TABLE `{table_name}` TO `{backup_table}`")

    create_sql = f"""
    CREATE TABLE `{table_name}` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `scene_image_path` VARCHAR(255) NOT NULL,
      `status` VARCHAR(32) NOT NULL,
      `remark` VARCHAR(255) NOT NULL DEFAULT '',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor.execute(create_sql)
    return backup_table


def main() -> None:
    args = _parse_args()
    load_dotenv(args.env_file)
    db_config = _build_db_config()

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            backup_table = _rebuild_table(cursor, args.table_name)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if backup_table:
        print(f"Rebuild done. Old table backed up as: {backup_table}")
    else:
        print("Rebuild done. No old table found; new table created directly.")


if __name__ == "__main__":
    main()
