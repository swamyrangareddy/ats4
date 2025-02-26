import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import re
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Configuration
DATABASE_PATH = "mydb.db"
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
BATCH_SIZE = 32

class ATSAnalyzer:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.embedding_cache = {}

    def batch_embed(self, texts):
        """Batch process embeddings with caching"""
        uncached = [text for text in texts if text not in self.embedding_cache]
        if uncached:
            batch_embeddings = self.model.encode(
                uncached, 
                batch_size=BATCH_SIZE,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            for text, embedding in zip(uncached, batch_embeddings):
                self.embedding_cache[text] = embedding
        return np.array([self.embedding_cache[text] for text in texts])

@st.cache_data
def fetch_resumes_from_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        query = """
        SELECT 
            Resume_ID, 
            NAME, 
            EMAIL, 
            PHONE_NUMBER, 
            JOB_TITLE, 
            CURRENT_JOB, 
            SKILLS, 
            LOCATION, 
            RESUME_SUMMARY
        FROM RESUMES
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except sqlite3.Error as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

@st.cache_data
def fetch_job_descriptions():
    """
    Fetch job descriptions from the JOBS table.
    The table is expected to have columns: Job_Details and Description.
    Returns a dictionary mapping Job_Details -> Description.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        query = "SELECT Job_Details, Description FROM JOBS"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if 'Job_Details' in df.columns and 'Description' in df.columns:
            return dict(zip(df['Job_Details'], df['Description']))
        else:
            return {}
    except Exception as e:
        st.error(f"Error fetching job descriptions: {e}")
        return {}

def calculate_scores(analyzer, job_embedding, resume_summaries, required_skills, resume_skills_list):
    """
    Calculate match scores based on both semantic similarity and required skills.
    Semantic similarity is computed between the job description and each resume summary.
    Skill match score is calculated by checking the presence of required skills in each resume.
    The final score is a weighted combination of these two measures.
    """
    resume_embeddings = analyzer.batch_embed(resume_summaries)
    semantic_similarities = cosine_similarity([job_embedding], resume_embeddings)[0]
    skill_match_scores = []
    for resume_skills in resume_skills_list:
        matched_skills = [kw for kw in required_skills if kw.lower() in resume_skills.lower()]
        match_percentage = len(matched_skills) / len(required_skills) if required_skills else 0
        skill_match_scores.append(match_percentage)
    
    combined_scores = (0.6 * semantic_similarities) + (0.4 * np.array(skill_match_scores))
    return (combined_scores * 100).clip(0, 100)

def resume_matching_system():
    st.title("📄 ATS Resume Analyzer")
    
    # Fetch job descriptions from the JOBS table.
    job_descriptions = fetch_job_descriptions()
    
    job_options = ["Custom"] + list(job_descriptions.keys())
    selected_job = st.selectbox("Select a job description:", job_options)
    if selected_job == "Custom":
        default_description = ""
        #st.warning("Please enter a custom job description.")
    else:
        default_description = job_descriptions.get(selected_job, "")
    
    job_description = st.text_area("Enter Job Description:", 
                                    value=default_description, 
                                    height=200, 
                                    placeholder="Paste complete job description...")
        
    match_threshold = st.number_input("Minimum Match Threshold (%):", min_value=0, max_value=100, value=70)
    
    if st.button("Analyze Resumes"):
        if not job_description.strip():
            st.warning("⚠️ Please enter a job description.")
            return

        with st.spinner("Fetching resumes from database..."):
            df_db = fetch_resumes_from_db()
        if df_db.empty:
            st.info("No resumes found in the database.")
            return

        total_resumes = len(df_db)
        
        analyzer = ATSAnalyzer()
        required_skills = list(set(re.findall(r'\b[A-Za-z-+]+\b', job_description)))
        if not required_skills:
            st.warning("No meaningful skills found in the job description.")
            return

        job_embedding = analyzer.batch_embed([job_description])[0]
        resume_summaries = df_db['RESUME_SUMMARY'].tolist()
        resume_skills_list = df_db['SKILLS'].tolist()
        
        with st.spinner("Analyzing resumes..."):
            scores = calculate_scores(analyzer, job_embedding, resume_summaries, required_skills, resume_skills_list)
        
        results = []
        for idx, (score, row) in enumerate(zip(scores, df_db.itertuples(index=False))):
            if score >= match_threshold:
                results.append({
                    "Resume_ID": row.Resume_ID,
                    "NAME": row.NAME,
                    "EMAIL": row.EMAIL,
                    "PHONE_NUMBER": row.PHONE_NUMBER,
                    "Match %": round(score, 1),
                    "SKILLS": row.SKILLS
                })
        
        if results:
            results_df = pd.DataFrame(results).sort_values("Match %", ascending=False)
            st.success(f"Found {len(results)} resumes that meet the minimum match criteria out of {total_resumes} total resumes.")
            st.markdown("### Top Matching Candidates")
            st.dataframe(
                results_df,
                column_config={
                    "Match %": st.column_config.ProgressColumn(
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    )
                },
                use_container_width=True,
                hide_index=True
            )
            csv_filename = f"ats_resume_matches_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            st.download_button(
                label="📥 Export Results",
                data=results_df.to_csv(index=False),
                file_name=csv_filename,
                mime="text/csv"
            )
        else:
            st.info("No candidates met the minimum match criteria.")

if __name__ == "__main__":
    resume_matching_system()
