import streamlit as st
import sqlite3
import pandas as pd

# Database connection
def get_db_connection():
    return sqlite3.connect('mydb.db')

# Fetch recruiter details
def load_recruiter_data():
    conn = get_db_connection()
    query = "SELECT * FROM Recruiter"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Update recruiter details
def update_recruiter_details(Recruiter_id, Name, Email, Phone_Number, Location, Designation):
    conn = get_db_connection()
    query = """
        UPDATE Recruiter
        SET name = ?, email = ?, phone_number = ?, location = ?, Designation = ?
        WHERE recruiter_id = ?
    """
    conn.execute(query, (Name, Email, Phone_Number, Location, Designation, Recruiter_id))
    conn.commit()
    conn.close()

# Add a new recruiter
def add_new_recruiter(Name, Email, Phone_Number, Location, Designation):
    conn = get_db_connection()
    query = """
        INSERT INTO Recruiter (Name, Email, Phone_Number, Location, Designation)
        VALUES (?, ?, ?, ?, ?)
    """
    conn.execute(query, (Name, Email, Phone_Number, Location, Designation))
    conn.commit()
    conn.close()

# Remove a recruiter
def remove_recruiter(recruiter_id):
    conn = get_db_connection()
    query = "DELETE FROM Recruiter WHERE recruiter_id = ?"
    conn.execute(query, (recruiter_id,))
    conn.commit()
    conn.close()

# Recruiter Page
def recruiter_page():
    st.header("Recruiter Details")

    # Load data from the database
    recruiter_detail = load_recruiter_data()

    # Search functionality
    search_term = st.text_input("Search by Name:")
    filtered_df_search = recruiter_detail[
        recruiter_detail["Name"].str.contains(search_term, case=False, na=False)
    ]
    with st.expander("Recruiter Details", expanded=bool(search_term)):
        st.dataframe(filtered_df_search, hide_index=True, use_container_width=True)

    action = st.radio(
        "Choose an Action:",
        options=["Edit Recruiter Details", "Add New Recruiter", "Remove Recruiter"],
    )

    if action == "Edit Recruiter Details":
        st.subheader("Edit Recruiter Details")
        recruiter_ids = recruiter_detail["Recruiter_id"].tolist()
        recruiter_ids.insert(0, "Select a Recruiter ID")

        selected_recruiter_id = st.selectbox("Select Recruiter ID:", recruiter_ids)
        if selected_recruiter_id != "Select a Recruiter ID":
            current_row = recruiter_detail[
                recruiter_detail["Recruiter_id"] == selected_recruiter_id
            ].iloc[0]

            updated_name = st.text_input("Name:", value=current_row["Name"])
            updated_email = st.text_input("Email:", value=current_row["Email"])
            updated_phone_number = st.text_input("Phone Number:", value=current_row["Phone_Number"],max_chars=11)
            
            if len(updated_phone_number) == 10 and updated_phone_number.isdigit():
                updated_phone_number = f"{updated_phone_number[:3]}-{updated_phone_number[3:6]}-{updated_phone_number[6:]}"
            
            updated_location = st.text_input("Location:", value=current_row["Location"])
            
            updated_designation = st.text_input("Designation:", value=current_row["Designation"])

            if st.button("Save Changes"):
                update_recruiter_details(
                    selected_recruiter_id,
                    updated_name,
                    updated_email,
                    updated_phone_number,
                    updated_location,
                    updated_designation,
                )
                st.success("Details updated successfully!")
                st.rerun()

    elif action == "Add New Recruiter":
        st.subheader("Add New Recruiter")

        with st.form("add_recruiter_form"):
            new_name = st.text_input("Name:")
            new_email = st.text_input("Email:")
            new_phone_number = st.text_input("Phone Number:",max_chars=10)
            # Validate phone number format
            if len(new_phone_number) == 10 and new_phone_number.isdigit():
                new_phone_number = f"{new_phone_number[:3]}-{new_phone_number[3:6]}-{new_phone_number[6:]}"
            
            new_location = st.text_input("Location:")
            new_designation = st.text_input("Designation:")

            submitted = st.form_submit_button("Submit")
            if submitted:
                add_new_recruiter(new_name, new_email, new_phone_number, new_location, new_designation)
                st.success("New recruiter added successfully!")
                st.rerun()

    elif action == "Remove Recruiter":
        st.subheader("Remove Recruiter")
        recruiter_ids = recruiter_detail["Recruiter_id"].tolist()
        recruiter_ids.insert(0, "Select a Recruiter ID")

        selected_recruiter_id = st.selectbox("Select Recruiter ID to Remove:", recruiter_ids)
        if selected_recruiter_id != "Select a Recruiter ID":
            if st.button("Remove Recruiter"):
                remove_recruiter(selected_recruiter_id)
                st.success("Recruiter removed successfully!")
                st.rerun()

# Main function
def main():
    if "updated" not in st.session_state:
        st.session_state.updated = False

    recruiter_page()

if __name__ == "__main__":
    main()
