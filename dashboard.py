import streamlit as st
import sqlite3
import pandas as pd

# Function to fetch data from SQLite
def fetch_data_from_db(query, db_path='mydb.db'):
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn)



# Dashboard Function
def dashboard():
    st.header('Summary Report')

    # Fetch data from SQLite
    recruiter_detail = fetch_data_from_db("SELECT * FROM Recruiter")
    job_requirements = fetch_data_from_db("SELECT * FROM Jobs")
    submission_table = fetch_data_from_db("SELECT * FROM Submissions")

    # Calculate totals
    total_recruiter = recruiter_detail.shape[0]
    total_jobs = job_requirements.shape[0]
    total_submission = submission_table.shape[0]

    # Display Metrics
    total1, total2, total3 = st.columns(3, gap='small')

    with total1:
        st.info('Total Recruiters', icon="👨‍💼")
        st.metric(label="Recruiters Count", value=f'{total_recruiter}', label_visibility="collapsed")
    with total2:
        st.info('Total Jobs', icon="📋")
        st.metric(label="Jobs Count", value=f'{total_jobs}', label_visibility="collapsed")
    with total3:
        st.info('Total Submissions', icon="📤")
        st.metric(label="Submissions Count", value=f'{total_submission}', label_visibility="collapsed")

# Run the dashboard
if __name__ == "__main__":
    dashboard()
