const chatBody = document.getElementById('chat-body');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const langSelect = document.getElementById('lang-select');
const welcomeText = document.getElementById('welcome-text');
const suggestionsContainer = document.getElementById('suggestions');
const toggleVoiceBtn = document.getElementById('toggle-voice');
const clearChatBtn = document.getElementById('clear-chat');
const micBtn = document.getElementById('mic-btn');
const autocompleteBox = document.getElementById('autocomplete-results');

let currentLang = 'en';
let isVoiceEnabled = false;
let sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
let allSuggestions = [];

const config = {
    en: {
        welcome: "Hello! I am your NPGC Assistant. How can I help you today?",
        placeholder: "Type your message...",
        rotatingPlaceholders: ["How to apply?", "When are admissions starting?", "Tell me about BCA fees", "Who is the HOD for CS?"],
        suggestions: ["BCA Fees & Seats", "Admission 2026 Latest", "Hostel Facilities", "Placement Records"]
    },
    hi: {
        welcome: "नमस्ते! मैं आपका NPGC सहायक हूँ। मैं आपकी कैसे मदद कर सकता हूँ?",
        placeholder: "अपना संदेश लिखें...",
        rotatingPlaceholders: ["आवेदन कैसे करें?", "प्रवेश कब शुरू हो रहे हैं?", "BCA शुल्क के बारे में बताएं", "CS के HOD कौन हैं?"],
        suggestions: ["BCA शुल्क और सीटें", "प्रवेश 2026 नवीनतम", "छात्रावास की सुविधा", "प्लेसमेंट रिकॉर्ड"]
    },
    hinglish: {
        welcome: "Hello! Main aapka NPGC Assistant hoon. Aapki kya help kar sakta hoon?",
        placeholder: "Apna question yahan type karein...",
        rotatingPlaceholders: ["BCA fees kya hai?", "B.Com admission news", "Teachers ki list", "Hostel facility available hai?"],
        suggestions: ["BCA Fees kya hai?", "Admission 2026 News", "Hostel kaise milega?", "Placement statistics"]
    }
};

// 1. Rotating Placeholder with Typing Effect
let placeholderIndex = 0;
let charIndex = 0;
let isDeleting = false;

function typePlaceholder() {
    const placeholders = config[currentLang].rotatingPlaceholders;
    const currentText = placeholders[placeholderIndex];
    
    if (isDeleting) {
        userInput.placeholder = currentText.substring(0, charIndex--);
    } else {
        userInput.placeholder = currentText.substring(0, charIndex++);
    }

    if (!isDeleting && charIndex === currentText.length + 1) {
        isDeleting = true;
        setTimeout(typePlaceholder, 2000); // Wait at end
    } else if (isDeleting && charIndex === 0) {
        isDeleting = false;
        placeholderIndex = (placeholderIndex + 1) % placeholders.length;
        setTimeout(typePlaceholder, 500);
    } else {
        setTimeout(typePlaceholder, isDeleting ? 50 : 100);
    }
}

// 2. Autocomplete Suggestions
async function fetchSuggestions() {
    try {
        const response = await fetch('/suggestions');
        const data = await response.json();
        allSuggestions = data.suggestions;
    } catch (e) { console.error("Could not fetch suggestions", e); }
}

function realTimeLangDetect(text) {
    if (!text || text.length < 3) return null;
    
    // 1. Hindi (Devanagari)
    if (/[\u0900-\u097F]/.test(text)) return "hi";
    
    // 2. Hinglish (Keywords)
    const hinglishKeywords = ["hai", "kya", "kar", "ho", "me", "se", "ka", "ki", "ke", "kab", "kon", "raha", "rahi"];
    const words = text.toLowerCase().split(/\W+/);
    if (words.some(w => hinglishKeywords.includes(w))) return "hinglish";
    
    return null;
}

