import streamlit as st
import sqlite3
import pandas as pd
import fitz  # PyMuPDF for PDF text extraction
import docx
import io

def extract_text_from_pdf(pdf_bytes):
    """Extract text from a PDF file."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join([page.get_text() for page in doc])
    return text if text.strip() else "No extractable text found in the PDF."

def extract_text_from_docx(docx_bytes):
    """Extract text from a DOCX file."""
    doc = docx.Document(io.BytesIO(docx_bytes))
    text = "\n".join([para.text for para in doc.paragraphs])
    return text if text.strip() else "No extractable text found in the DOCX file."

def get_all_resumes():
    """Fetch all resume records from the database."""
    conn = sqlite3.connect("mydb.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            NAME, EMAIL, PHONE_NUMBER, JOB_TITLE, CURRENT_JOB, SKILLS, 
            LOCATION, RESUME_FILE, FILE_NAME
        FROM RESUMES
    """)
    rows = cursor.fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=[
        'Name', 'Email ID', 'Phone Number', 'Job Title', 'Current Company',
        'Skills', 'Location', 'Resume_File', 'File_Name'
    ])
    return df

def search_fun():
    df = get_all_resumes()
    if df.empty:
        st.info("No resumes found in the database.")
        return

    st.title("Resume Viewer & Downloader")
    search_option = st.radio("Search resumes by:", ("Skills", "Emails"), horizontal=True)

    if search_option == "Skills":
        search_input = st.text_input("Enter Skills (comma-separated):", placeholder="e.g., Python, Machine Learning")
        if search_input:
            search_list = [s.strip().lower() for s in search_input.split(",") if s.strip()]
            df_filtered = df[df["Skills"].apply(lambda x: all(skill in x.lower() for skill in search_list))]
        else:
            df_filtered = df
    else:  # Emails search
        search_input = st.text_input("Enter Emails (space-separated):", placeholder="e.g., example@example.com another@example.com")
        if search_input:
            search_list = [s.strip().lower() for s in search_input.split() if s.strip()]
            df_filtered = df[df["Email ID"].str.lower().isin(search_list)]
        else:
            df_filtered = df

    st.write(f"Total Resumes Found: {len(df_filtered)}")

    for index, row in df_filtered.iterrows():
        with st.expander(f"📄 {row['Name']} - {row['Job Title']}"):
            st.write(f"**Email:** {row['Email ID']}")
            st.write(f"**Phone:** {row['Phone Number']}")
            st.write(f"**Current Job:** {row['Current Company']}")
            st.write(f"**Skills:** {row['Skills']}")
            st.write(f"**Location:** {row['Location']}")

            file_name = row["File_Name"]
            resume_bytes = row["Resume_File"]
            
            mime_type = (
                "application/pdf" if file_name.lower().endswith('.pdf')
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if file_name.lower().endswith('.docx')
                else "application/octet-stream"
            )

            # Add View and Download Buttons
            col1, col2 = st.columns([0.2, 0.2])
            if col1.button("👁 View", key=f"view_{index}"):
                with st.spinner("Extracting text..."):
                    if file_name.lower().endswith(".pdf"):
                        extracted_text = extract_text_from_pdf(resume_bytes)
                    elif file_name.lower().endswith(".docx"):
                        extracted_text = extract_text_from_docx(resume_bytes)
                    else:
                        extracted_text = "Unsupported file format."

                    st.text_area("Extracted Resume Text", extracted_text, height=300)
            
            col2.download_button(
                label="⬇️ Download", 
                data=resume_bytes, 
                file_name=file_name, 
                mime=mime_type,
                key=f"download_{index}"
            )

if __name__ == "__main__":
    search_fun()
