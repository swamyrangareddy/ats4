import os
# Suppress torch C++ stack traces and set its logging level to ERROR.
os.environ["TORCH_SHOW_CPP_STACKTRACES"] = "0"
import logging
logging.getLogger("torch").setLevel(logging.ERROR)

import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
import PyPDF2 as pdf
from dotenv import load_dotenv
import docx2txt
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Tuple, Dict, Any
import json

# ------------------------------------------------------------------------------
# Environment & Configuration
# ------------------------------------------------------------------------------
load_dotenv()

MAX_WORKERS = 2    # Adjust based on your API rate limits
BATCH_SIZE = 50    # Number of records to insert at once
DELAY_THRESHOLD = 15  # Number of resumes to process before a delay
DELAY_TIME = 10  # Increased delay time to prevent API exhaustion
MAX_TEXT_LENGTH = 8000  # Limit resume text length to prevent API errors
MAX_RETRIES = 3  # Maximum retry attempts for failed resumes

# ------------------------------------------------------------------------------
# 1. Database Initialization & Retrieval (SQLite with original schema)
# ------------------------------------------------------------------------------
def init_db():
    """
    Initialize (or upgrade) the SQLite database with table RESUMES.
    This table stores resume details plus the file as a blob and its filename.
    """
    conn = sqlite3.connect("mydb.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS RESUMES(
            Resume_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            NAME VARCHAR(50) NOT NULL,
            EMAIL VARCHAR(50) NOT NULL,
            PHONE_NUMBER VARCHAR(20) NOT NULL,
            JOB_TITLE VARCHAR(50) NOT NULL,
            CURRENT_JOB VARCHAR(50) NOT NULL,
            SKILLS TEXT NOT NULL,
            LOCATION VARCHAR(50) NOT NULL,
            RESUME_SUMMARY TEXT NOT NULL,
            RESUME_FILE BLOB,
            FILE_NAME VARCHAR(100)
        );
    ''')
    conn.commit()
    
    # Check if FILE_NAME column exists; if not, try to add it.
    cursor.execute("PRAGMA table_info(RESUMES)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'FILE_NAME' not in columns:
        try:
            cursor.execute("ALTER TABLE RESUMES ADD COLUMN FILE_NAME VARCHAR(100)")
            conn.commit()
        except sqlite3.OperationalError as e:
            # Ignore error if column already exists.
            if "duplicate column" in str(e).lower():
                pass
            else:
                st.error(f"Error updating database schema: {e}")
    return conn

def get_all_resumes():
    """
    Retrieve all resume records from the database and return a DataFrame.
    """
    conn = sqlite3.connect("mydb.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            NAME, EMAIL, PHONE_NUMBER, JOB_TITLE, CURRENT_JOB, 
            SKILLS, LOCATION, RESUME_SUMMARY, RESUME_FILE, FILE_NAME
        FROM RESUMES
    ''')
    rows = cursor.fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=[
        'Name', 'Email ID', 'Phone Number', 'Job Title', 'Current Company',
        'Skills', 'Location', 'Resume_Text', 'Resume_File', 'File_Name'
    ])
    return df

# ------------------------------------------------------------------------------
# 2. Resume Extraction Function
# ------------------------------------------------------------------------------
def extract_text(uploaded_file) -> str:
    """
    Extract text from an uploaded PDF or DOCX file.
    """
    file_data = uploaded_file.getvalue()
    file_obj = BytesIO(file_data)
    try:
        if uploaded_file.name.lower().endswith('.pdf'):
            reader = pdf.PdfReader(file_obj)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
            return text.strip()
        elif uploaded_file.name.lower().endswith('.docx'):
            text = docx2txt.process(file_obj)
            return text.strip()
        else:
            raise ValueError("Unsupported file format")
    except Exception as e:
        raise ValueError(f"Error processing {uploaded_file.name}: {str(e)}")

