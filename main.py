import os
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Load env vars from .env if you want
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DIAGNOSIS_API_URL = os.getenv("DIAGNOSIS_API_URL")  # from Postman docs
DIAGNOSIS_API_KEY = os.getenv("DIAGNOSIS_API_KEY")  # if required
DIAGNOSIS_CREATE_URL = os.getenv("DIAGNOSIS_CREATE_URL")
DIAGNOSIS_RETRIEVE_URL = os.getenv("DIAGNOSIS_RETRIEVE_URL")
# print("Loaded API Key:", DIAGNOSIS_API_KEY)
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=OPENAI_API_KEY)


# Load knowledge base
KB_PATH = Path("data/jubaili_kb.md")
if not KB_PATH.exists():
    raise RuntimeError(f"Knowledge base file not found at {KB_PATH}")

JUBAILI_KB = KB_PATH.read_text(encoding="utf-8")

app = FastAPI(title="Jubaili Agrotec Avatar Backend")

# CORS to allow HeyGen / web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    answer: str


class DiagnoseResponse(BaseModel):
    disease_name: str
    raw_api_response: dict
    answer: str


SYSTEM_PROMPT_BASE = """
You are the official Jubaili Agrotec (pronounced "Ju-bai-lee") Virtual Advisor.

You must:
- Use ONLY the Jubaili Agrotec knowledge base provided.
- If information is not in the KB, say: "I'm sorry, I don't have information about that."
- Always follow Jubaili's tone: friendly, expert, farmer-focused.
- When appropriate, recommend relevant Jubaili products with correct names and usage from the KB.
- Do NOT invent products or diseases that are not in the KB.
- End each answer with: "Jubaili Agrotec — Let's Grow Together."
"""


def ask_llm(user_message: str, extra_context: Optional[str] = None) -> str:
    """
    Ask OpenAI model using the Jubaili KB as context.
    extra_context: any extra info like diagnosed disease from image.
    """
    context = JUBAILI_KB
    if extra_context:
        context = context + "\n\nAdditional context:\n" + extra_context

    system_prompt = SYSTEM_PROMPT_BASE + "\n\nJubaili Knowledge Base:\n" + context

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",  # or gpt-4.1 if you prefer
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
    )
    return completion.choices[0].message.content


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    General text Q&A based on the Jubaili knowledge base.
    This is the endpoint HeyGen should call for text questions.
    """
    answer = ask_llm(req.text)
    return ChatResponse(answer=answer)


@app.post("/diagnose-simple")
async def diagnose_simple(file: UploadFile = File(...)):
    headers = {
        "Api-Key": DIAGNOSIS_API_KEY,
        "accept": "application/json"
    }

    # Cropwise expects `images` array
    files = [
        ('images', (file.filename, await file.read(), file.content_type))
    ]

    # Only allowed modifier
    data = {
        "similar_images": "true"
    }

    resp = requests.post(
        DIAGNOSIS_CREATE_URL,
        headers=headers,
        files=files,
        data=data
    )

    # If API rejects → return raw error for debugging
    try:
        resp.raise_for_status()
    except Exception:
        return {
            "error": resp.text,
            "status_code": resp.status_code
        }

    raw = resp.json()

    # Extract highest-probability disease
    disease_name = "UNKNOWN"
    probability = 0.0

    try:
        suggestions = raw["result"]["disease"]["suggestions"]
        if suggestions:
            best = max(suggestions, key=lambda x: x["probability"])
            disease_name = best["name"]
            probability = best["probability"]
    except Exception as e:
        return {"parse_error": str(e), "raw": raw}

    return {
        "disease_name": disease_name,
        "probability": probability,
        "raw": raw
    }


