import sqlite3
import pandas as pd

# Function to fetch data from SQLite
def fetch_data_from_db(query, db_path='mydb.db'):
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)

# Updated load_data function
def load_data():
    # Fetch data from SQLite instead of CSV
    recruiter_detail = fetch_data_from_db("SELECT * FROM Recruiter")
    job_requirements = fetch_data_from_db("SELECT * FROM Jobs")
    submission_table = fetch_data_from_db("SELECT * FROM Submissions")

    return recruiter_detail, job_requirements, submission_table
