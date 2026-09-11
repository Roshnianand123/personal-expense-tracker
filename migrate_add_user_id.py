"""
Database migration script: adds the 'user_id' column to the 'transactions'
table if it does not already exist.

Run once before starting the app after the auth feature was introduced:
    python migrate_add_user_id.py
"""

import os
import sqlite3
import sys


def get_db_path():
    """Resolve the SQLite database path from DATABASE_URL or default."""
    db_url = os.environ.get("DATABASE_URL", "sqlite:///expense_tracker.db")

    # Only handle SQLite for this migration script
    if "postgresql" in db_url or "postgres:" in db_url:
        print("This script only handles SQLite databases.")
        print("For PostgreSQL, run the following SQL manually:")
        print("  ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id);")
        sys.exit(0)

    # Extract file path from sqlite:///path
    if db_url.startswith("sqlite:///"):
        relative = db_url[len("sqlite:///"):]
        return os.path.join("instance", relative)

    return os.path.join("instance", "expense_tracker.db")


def migrate():
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Nothing to migrate.")
        print("The app will create the schema automatically on first run.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check whether user_id column already exists
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_id" in columns:
        print("Column 'user_id' already exists in 'transactions'. No migration needed.")
        conn.close()
        return

    print(f"Migrating database at: {db_path}")
    print("Adding 'user_id' column to 'transactions' table...")

    cursor.execute(
        "ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)"
    )
    conn.commit()

    # Verify
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "user_id" in columns, "Migration failed – column not added."

    # Report orphan transactions (those without a user)
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id IS NULL")
    orphan_count = cursor.fetchone()[0]
    if orphan_count > 0:
        print(f"Note: {orphan_count} existing transaction(s) have no assigned user.")
        print("They will not appear on any user's dashboard until reassigned.")

    conn.close()
    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
