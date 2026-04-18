import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import Database
from nlp_engine import NLPEngine
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="NPGC Smart Assistant Class of 2026")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_history = {}

@app.on_event("startup")
async def startup():
    global nlp
    await Database.get_pool()
    
    # 1. Load Courses with RICH CONTEXT (JOINs)
    courses_raw = await Database.fetch_all("""
        SELECT c.course, c.duration, c.seats, c.eligibility, ct.type, d.deptName
        FROM course c
        LEFT JOIN coursetype ct ON c.courseTypeId = ct.id
        LEFT JOIN department d ON c.deptId = d.deptId
    """)
    
    # 2. Load Faculty with RICH CONTEXT (JOIN)
    faculty_raw = await Database.fetch_all("""
        SELECT f.name, f.designation, f.qualification, d.deptName
        FROM faculty f
        LEFT JOIN department d ON f.deptId = d.deptId
    """)
    
    faqs_raw = await Database.fetch_all("SELECT question, answer FROM faqs")
    knowledge_raw = await Database.fetch_all("SELECT Keywords, FixedResponseEn, Intent FROM chatbotknowledge")
    
    # Build context strings for RAG (Lean version)
    courses = [{"text": f"Course: {c['course']}, Type: {c['type']}, Department: {c['deptName']}, Duration: {c['duration']}, Seats: {c['seats']}, Eligibility: {c['eligibility']}"} for c in courses_raw]
    faqs = [{"text": f"Q: {f['question']} A: {f['answer']}"} for f in faqs_raw]
    knowledge = [{"text": f"Topic: {k['Intent']} ({k['Keywords']}), Information: {k['FixedResponseEn']}"} for k in knowledge_raw]
    faculty = [{"text": f"Faculty Name: {fac['name']}, Department: {fac['deptName']}, Designation: {fac['designation']}, Qualification: {fac['qualification']}"} for fac in faculty_raw]
    
    nlp = NLPEngine(courses=courses, faqs=faqs, knowledge=knowledge, faculty=faculty)
    print("Class of 2026 Engine Loaded with RICH Deep Context!")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    query = data.get("query", "")
    lang = data.get("lang", "en")
    session_id = data.get("session_id", "default")

    if not query:
        return {"response": "I'm listening..."}

    result = nlp.process_query(query)
    if result.get("is_gibberish"):
        msg = "I didn't quite catch that. Please type a clear question about college." if lang != "hi" else "मुझे समझ नहीं आया। कृपया कॉलेज के बारे में स्पष्ट प्रश्न पूछें।"
        return {"response": msg, "recommendations": []}

    context = result["context"]
    recommendations = result.get("recommendations", [])

    if session_id not in chat_history:
        chat_history[session_id] = []
    history = chat_history[session_id][-4:]

    lang_instructions = {
        "en": "Always reply in clear, professional English.",
        "hi": "Always reply in pure Hindi (Devanagari script).",
        "hinglish": "Always reply in a natural, polite Hinglish mix (Hindi + English). Example: 'BCA ki eligibility 12th pass hai.'"
    }
    
    system_prompt = (
        "You are the NPGC Smart Assistant, created by Pushpesh Srivastava, Krishna Agarwal, Akshat Sharma, and Aditi Srivastava. "
        "Use the provided database context to answer accurately. "
        f"PERSONALITY: {lang_instructions.get(lang, lang_instructions['en'])} "
        "INSTRUCTIONS:\n"
        "1. Identify the Course Type (Certification, Diploma, UG, PG) clearly in the answer.\n"
        "2. For Faculty queries, ALWAYS specify which Department they belong to.\n"
        "3. If details are missing, direct users to npgc.in or support@npgc.in (0522-4021304).\n"
        f"\n\nContext:\n{context}"
    )

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *[{"role": m["role"], "content": m["content"]} for m in history],
                    {"role": "user", "content": query}
                ],
                "temperature": 0.5,
                "max_tokens": 500
            }
        )
        response_text = response.json()["choices"][0]["message"]["content"]
        chat_history[session_id].append({"role": "user", "content": query})
        chat_history[session_id].append({"role": "assistant", "content": response_text})
        
        print(f"Query: {query} | Detected: {result.get('detected_lang')}")
        return {"response": response_text, "recommendations": recommendations, "detected_lang": result.get("detected_lang")}
    except Exception as e:
        return {"response": "Connecting to server...", "recommendations": []}

@app.get("/suggestions")
async def suggestions():
    return {"suggestions": nlp.get_autosuggest_list() if nlp else []}

# THE FINAL FIX: Mount everything from the 'static' folder to the root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
