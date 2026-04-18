import re
import numpy as np
from thefuzz import process, fuzz
from sentence_transformers import SentenceTransformer

class NLPEngine:
    def __init__(self, courses=None, faqs=None, knowledge=None, faculty=None):
        self.course_corpus = courses or []
        self.faq_corpus = faqs or []
        self.knowledge_corpus = knowledge or []
        self.faculty_corpus = faculty or []
        
        print("Initializing NLP Engine with Semantic Model...")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        self.intents = {
            "FEES": ["fee", "fees", "cost", "price", "paisa", "rupaye", "shulk", "फीस", "शुल्क"],
            "DURATION": ["duration", "time", "period", "years", "saal", "waqt", "समय", "अवधि"],
            "ELIGIBILITY": ["eligibility", "qualification", "criteria", "apply", "yogya", "योग्यता", "पात्रता"],
            "FACULTY": ["faculty", "teacher", "professor", "hod", "staff", "mam", "sir", "dr", "शिक्षक", "प्राध्यापक", "संकाय", "सदस्य", "संकाय सदस्य", "प्रोफेसर"],
            "ADMISSION": ["admission", "apply", "deadline", "date", "form", "प्रवेश", "दाखिला"],
            "GREETING": ["hi", "hello", "hey", "namaste", "pranam", "नमस्ते", "हेलो"],
            "CERTIFICATION": ["certification", "certificate", "diploma", "vocational", "सर्टिफिकेशन", "प्रमाणपत्र", "डिप्लोमा"],
            "AVAILABLE": ["available", "list", "show", "tell", "kya hai", "kon se", "उपलब्ध", "कौन से", "बताएं", "पाठ्यक्रम", "कोर्स", "सीट", "सीटें"]
        }

    def detect_language(self, text):
        # 1. Hindi (Devanagari)
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        
        # 2. Hinglish (Romanized Hindi)
        text_lower = text.lower()
        hinglish_keywords = ["hai", "kya", "kar", "ho", "me", "se", "ka", "ki", "ke", "kab", "kon", "raha", "rahi", "paisa", "rupay", "shulk"]
        
        # Simple word-based check
        words = re.findall(r'\w+', text_lower)
        hits = sum(1 for w in words if w in hinglish_keywords)
        
        if hits >= 1:
            return "hinglish"
            
        return "en"

    def clean_text(self, text):
        return text.lower().strip()

    def get_semantic_matches(self, query_vector, corpus, top_k=5):
        if not corpus: return []
        scores = []
        for item in corpus:
            if item.get('embedding'):
                target_vec = np.array(item['embedding'])
                sim = np.dot(query_vector, target_vec)
                scores.append((float(sim), item))
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]

    def is_gibberish(self, text):
        if len(text) < 3: return True
        # Allow Devanagari (Hindi) characters: \u0900-\u097F
        if re.search(r'[\u0900-\u097F]', text):
            return False
            
        vowels = 'aeiouAEIOU'
        vcount = sum(1 for char in text if char in vowels)
        if len(text) > 8 and vcount < 1: return True
        if any(text.count(c) > 6 for c in set(text)): return True 
        return False

    def process_query(self, text):
        cleaned_query = self.clean_text(text)
        if self.is_gibberish(cleaned_query):
            return {"is_gibberish": True}

        query_vector = self.model.encode(cleaned_query)
        
        intent = "UNKNOWN"
        for i_name, keywords in self.intents.items():
            if any(kw in cleaned_query for kw in keywords):
                intent = i_name
                break
        
        matches = {
            "courses": self.get_semantic_matches(query_vector, self.course_corpus),
            "faqs": self.get_semantic_matches(query_vector, self.faq_corpus),
            "knowledge": self.get_semantic_matches(query_vector, self.knowledge_corpus),
            "faculty": self.get_semantic_matches(query_vector, self.faculty_corpus)
        }
        
        all_matches = matches["courses"] + matches["faqs"] + matches["knowledge"] + matches["faculty"]
        all_matches.sort(key=lambda x: x[0], reverse=True)
        
        context_items = []
        recommendations = []
        
        intent_fallbacks = {
            "FEES": ["BCA Fees & Seats", "Scholarship Window", "Hostel Facilities"],
            "FACULTY": ["Faculty of B.Sc", "HOD for CS", "Staff Contact"],
            "ADMISSION": ["Admission 2026 Latest", "Course List", "How to apply?"],
            "PLACEMENT": ["BCA Placement", "B.Com Placement", "Placement Records"]
        }
        
        # Top 3 for context
        for score, item in all_matches[:3]:
            if score > 0.35:
                context_items.append(item['text'])
        
        # 4. Smart Recommendations & Backfill
        for score, item in all_matches[3:10]: 
            if score > 0.2:
                text = item['text']
                if "Q: " in text: text = text.split(" A:")[0].replace("Q: ", "")
                elif "Course: " in text: text = text.split(",")[0].replace("Course: ", "") + " Details"
                elif "Topic: " in text: 
                    text = text.split(" (")[0].replace("Topic: ", "")
                    # Humanize technical intents (e.g., ADMISSION_SEATS -> Admission Seats)
                    text = text.replace("_", " ").title()
                elif "Faculty Name: " in text: 
                    text = text.split(",")[0].replace("Faculty Name: ", "")
                
                if text not in recommendations: recommendations.append(text)
        
        if len(recommendations) < 3:
            backfills = intent_fallbacks.get(intent, ["Course List", "Admission 2026 Latest", "Hostel Info"])
            for bf in backfills:
                if bf not in recommendations: recommendations.append(bf)
                if len(recommendations) >= 4: break

        return {
            "intent": intent,
            "context": "\n".join(context_items),
            "recommendations": recommendations[:3], 
            "detected_lang": self.detect_language(text),
            "is_gibberish": False
        }

    def get_autosuggest_list(self):
        suggestions = []
        for c in self.course_corpus:
            match = re.search(r"Course: (.*?),", c['text'])
            if match: suggestions.append(match.group(1))
        for f in self.faq_corpus:
            match = re.search(r"Q: (.*?) A:", f['text'])
            if match: suggestions.append(match.group(1))
        for k in self.knowledge_corpus:
             match = re.search(r"Topic: (.*?) \(", k['text'])
             if match: suggestions.append(match.group(1))
        for fac in self.faculty_corpus:
             match = re.search(r"Faculty Name: (.*?),", fac['text'])
             if match: suggestions.append(match.group(1))

        return list(set(suggestions))
