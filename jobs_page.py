import streamlit as st
import sqlite3
import pandas as pd

# Database connection
def get_db_connection():
    return sqlite3.connect('mydb.db')


# Fetch job details
def load_job_data():
    conn = get_db_connection()
    query = "SELECT * FROM Jobs"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# Update job details


def update_job_details(Job_ID, Job_Details, Job_Location, Bill_Rate, Visas, Description, Client):
    conn = get_db_connection()
    query = """
        UPDATE Jobs
        SET Job_Details = ?, Job_Location = ?, Bill_Rate = ?, Visas = ?, Description = ?, Client = ?
        WHERE Job_ID = ?
    """
    conn.execute(query, (Job_Details, Job_Location, Bill_Rate, Visas, Description, Client, Job_ID))
    conn.commit()
    conn.close()


# Add a new job
def add_new_job( Job_Details, Job_Location, Bill_Rate, Visas, Description, Client):
    conn = get_db_connection()
    query = """
        INSERT INTO Jobs (Job_Details, Job_Location, Bill_Rate, Visas, Description, Client)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    conn.execute(query, ( Job_Details, Job_Location, Bill_Rate, Visas, Description, Client))
    conn.commit()
    conn.close()


# Remove a job
def remove_job(job_id):
    conn = get_db_connection()
    query = "DELETE FROM Jobs WHERE Job_ID = ?"
    conn.execute(query, (job_id,))
    conn.commit()
    conn.close()


# Jobs Page
def jobs_page():
    st.header("Job Details")

    # Load data from the database
    job_data = load_job_data()

    # Search functionality
    search_term = st.text_input("Search by Job Description:")
    filtered_df_search = job_data[
        job_data["Description"].str.contains(search_term, case=False, na=False)
    ]
    with st.expander("Job Requirements", expanded=bool(search_term)):
        st.dataframe(filtered_df_search, hide_index=True, use_container_width=True)

    action = st.radio(
        "Choose an Action:",
        options=["Edit Job Details", "Add New Job", "Remove Job"],
    )

    if action == "Edit Job Details":
        st.subheader("Edit Job Details")
        job_ids = job_data["Job_ID"].tolist()
        job_ids.insert(0, "Select a Job ID")

        selected_job_id = st.selectbox("Select Job ID:", job_ids)
        if selected_job_id != "Select a Job ID":
            current_row = job_data[
                job_data["Job_ID"] == selected_job_id
            ].iloc[0]

            updated_jd_details = st.text_input("Job Details:", value=current_row["Job_Details"])
            updated_job_location = st.text_input("Job Location:", value=current_row["Job_Location"])
            updated_bill_rate = st.text_input("Bill Rate:", value=current_row["Bill_Rate"])
            updated_visas = st.text_input("Visas:", value=current_row["Visas"])
            updated_description = st.text_input("Description:", value=current_row["Description"])
            updated_client = st.text_input("Client:", value=current_row["Client"])

            if st.button("Save Changes",key="edit_job_details"):
                update_job_details(
                    selected_job_id,
                    updated_jd_details,
                    updated_job_location,
                    updated_bill_rate,
                    updated_visas,
                    updated_description,
                    updated_client,
                )
                st.success("Details updated successfully!")
                st.rerun()

    elif action == "Add New Job":
        st.subheader("Add New Job")
        with st.form("add_job_form"):
            new_jd_details = st.text_input("Job Details:")
            new_job_location = st.text_input("Job Location:")
            new_bill_rate = st.text_input("Bill Rate:")
            new_visas = st.text_input("Visas:")
            new_description = st.text_input("Description:")
            new_client = st.text_input("Client:")

            submitted = st.form_submit_button("Submit")
            if submitted:
                add_new_job(new_jd_details, new_job_location, new_bill_rate, new_visas, new_description, new_client)
                st.success("New job added successfully!")
                st.rerun()

    elif action == "Remove Job":
        st.subheader("Remove Job")
        job_ids = job_data["Job_ID"].tolist()
        job_ids.insert(0, "Select a Job ID")

        selected_job_id = st.selectbox("Select Job ID to Remove:", job_ids)
        if selected_job_id != "Select a Job ID":
            if st.button("Remove Job", key="remove_job"):
                remove_job(selected_job_id)
                st.success("Job removed successfully!")
                st.rerun()


# Main function
def main():
    if "updated" not in st.session_state:
        st.session_state.updated = False

    jobs_page()


if __name__ == "__main__":
    main()
