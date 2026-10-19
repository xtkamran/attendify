
from getpass import getpass
from urllib.parse import quote_plus

import certifi
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from app.auth import hash_password

user = "kamranlmps_db_user"
db_password = quote_plus(getpass("Atlas database password: "))

uri = (
    f"mongodb+srv://{user}:{db_password}"
    "@attendifycluster.svoatqt.mongodb.net/attendance"
    "?retryWrites=true&w=majority"
)

email = input("Admin email: ").strip().lower()
if "@" not in email or len(email) > 254:
    raise SystemExit("Please enter a valid email address.")

password = getpass("New admin password (minimum 12 characters): ")
confirmation = getpass("Confirm admin password: ")

if len(password) < 12:
    raise SystemExit("Password must contain at least 12 characters.")
if password != confirmation:
    raise SystemExit("Passwords do not match.")

client = None
try:
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=15000,
    )
    client.admin.command("ping")

    users = client["attendance"]["users"]
    users.create_index("email", unique=True, name="uq_users_email")

    if users.find_one({"email": email}):
        raise SystemExit("This email already exists. No account was changed.")

    users.insert_one({
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "is_active": True,
    })
    print("SUCCESS: Admin account created.")
except DuplicateKeyError:
    print("This email already exists. No account was changed.")
finally:
    if client:
        client.close()