userInput.addEventListener('input', () => {
    const val = userInput.value.trim();
    
    // Auto-detect language while typing
    const detected = realTimeLangDetect(val);
    if (detected && detected !== currentLang) {
        langSelect.value = detected;
        changeLanguage();
    }

    const valLower = val.toLowerCase();
    autocompleteBox.innerHTML = '';
    if (!val) {
        autocompleteBox.style.display = 'none';
        return;
    }

    const filtered = allSuggestions.filter(s => s.toLowerCase().includes(val)).slice(0, 5);
    if (filtered.length > 0) {
        filtered.forEach(item => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.textContent = item;
            div.onclick = () => {
                userInput.value = item;
                autocompleteBox.style.display = 'none';
                sendMessage();
            };
            autocompleteBox.appendChild(div);
        });
        autocompleteBox.style.display = 'block';
    } else {
        autocompleteBox.style.display = 'none';
    }
});

// Close autocomplete on click outside
document.addEventListener('click', (e) => {
    if (e.target !== userInput) autocompleteBox.style.display = 'none';
});

// 3. Core Chat Logic
function changeLanguage() {
    currentLang = langSelect.value;
    welcomeText.textContent = config[currentLang].welcome;
    placeholderIndex = 0;
    charIndex = 0;
    isDeleting = false;
    renderSuggestions();
}

function renderSuggestions(customSuggestions = null) {
    const list = customSuggestions || config[currentLang].suggestions;
    if (!list || list.length === 0) {
        suggestionsContainer.style.display = 'none';
        return;
    }

    suggestionsContainer.innerHTML = '';
    suggestionsContainer.style.display = 'flex';
    
    // Crucial: Move the container to the end of the chat history
    chatBody.appendChild(suggestionsContainer);

    list.forEach(suggest => {
        const chip = document.createElement('div');
        chip.className = 'suggestion-chip fadeIn';
        chip.textContent = suggest;
        chip.onclick = () => sendMessage(suggest);
        suggestionsContainer.appendChild(chip);
    });
    
    // Auto-scroll to show the new suggestions
    chatBody.scrollTop = chatBody.scrollHeight;
}

function addMessage(text, isUser = false, recommendations = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'} animated fadeIn`;
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    msgDiv.innerHTML = `
        <div class="message-content">
            <p>${text.replace(/\n/g, '<br>')}</p>
        </div>
        <span class="message-time">${time}</span>
    `;
    
    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;

    if (!isUser) {
        if (isVoiceEnabled) speakText(text);
        if (recommendations && recommendations.length > 0) {
            setTimeout(() => renderSuggestions(recommendations), 500);
        }
    }
}

async function sendMessage(text = null) {
    const message = text || userInput.value.trim();
    if (!message) return;

    if (!text) userInput.value = '';
    autocompleteBox.style.display = 'none';
    suggestionsContainer.style.display = 'none';

    addMessage(message, true);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query: message, 
                lang: currentLang,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        // Auto-switch Language if detected
        if (data.detected_lang && data.detected_lang !== currentLang) {
            langSelect.value = data.detected_lang;
            changeLanguage();
        }

        addMessage(data.response, false, data.recommendations);
    } catch (error) {
        addMessage(currentLang === 'hi' ? "Seva upalabd nahi hai." : "Service unavailable.");
    }
}

// 4. Voice Logic
function speakText(text) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';
    window.speechSynthesis.speak(utterance);
}

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
    const recognition = new Recognition();
    micBtn.onclick = () => {
        recognition.lang = currentLang === 'hi' ? 'hi-IN' : 'en-IN';
        recognition.start();
        micBtn.classList.add('recording');
    };
    recognition.onresult = (e) => {
        userInput.value = e.results[0][0].transcript;
        sendMessage();
    };
    recognition.onend = () => micBtn.classList.remove('recording');
}

toggleVoiceBtn.onclick = () => {
    isVoiceEnabled = !isVoiceEnabled;
    toggleVoiceBtn.classList.toggle('active');
    toggleVoiceBtn.querySelector('i').className = isVoiceEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute';
    if (!isVoiceEnabled) window.speechSynthesis.cancel();
};

clearChatBtn.onclick = () => {
    window.speechSynthesis.cancel();
    location.reload(); // Hard reset for clean state
};

userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });
sendBtn.onclick = () => sendMessage();

// Init
fetchSuggestions();
typePlaceholder();
renderSuggestions();
