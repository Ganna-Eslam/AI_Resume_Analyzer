from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import sqlite3
import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import UploadFile, File
import io
import PyPDF2
import docx
import json
import os
from groq import Groq
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np


app = FastAPI(title="AI Resume Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


SECRET_KEY = "your_super_secret_key_here" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 



embedding_model = SentenceTransformer('all-MiniLM-L6-v2')



class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: str
    experience_level: str

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[str] = None
    experience_level: Optional[str] = None



def get_db_connection():
    conn = sqlite3.connect('resume_analyzer.db')
    conn.row_factory = sqlite3.Row 
    return conn

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def extract_text_from_pdf(file_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    text = "\n".join([para.text for para in doc.paragraphs])
    return text


GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

def analyze_resume_with_llama(text: str):
    prompt = f"""
    You are an expert AI Resume Analyzer. Analyze the following resume text and extract the key information.
    Return ONLY a valid JSON object with the exact following keys:
    - "ai_summary": A short professional summary of the candidate.
    - "technical_skills": A comma-separated list of technical skills found.
    - "soft_skills": A comma-separated list of soft skills found.
    - "education_details": A brief text summarizing education.
    - "experience_details": A brief text summarizing work experience.

    Resume Text:
    {text}
    """
    
    response = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="qwen/qwen3.8-27b",
        response_format={"type": "json_object"},
        temperature=0.3 
    )
    
    return json.loads(response.choices[0].message.content)



@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    

    cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
   
    hashed_pwd = hash_password(user.password)
    cursor.execute(
        "INSERT INTO users (full_name, email, hashed_password) VALUES (?, ?, ?)",
        (user.full_name, user.email, hashed_pwd)
    )
    conn.commit()
    conn.close()
    
    return {"message": "User registered successfully"}

@app.post("/login")
def login_user(user: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    
  
    cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    db_user = cursor.fetchone()
    conn.close()
    
    
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
  
    access_token = create_access_token(data={"sub": db_user["email"], "role": db_user["role"]})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "id": db_user["id"],
            "full_name": db_user["full_name"],
            "email": db_user["email"],
            "role": db_user["role"]
        }
    }

    
