import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo.errors import DuplicateKeyError

from app.auth import hash_password
from app.database import connect_to_mongo, close_mongo_connection, get_db


def main():
    email = input("Admin email: ").strip().lower()
    if "@" not in email or len(email) > 254:
        raise SystemExit("Please enter a valid email address.")

    password = getpass.getpass("New admin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm admin password: ")

    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    try:
        connect_to_mongo()
        users = get_db()["users"]
        users.create_index("email", unique=True, name="uq_users_email")

        if users.find_one({"email": email}):
            raise SystemExit("This email already exists. No account was changed.")

        try:
            users.insert_one({
                "email": email,
                "password_hash": hash_password(password),
                "role": "admin",
                "is_active": True,
            })
        except DuplicateKeyError:
            raise SystemExit("This email already exists. No account was changed.")

        print("Admin account created successfully.")
    finally:
        close_mongo_connection()


if __name__ == "__main__":
    main()
