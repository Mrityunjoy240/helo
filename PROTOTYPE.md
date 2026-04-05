# BCREC Voice Agent - Gemini LLM Prototype

## Quick Start Guide

### Step 1: Get Gemini API Key

1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click "Get API Key" in the sidebar
4. Create a new API key
5. Copy the key

### Step 2: Setup Environment

```bash
# Navigate to project
cd Ai_voice-main/Ai_voice-main

# Copy environment file
copy local.env.example local.env

# Edit local.env and add your Gemini API key
# GEMINI_API_KEY=your_key_here
```

### Step 3: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Step 4: Start the Server

```bash
# Start backend
python -m uvicorn app.main:app --reload --port 8000

# In another terminal, start frontend
cd frontend
npm install
npm run dev
```

### Step 5: Open in Browser

Open http://localhost:5173

You should see:
- "Gemini Active (Prototype)" status chip
- Voice chat interface
- Ability to type or speak queries

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/qa/llm-query` | POST | **PROTOTYPE** - Uses Gemini |
| `/qa/hybrid-query` | POST | Local hybrid (Ollama) |
| `/qa/query` | POST | Legacy keyword-based |

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
│   /qa/llm-query endpoint                                   │
│       ↓                                                      │
│   Gemini Service                                              │
│   ├── System Prompt (rules)                                 │
│   ├── Knowledge Base (full JSON)                            │
│   └── Conversation History (last 4)                         │
│       ↓                                                      │
│   Gemini 2.0 Flash                                           │
│       ↓                                                      │
│   Natural Response                                           │
└─────────────────────────────────────────────────────────────┘
```

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
| Gemini API | Free (15 req/min, 1500/day) |
| Hosting | Your server |
| Total | **₹0** |

---

## Data Privacy (Prototype Warning)

⚠️ **This prototype sends data to Google servers.**

For demo purposes, this is acceptable. For production, you must switch to the local hybrid approach.

---

## Switching Between Modes

In `frontend/src/components/VoiceChat/VoiceChat.tsx`:

```typescript
const QUERY_ENDPOINT = '/qa/llm-query';  // Prototype (Gemini)
// OR
const QUERY_ENDPOINT = '/qa/hybrid-query';  // Production (Local)
```

---

## Troubleshooting

### Gemini Not Working?
1. Check API key is set in `local.env`
2. Check `/qa/health` shows `"gemini_available": true`
3. Check server logs for errors

### Slow Responses?
- Gemini free tier: ~500ms-1s
- This is normal for free tier

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
| `master` | Current prototype with Gemini |
| `hybrid-safe-point` | Pre-Gemini (local hybrid only) |

To return to local-only: `git checkout hybrid-safe-point`

---

## Support

For issues or questions about this prototype, check:
- Server logs: `python -m uvicorn app.main:app --log-level debug`
- Gemini API status: https://status.ai.google.com
