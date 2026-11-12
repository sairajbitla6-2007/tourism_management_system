import os
from getpass import getpass

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

email = input("Account email: ").strip().lower()
new_password = getpass("New demo password (8+ characters): ")

if len(new_password) < 8:
    raise SystemExit("Password must be at least 8 characters.")

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
)

cursor = connection.cursor()

try:
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE email = %s",
        (generate_password_hash(new_password), email),
    )

    if cursor.rowcount == 1:
        connection.commit()
        print("Password updated. The password was not displayed.")
    else:
        connection.rollback()
        print("No matching account was found in the configured database.")
finally:
    cursor.close()
    connection.close()