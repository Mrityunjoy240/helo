# BCREC Voice Agent - Groq LLM Prototype

## Quick Start Guide

### Step 1: Get Groq API Key (Already configured)

The Groq API key is already set in `local.env`:
```
GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
```

If you need a new key:
1. Go to https://console.groq.com
2. Sign up (free)
3. Create API key
4. Copy to `local.env`

### Step 2: Install & Setup

```bash
# Navigate to project
cd Ai_voice-main/Ai_voice-main

# Copy environment file (if not exists)
copy local.env.example local.env

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### Step 3: Start the Server

```bash
# Start backend (in one terminal)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Start frontend (in another terminal)
cd frontend
npm install
npm run dev
```

### Step 4: Open in Browser

Open http://localhost:5173

You should see:
- "Groq Active (Prototype)" status chip (blue)
- Voice chat interface
- Ability to type or speak queries

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/qa/groq-query` | POST | **PROTOTYPE** - Uses Groq Llama 3.3 70B |
| `/qa/hybrid-query` | POST | Local hybrid (Ollama) |
| `/qa/query` | POST | Legacy keyword-based |
| `/qa/health` | GET | Shows Groq/Ollama status |

---

## Query Examples to Test

### Basic Queries
```
What is the fee for CSE?
Kitna paisa lagta hai CSE ke liye?
Documents kya chahiye admission ke liye?
```

### Follow-up Queries
```
My rank is 20000. What can I get?
What about placement for that?
Kitni salary milti hai?
```

### Edge Cases
```
asdfghjkl
Tell me everything about college
I hate coding. What branch should I take?
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PROTOTYPE FLOW                           │
│                                                              │
│   User Query                                                 │
│       ↓                                                      │
│   Frontend (React)                                           │
│       ↓                                                      │
│   /qa/groq-query endpoint                                   │
│       ↓                                                      │
│   Groq Service                                                │
│   ├── System Prompt (rules)                                  │
│   ├── Knowledge Base (full JSON)                            │
│   └── Conversation History (last 4)                         │
│       ↓                                                      │
│   Groq Llama 3.3 70B                                         │
│       ↓                                                      │
│   Natural Response                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Why Groq Instead of Gemini?

| Feature | Groq | Gemini |
|---------|------|--------|
| Speed | ~500ms (FAST) | ~2-3s |
| Model | Llama 3.3 70B | Gemini 2.0 Flash |
| Free Tier | Unlimited requests | 15 req/min |
| Accuracy | Excellent | Good |
| Context Window | 128K tokens | 1M tokens |

**Groq wins for voice assistant use cases** because:
1. Speed is critical for real-time voice interaction
2. Llama 3.3 70B handles complex queries well
3. No rate limits for prototype/demo

---

## Knowledge Base

The prototype uses `combined_kb.json` which contains:
- College info (name, contact, NAAC grade)
- B.Tech courses (CSE, IT, ECE, etc.)
- Fees structure
- Placement statistics
- Hostel facilities
- Scholarships
- Admission process

**Non-technical staff can edit this file directly to update information.**

---

## Cost

| Component | Cost |
|-----------|------|
| Groq API | **FREE** (current tier) |
| Hosting | Your server |
| Total | **₹0** |

---

## Data Privacy (Prototype Warning)

⚠️ **This prototype sends data to Groq servers.**

For demo purposes, this is acceptable. For production, switch to the local hybrid approach.

---

## Switching Between Modes

In `frontend/src/components/VoiceChat/VoiceChat.tsx`:

```typescript
const QUERY_ENDPOINT = '/qa/groq-query';    // Prototype (Groq) - FAST & ACCURATE
const QUERY_ENDPOINT = '/qa/hybrid-query';    // Production (Local) - PRIVACY
```

---

## Troubleshooting

### Groq Not Working?
1. Check API key is set in `local.env`
2. Check `/qa/health` shows `"groq_available": true`
3. Check server logs for errors

### Slow Responses?
- Groq is FAST (~500ms)
- If slow, check your internet connection

### Knowledge Base Not Found?
- Ensure `backend/data/knowledge_base/combined_kb.json` exists
- Check file permissions

---

## Next Steps After Demo

1. **If approved**: Proceed with production hardware (₹3+ Lakhs)
2. **If rejected**: Continue with hybrid local approach
3. **If changes needed**: Update `combined_kb.json` and redeploy

---

## Git Branches

| Branch | Purpose |
|--------|---------|
| `master` | Current prototype with Groq |
| `hybrid-safe-point` | Pre-Groq (local hybrid only) |

To return to local-only: `git checkout hybrid-safe-point`

---

## Support

For issues or questions about this prototype, check:
- Server logs: `python -m uvicorn app.main:app --log-level debug`
- Groq API status: https://status.groq.com
