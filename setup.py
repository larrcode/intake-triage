"""
Run this once before the first launch: python setup.py
Creates the database and one admin account. There's no "create first
user" flow inside the app itself on purpose, a login screen shouldn't
also be the thing that creates accounts with no credentials checked.
"""

import getpass
import storage

def main():
    storage.init_db()
    print("Database initialized.")

    conn = storage.get_connection()
    existing = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    if existing > 0:
        print(f"Database already has {existing} user(s). Nothing to do.")
        conn.close()
        return

    print("No users yet. Let's create the first admin account.")
    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")
    storage.create_user(conn, username, password, role="admin")
    storage.log_action(conn, username, "account_created", "initial admin setup")
    conn.close()
    print(f"Admin user '{username}' created. Run: python main.py")


if __name__ == "__main__":
    main()
