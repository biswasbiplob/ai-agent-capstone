import sqlite3
import json

conn = sqlite3.connect("students.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- EXAMS ---")
cursor.execute("SELECT * FROM exams")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- ANALYSIS ---")
print("\n--- Exams Table (Last 5) ---")
cursor.execute("SELECT * FROM exams ORDER BY rowid DESC LIMIT 5")
exams = cursor.fetchall()
for exam in exams:
    print(dict(exam))

conn.close()
