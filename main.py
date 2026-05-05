import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import Database
from nlp_engine import NLPEngine
import requests
import traceback
import random
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

async def load_nlp_engine():
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

@app.on_event("startup")
async def startup():
    await load_nlp_engine()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "NPGC Assistant is running"}

@app.get("/refresh")
async def refresh():
    try:
        await load_nlp_engine()
        return {"status": "success", "message": "Knowledge engine refreshed successfully!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

    # Off-topic guard — refuse non-NPGC queries politely
    if result.get("is_off_topic"):
        off_topic_msgs = {
            "en": "I'm your NPGC college assistant and can only help with college-related queries! 😊 Ask me about our courses, admissions, faculty, fees, or facilities.",
            "hi": "मैं NPGC कॉलेज का सहायक हूँ और केवल कॉलेज संबंधी प्रश्नों में मदद कर सकता हूँ! हमारे कोर्स, प्रवेश, फैकल्टी, या सुविधाओं के बारे में पूछें।",
            "hinglish": "Main NPGC college ka assistant hoon aur sirf college se related sawaalon mein help kar sakta hoon! 😊 Courses, admission, faculty ya fees ke baare mein poochho."
        }
        return {
            "response": off_topic_msgs.get(lang, off_topic_msgs["en"]),
            "recommendations": result.get("recommendations", [])
        }

    context = result["context"]
    recommendations = result.get("recommendations", [])

    if session_id not in chat_history:
        chat_history[session_id] = []
    history = chat_history[session_id][-4:]

    lang_instructions = {
        "en": "You are a Senior Academic Advisor. Reply in a professional, comprehensive, and intelligent manner.",
        "hi": "Aap ek Senior Academic Advisor hain. Kripya vistrit, prabhavshali aur formal Hindi mein jawab dein.",
        "hinglish": "You are a Senior Academic Advisor. Give comprehensive, intelligent, and formal answers in a polished Hinglish mix."
    }
    
    system_prompt = (
        "You are the official AI assistant of NPGC — National PG College, Lucknow (website: npgc.in). "
        "Your SOLE purpose is to answer questions about National PG College, Lucknow (NPGC) — its courses, faculty, admissions, fees, departments, facilities, and related topics. "
        "\n\n"
        "=== STRICT SCOPE RULE ===\n"
        "If the user asks anything NOT related to NPGC college (e.g. general knowledge, other colleges, politics, movies, coding help, etc.), "
        "you MUST politely refuse and redirect them. Say something like: "
        "'I can only help with NPGC college-related queries. Please ask me about our courses, admissions, faculty, or facilities!' "
        "Do NOT answer off-topic questions under any circumstance.\n\n"
        "=== VERIFIED NPGC FACTS (Always use these — they override any other source) ===\n"
        "1. BCA (Bachelor of Computer Applications) has a total intake of 120 seats.\n"
        "2. The HOD (Head of Department) of BCA / Department of Computer Science is Dr. Shalini Lamba.\n"
        "3. NPGC does NOT offer B.Tech (Bachelor of Technology). If asked, clearly state this.\n"
        "4. NPGC does NOT offer MBBS or any medical degree programs. If asked, clearly state this.\n\n"
        "=== INSTRUCTIONS ===\n"
        f"TONE: {lang_instructions.get(lang, lang_instructions['en'])}\n"
        "1. DATA SYNTHESIS: Use the provided [COURSE], [FACULTY], [FAQ], and [KNOWLEDGE] data to build complete answers.\n"
        "2. DEPARTMENT CLARITY: There is NO standalone 'BCA Department'. BCA is a course within the 'Department of Computer Science'. Always refer to it as such.\n"
        "3. COMPREHENSIVE LISTS: If the user asks for courses or faculty, list ALL relevant items from the context. Do not truncate.\n"
        "4. CROSS-REFERENCING: If you find a connection (e.g. asking about a department shows its HOD in faculty data), mention it proactively.\n"
        "5. MISSING DATA: If certain details (like exact fees) aren't in the context, provide related info and suggest contacting support@npgc.in.\n"
        "6. STRUCTURE: Use bullet points and clear headings for readability.\n"
        "7. LANGUAGE: Respect the 'TONE' instruction above. If the tone is English, do NOT include Hindi snippets unless explicitly asked.\n"
        f"\n\nContext from Database:\n{context}"
    )

    # Load multiple keys for rotation
    GROQ_KEYS_RAW = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
    GROQ_KEYS = [k.strip() for k in GROQ_KEYS_RAW.split(",") if k.strip()]
    
    if not GROQ_KEYS:
         print("!!! CRITICAL: No GROQ_API_KEY found in environment variables!")
         return {"response": "System configuration error. Please check API keys.", "recommendations": []}

    # Try keys in random order to distribute load
    available_keys = list(GROQ_KEYS)
    random.shuffle(available_keys)
    
    response_text = None
    last_error = ""

    for attempt_key in available_keys:
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {attempt_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *[{"role": m["role"], "content": m["content"]} for m in history],
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 500
                },
                timeout=10
            )
            
            if response.status_code == 429:
                print(f"!!! Rate limit hit for key: {attempt_key[:10]}... Switching to next key.")
                last_error = "Rate limit (429)"
                continue # Try the next key
                
            response.raise_for_status()
            response_text = response.json()["choices"][0]["message"]["content"]
            break # Success! Exit the retry loop
            
        except Exception as e:
            print(f"!!! Error using key {attempt_key[:10]}...: {str(e)}")
            last_error = str(e)
            continue # Try next key if any

    if response_text:
        chat_history[session_id].append({"role": "user", "content": query})
        chat_history[session_id].append({"role": "assistant", "content": response_text})
        
        print(f"Query: {query} | Detected: {result.get('detected_lang')}")
        return {"response": response_text, "recommendations": recommendations, "detected_lang": result.get("detected_lang")}
    else:
        # ALL KEYS FAILED - Fallback to Database context
        print(f"!!! ALL {len(available_keys)} KEYS FAILED. Last error: {last_error}")
        
        if context and len(context.strip()) > 5:
            fallback_prefix = {
                "en": "I'm having trouble connecting to my AI brain, but here's the data from our records:\n\n",
                "hi": "मेरे AI सर्वर में समस्या है, लेकिन कॉलेज रिकॉर्ड्स से जानकारी यहाँ है:\n\n",
                "hinglish": "AI server me thodi dikkat hai, par college records se ye info mili hai:\n\n"
            }
            msg = fallback_prefix.get(lang, fallback_prefix['en']) + context
            return {"response": msg, "recommendations": recommendations, "detected_lang": result.get("detected_lang")}

        return {"response": "Connecting to server... (Low memory or API limit reached)", "recommendations": []}

@app.get("/suggestions")
async def suggestions():
    return {"suggestions": nlp.get_autosuggest_list() if nlp else []}

# THE FINAL FIX: Mount everything from the 'static' folder to the root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
