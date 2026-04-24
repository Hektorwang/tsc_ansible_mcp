#!/usr/bin/env python3
"""
Database migration script for model changes.

This script handles the following migrations:
1. Rename created_at/updated_at to create_time/update_time in all tables
2. Add ansible_old_port column to hosts table

Usage:
    python bin/migrate.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from sqlalchemy import create_engine, text, inspect


def get_db_path():
    return Path("logs/tsc_ansible_mcp.db")


def migrate():
    db_path = get_db_path()
    db_url = f"sqlite:///{db_path}"

    print(f"Connecting to database: {db_path}")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)

    with engine.connect() as conn:
        # Check current schema
        print("\n=== Current Schema ===")

        # Check hosts table
        hosts_columns = [col["name"] for col in inspector.get_columns("hosts")]
        print(f"hosts table columns: {hosts_columns}")

        # Check tasks table
        tasks_columns = [col["name"] for col in inspector.get_columns("tasks")]
        print(f"tasks table columns: {tasks_columns}")

        # Check contexts table
        contexts_columns = [col["name"] for col in inspector.get_columns("contexts")]
        print(f"contexts table columns: {contexts_columns}")

        print("\n=== Running Migrations ===")

        # Migration 1: Add ansible_old_port to hosts if not exists
        if "ansible_old_port" not in hosts_columns:
            print("Adding ansible_old_port column to hosts table...")
            conn.execute(text("ALTER TABLE hosts ADD COLUMN ansible_old_port INTEGER"))
            conn.commit()
            print("  Done.")
        else:
            print("ansible_old_port column already exists in hosts table.")

        # Migration 2: Rename created_at -> create_time in hosts
        if "created_at" in hosts_columns and "create_time" not in hosts_columns:
            print("Renaming created_at -> create_time in hosts table...")
            conn.execute(
                text("ALTER TABLE hosts RENAME COLUMN created_at TO create_time")
            )
            conn.commit()
            print("  Done.")
        elif "create_time" in hosts_columns:
            print("create_time column already exists in hosts table.")
        else:
            print("created_at column not found in hosts table, skipping.")

        # Migration 3: Rename updated_at -> update_time in hosts
        if "updated_at" in hosts_columns and "update_time" not in hosts_columns:
            print("Renaming updated_at -> update_time in hosts table...")
            conn.execute(
                text("ALTER TABLE hosts RENAME COLUMN updated_at TO update_time")
            )
            conn.commit()
            print("  Done.")
        elif "update_time" in hosts_columns:
            print("update_time column already exists in hosts table.")
        else:
            print("updated_at column not found in hosts table, skipping.")

        # Migration 4: Rename created_at -> create_time in tasks
        if "created_at" in tasks_columns and "create_time" not in tasks_columns:
            print("Renaming created_at -> create_time in tasks table...")
            conn.execute(
                text("ALTER TABLE tasks RENAME COLUMN created_at TO create_time")
            )
            conn.commit()
            print("  Done.")
        elif "create_time" in tasks_columns:
            print("create_time column already exists in tasks table.")
        else:
            print("created_at column not found in tasks table, skipping.")

        # Migration 5: Rename updated_at -> update_time in tasks
        if "updated_at" in tasks_columns and "update_time" not in tasks_columns:
            print("Renaming updated_at -> update_time in tasks table...")
            conn.execute(
                text("ALTER TABLE tasks RENAME COLUMN updated_at TO update_time")
            )
            conn.commit()
            print("  Done.")
        elif "update_time" in tasks_columns:
            print("update_time column already exists in tasks table.")
        else:
            print("updated_at column not found in tasks table, skipping.")

        # Migration 6: Rename created_at -> create_time in contexts
        if "created_at" in contexts_columns and "create_time" not in contexts_columns:
            print("Renaming created_at -> create_time in contexts table...")
            conn.execute(
                text("ALTER TABLE contexts RENAME COLUMN created_at TO create_time")
            )
            conn.commit()
            print("  Done.")
        elif "create_time" in contexts_columns:
            print("create_time column already exists in contexts table.")
        else:
            print("created_at column not found in contexts table, skipping.")

        # Migration 7: Rename updated_at -> update_time in contexts
        if "updated_at" in contexts_columns and "update_time" not in contexts_columns:
            print("Renaming updated_at -> update_time in contexts table...")
            conn.execute(
                text("ALTER TABLE contexts RENAME COLUMN updated_at TO update_time")
            )
            conn.commit()
            print("  Done.")
        elif "update_time" in contexts_columns:
            print("update_time column already exists in contexts table.")
        else:
            print("updated_at column not found in contexts table, skipping.")

        print("\n=== Updated Schema ===")

        # Refresh inspector to get updated columns
        inspector = inspect(engine)
        hosts_columns = [col["name"] for col in inspector.get_columns("hosts")]
        print(f"hosts table columns: {hosts_columns}")

        tasks_columns = [col["name"] for col in inspector.get_columns("tasks")]
        print(f"tasks table columns: {tasks_columns}")

        contexts_columns = [col["name"] for col in inspector.get_columns("contexts")]
        print(f"contexts table columns: {contexts_columns}")

        print("\n=== Migration Complete ===")


if __name__ == "__main__":
    migrate()