@app.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_job(job: JobCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO jobs (title, description, required_skills, experience_level) VALUES (?, ?, ?, ?)",
        (job.title, job.description, job.required_skills, job.experience_level)
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return {"message": "Job added successfully", "job_id": job_id}



@app.get("/jobs")
def get_jobs(search: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if search:
      
        search_query = f"%{search}%"
        cursor.execute("SELECT * FROM jobs WHERE title LIKE ? OR required_skills LIKE ?", (search_query, search_query))
    else:
        cursor.execute("SELECT * FROM jobs")
        
    jobs = cursor.fetchall()
    conn.close()
    return [dict(job) for job in jobs]


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(job)


@app.put("/jobs/{job_id}")
def update_job(job_id: int, job_data: JobUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    

    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    existing_job = cursor.fetchone()
    
    if not existing_job:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")
        
    
    new_title = job_data.title if job_data.title else existing_job["title"]
    new_desc = job_data.description if job_data.description else existing_job["description"]
    new_skills = job_data.required_skills if job_data.required_skills else existing_job["required_skills"]
    new_level = job_data.experience_level if job_data.experience_level else existing_job["experience_level"]
    
    cursor.execute(
        "UPDATE jobs SET title=?, description=?, required_skills=?, experience_level=? WHERE id=?",
        (new_title, new_desc, new_skills, new_level, job_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Job updated successfully"}


@app.post("/upload-resume")
async def upload_resume(user_id: int, file: UploadFile = File(...)):
    
    file_bytes = await file.read()
    
  
    extracted_text = ""
    if file.filename.endswith('.pdf'):
        extracted_text = extract_text_from_pdf(file_bytes)
    elif file.filename.endswith('.docx'):
        extracted_text = extract_text_from_docx(file_bytes)
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
    
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resumes (user_id, file_path, extracted_text) VALUES (?, ?, ?)",
        (user_id, file.filename, extracted_text)
    )
    resume_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "message": "Resume uploaded and text extracted successfully",
        "resume_id": resume_id,
        "extracted_text_preview": extracted_text[:200] + "..." 
    }

@app.post("/analyze-resume/{resume_id}")
def analyze_resume(resume_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    

    cursor.execute("SELECT extracted_text FROM resumes WHERE id = ?", (resume_id,))
    resume = cursor.fetchone()
    
    if not resume or not resume["extracted_text"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume not found or text not extracted")
    
    text = resume["extracted_text"]
    
  
    try:
        analysis_result = analyze_resume_with_llama(text)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")
        
  
    cursor.execute("""
        UPDATE resumes 
        SET ai_summary = ?, technical_skills = ?, soft_skills = ?, education_details = ?, experience_details = ?
        WHERE id = ?
    """, (
        analysis_result.get("ai_summary", ""),
        analysis_result.get("technical_skills", ""),
        analysis_result.get("soft_skills", ""),
        analysis_result.get("education_details", ""),
        analysis_result.get("experience_details", ""),
        resume_id
    ))
    
    conn.commit()
    conn.close()
    
    return {
        "message": "Resume analyzed successfully",
        "analysis_results": analysis_result
    }

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"message": "Job deleted successfully"}

@app.get("/match-jobs/{resume_id}")
def match_jobs_with_rag(resume_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
   
    cursor.execute("SELECT ai_summary, technical_skills, soft_skills FROM resumes WHERE id = ?", (resume_id,))
    resume = cursor.fetchone()
    if not resume or not resume["ai_summary"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume not found or not analyzed yet")
        
    
    candidate_profile = f"Summary: {resume['ai_summary']} | Tech Skills: {resume['technical_skills']} | Soft Skills: {resume['soft_skills']}"
    
    
    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()
    conn.close()
    
    if not jobs:
        return {"message": "No jobs available in the system yet."}
        
    job_texts = [f"Title: {job['title']} | Desc: {job['description']} | Skills: {job['required_skills']}" for job in jobs]
    
    job_embeddings = embedding_model.encode(job_texts)
    dimension = job_embeddings.shape[1]
    
    index = faiss.IndexFlatL2(dimension)
    index.add(job_embeddings)
    
   
    candidate_embedding = embedding_model.encode([candidate_profile])
    k = min(3, len(jobs))
    distances, indices = index.search(candidate_embedding, k)
   
    top_jobs = [dict(jobs[i]) for i in indices[0]]
    jobs_context = json.dumps(top_jobs, ensure_ascii=False)
    
    
    prompt = f"""
    You are an expert Career Advisor Agent. Compare the candidate's profile with the retrieved jobs.
    For each job, calculate a matching score (0-100%) and explain in one sentence WHY it's a good fit.
    
    Candidate Profile: {candidate_profile}
    Retrieved Jobs: {jobs_context}
    
    Return ONLY a JSON object with a single key "matches" containing a list of objects.
    Each object must have: "job_id", "job_title", "matching_score", and "explanation".
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="qwen/qwen3.8-27b",
            response_format={"type": "json_object"},
            temperature=0.2 
        )
        ai_insights = json.loads(response.choices[0].message.content)
    except Exception as e:
        ai_insights = {"error": f"AI generation failed: {str(e)}"}

    return {
        "candidate_profile_preview": candidate_profile[:100] + "...",
        "ai_recommendations": ai_insights
    }


@app.get("/career-advice/{resume_id}")
def get_career_advice(resume_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
   
    cursor.execute("SELECT ai_summary, technical_skills, soft_skills FROM resumes WHERE id = ?", (resume_id,))
    resume = cursor.fetchone()
    conn.close()
    
    if not resume or not resume["ai_summary"]:
        raise HTTPException(status_code=404, detail="Resume not found or not analyzed yet")
        
    candidate_profile = f"Summary: {resume['ai_summary']} | Tech Skills: {resume['technical_skills']} | Soft Skills: {resume['soft_skills']}"
    
    
    prompt = f"""
    You are an expert Career Advisor Agent. Review this candidate's profile and provide professional advice to improve their career prospects.
    Candidate Profile: {candidate_profile}
    
    Return ONLY a valid JSON object with the exact following keys:
    - "weaknesses": A brief text about areas of improvement or gaps in the profile.
    - "missing_skills": A list of in-demand skills they should learn based on their current profile.
    - "recommended_certifications": A list of relevant professional certificates they should aim for.
    - "learning_resources": A list of recommended platforms or specific courses to improve their skills.
    """
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="qwen/qwen3.8-27b",
            response_format={"type": "json_object"},
            temperature=0.4 
        )
        career_advice = json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Career Advisor failed: {str(e)}")

    return {
        "message": "Career advice generated successfully",
        "advice": career_advice
    }