# ------------------------------------------------------------------------------
# 3. GeminiProcessor Class for Fast Extraction & Summary Generation
# ------------------------------------------------------------------------------
class GeminiProcessor:
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(
            'gemini-pro',
            generation_config={
                "temperature": 0.1,
                "top_p": 0.95,
                "max_output_tokens": 2048,
            }
        )
        self.retry_config = {
            'max_retries': 3,
            'delay': 2,
            'backoff': 2
        }

    def process_resume(self, text: str) -> Tuple[Dict[str, Any], str]:
        """
        Call Gemini to extract details and generate a summary.
        Returns a tuple: (details dict, summary as JSON string)
        """
        combined_prompt = f"""
Extract resume details and generate summary following these strict formats:

DETAILS EXTRACTION:
{{
    "Name": "Full name from resume header",
    "Phone": "Valid phone number or Null",
    "Email": "Valid email or Null",
    "JobTitle": "Current/most recent job title",
    "CurrentCompany": "Current/most recent employer",
    "Skills": "Comma-separated technical skills",
    "Location": "City/State or Null"
}}

SUMMARY GENERATION:
{{
    "ProfessionalSummary": "2-3 sentence career overview",
    "KeySkills": "Top 10 technical skills",
    "Experience": "Recent roles and companies",
    "Education": "Highest degree if available",
    "Achievements": "Notable accomplishments"
}}

RESUME TEXT:
{text}

Return ONLY valid JSON following this structure:
{{
    "details": {{...}},
    "summary": {{...}}
}}
"""
        for attempt in range(self.retry_config['max_retries'] + 1):
            try:
                response = self.model.generate_content(combined_prompt)
                #------------------------------Testing--------------------------------
                print("Gemini Response:", response)
                #-----------------------------------------------------------------------
                if response and response.text:
                    return self._parse_response(response.text)
            except Exception as e:
                if attempt == self.retry_config['max_retries']:
                    raise e
                time.sleep(self.retry_config['delay'] * (self.retry_config['backoff'] ** attempt))
        return {}, ""  # If all retries fail

    def _parse_response(self, response_text: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse Gemini's JSON response.
        """
        try:
            # Remove any markdown formatting if needed
            clean_text = response_text.strip("```json\n").strip("```")
            data = json.loads(clean_text)
            return data.get("details", {}), json.dumps(data.get("summary", {}))
        except json.JSONDecodeError:
            return {}, ""

# ------------------------------------------------------------------------------
# 4. Process Single Resume File (used in parallel)
# ------------------------------------------------------------------------------
def process_file(uploaded_file, processor: GeminiProcessor):
    """
    Process an individual file: extract text, call Gemini, and package data.
    Includes the file's binary data and filename for storage.
    Tries three times if a valid email is not found.
    """
    attempts = 0
    while attempts < 3:
        try:
            file_data = uploaded_file.getvalue()
            text = extract_text(uploaded_file)
            #------------------------------Testing--------------------------------
            print("Extracted Text:", text)
            #-----------------------------------------------------------------------
            details, summary = processor.process_resume(text)
            email = details.get("Email", "").strip()
            # Check if a valid email is found (not empty or default "Not Specified")
            if email and email.lower() not in ["not specified", ""]:
                return {
                    "name": details.get("Name", "Not Specified"),
                    "email": email,
                    "phone": details.get("Phone", "Not Specified"),
                    "job_title": details.get("JobTitle", "Not Specified"),
                    "current_company": details.get("CurrentCompany", "Not Specified"),
                    "skills": details.get("Skills", "Not Specified"),
                    "location": details.get("Location", "Not Specified"),
                    "summary": summary if summary else "Not Specified",
                    "resume_file": file_data,
                    "file_name": uploaded_file.name,
                    "error": None
                }
            else:
                attempts += 1
                if attempts < 3:
                    time.sleep(1)  # small delay before retrying
                    continue
                else:
                    # After three attempts, mark email as not found (but do not flag as error)
                    return {
                        "name": details.get("Name", "Not Specified"),
                        "email": "Email not found",
                        "phone": details.get("Phone", "Not Specified"),
                        "job_title": details.get("JobTitle", "Not Specified"),
                        "current_company": details.get("CurrentCompany", "Not Specified"),
                        "skills": details.get("Skills", "Not Specified"),
                        "location": details.get("Location", "Not Specified"),
                        "summary": summary if summary else "Not Specified",
                        "resume_file": file_data,
                        "file_name": uploaded_file.name,
                        "error": None
                    }
        except Exception as e:
            return {"error": str(e), "file_data": uploaded_file.getvalue(), "file_name": uploaded_file.name}

# ------------------------------------------------------------------------------
# 5. Batch Insert / Update into Database (Upsert by EMAIL)
# ------------------------------------------------------------------------------
def batch_insert(conn, data) -> int:
    """
    Insert new records or update existing records (by EMAIL) in the RESUMES table.
    Only records with a valid email (i.e. not "Email not found") are inserted.
    """
    try:
        cursor = conn.cursor()
        inserted_count = 0
        updated_count = 0
        for record in data:
            if not record.get("error"):
                email = record.get("email", "not_specified@example.com")
                # Check if the email already exists in the database.
                cursor.execute("SELECT Resume_ID FROM RESUMES WHERE EMAIL = ?", (email,))
                result = cursor.fetchone()
                if result:
                    # Update the existing record with new details.
                    cursor.execute('''
                        UPDATE RESUMES
                        SET NAME = ?,
                            PHONE_NUMBER = ?,
                            JOB_TITLE = ?,
                            CURRENT_JOB = ?,
                            SKILLS = ?,
                            LOCATION = ?,
                            RESUME_SUMMARY = ?,
                            RESUME_FILE = ?,
                            FILE_NAME = ?
                        WHERE EMAIL = ?
                    ''', (
                        record.get("name", "Not Specified") or "Not Specified",
                        record.get("phone", "Not Specified") or "Not Specified",
                        record.get("job_title", "Not Specified") or "Not Specified",
                        record.get("current_company", "Not Specified") or "Not Specified",
                        record.get("skills", "Not Specified") or "Not Specified",
                        record.get("location", "Not Specified") or "Not Specified",
                        record.get("summary", "Not Specified") or "Not Specified",
                        record.get("resume_file", None),
                        record.get("file_name", "Unknown"),
                        email
                    ))
                    updated_count += 1
                else:
                    cursor.execute('''
                        INSERT INTO RESUMES (
                            NAME, EMAIL, PHONE_NUMBER, JOB_TITLE, CURRENT_JOB, 
                            SKILLS, LOCATION, RESUME_SUMMARY, RESUME_FILE, FILE_NAME
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        record.get("name", "Not Specified") or "Not Specified",
                        email,
                        record.get("phone", "Not Specified") or "Not Specified",
                        record.get("job_title", "Not Specified") or "Not Specified",
                        record.get("current_company", "Not Specified") or "Not Specified",
                        record.get("skills", "Not Specified") or "Not Specified",
                        record.get("location", "Not Specified") or "Not Specified",
                        record.get("summary", "Not Specified") or "Not Specified",
                        record.get("resume_file", None),
                        record.get("file_name", "Unknown")
                    ))
                    inserted_count += 1
        conn.commit()
        st.success(f"Successfully inserted {inserted_count} records and updated {updated_count} records in the database.")
        return inserted_count + updated_count
    except sqlite3.Error as e:
        conn.rollback()
        st.error(f"Database Error: {str(e)}")
        raise

# ------------------------------------------------------------------------------
# Helper: Create an UploadedFile-like object from bytes (for retries)
# ------------------------------------------------------------------------------
def create_uploaded_file(file_data, file_name):
    file_obj = BytesIO(file_data)
    file_obj.name = file_name
    return file_obj

# ------------------------------------------------------------------------------
# 6. Main Streamlit App (Upload & Search)
# ------------------------------------------------------------------------------
def run_app():
    st.header("Smart ATS - Multiple Resumes Processing")
    

    uploaded_files = st.file_uploader(
        "Upload your resumes (PDF/DOCX)...", 
        type=["pdf", "docx"], 
        accept_multiple_files=True
    )
    start_btn = st.button("Start Bulk Processing")
    
    if start_btn:
        if not uploaded_files:
            st.info("Please upload at least one resume file.")
            return
        
        processor = GeminiProcessor()
        conn = init_db()
        total_files = len(uploaded_files)
        processed_data = []
        errors = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Process files in parallel with throttling after every 14 files.
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_file, file, processor): file for file in uploaded_files}
            for i, future in enumerate(as_completed(futures)):
                try:
                    result = future.result()
                    if result.get("error"):
                        errors.append(result)
                    else:
                        processed_data.append(result)
                except Exception as e:
                    errors.append({"error": str(e), "file_name": futures[future].name})
                
                progress_bar.progress((i + 1) / total_files)
                status_text.text(f"Processed {i+1}/{total_files}. Successful: {len(processed_data)}. Errors: {len(errors)}")
                
                # Throttle: After every 14 resumes, wait for 10 seconds before proceeding.
                if (i + 1) % 14 == 0 and (i + 1) < total_files:
                    time.sleep(5)
        
        # Retry failed resumes (only genuine errors, not missing email cases) up to 3 times.
        retry_attempts = 3
        for attempt in range(retry_attempts):
            if not errors:
                break
            # Use one spinner for the entire retry attempt.
            with st.spinner(f"Retrying failed resumes: Attempt {attempt+1} of {retry_attempts}"):
                new_errors = []
                for error_entry in errors:
                    file_data = error_entry.get("file_data")
                    file_name = error_entry.get("file_name")
                    uploaded_file_retry = create_uploaded_file(file_data, file_name)
                    result = process_file(uploaded_file_retry, processor)
                    if result.get("error"):
                        new_errors.append(result)
                    else:
                        processed_data.append(result)
                errors = new_errors
                status_text.text(
                    f"After retry attempt {attempt+1}: Successful: {len(processed_data)}. Remaining errors: {len(errors)}"
                )
            if errors:
                time.sleep(5)

        # Separate records with a valid email from those with missing email.
        valid_records = [r for r in processed_data if r.get("email") != "Email not found"]
        missing_email_count = len([r for r in processed_data if r.get("email") == "Email not found"])
        
        if valid_records:
            inserted_count = batch_insert(conn, valid_records)
        else:
            inserted_count = 0

        st.dataframe(processed_data["name","email","phone","job_title","current_company","skills","location"], height=300)
        # st.success(f"Successfully processed {inserted_count} records.")
        if missing_email_count:
            st.info(f"Remaining errors: {missing_email_count} resume(s) with email not found.")
        
        conn.close()
    
    

# ------------------------------------------------------------------------------
# 7. Run the App
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    run_app()
