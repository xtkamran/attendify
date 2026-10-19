import json
import os
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

user = "kamranlmps_db_user"
password = quote_plus(getpass("Atlas database password: "))
uri = (
    f"mongodb+srv://{user}:{password}"
    "@attendifycluster.svoatqt.mongodb.net/attendance"
)

file_path = Path("sample_data/employees.json")
employees = json.loads(file_path.read_text())

client = MongoClient(uri, serverSelectionTimeoutMS=15000)

try:
    client.admin.command("ping")
    db = client["attendance"]
    collection = db["employees"]

    collection.create_index("employee_id", unique=True)

    inserted = 0
    skipped = 0

    for employee in employees:
        employee_id = employee["employee_id"]
        employee["emp_code"] = employee_id

        if collection.find_one({"employee_id": employee_id}):
            print(f"Skipped existing employee: {employee_id}")
            skipped += 1
            continue

        employee["created_at"] = datetime.now(timezone.utc)

        try:
            collection.insert_one(employee)
            print(f"Inserted: {employee_id} - {employee['name']}")
            inserted += 1
        except DuplicateKeyError as e:
            print(f"\nDuplicate error for {employee_id}:")
            print(e.details)
            print("Error message:", str(e))
            raise

    print(f"\nImport complete. Inserted: {inserted}, Skipped: {skipped}")
    print("Total employees in Atlas:", collection.count_documents({}))

finally:
    client.close()
