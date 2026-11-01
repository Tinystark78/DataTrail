import json
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_POLICY_CHARS = 30000

SYSTEM_PROMPT = """You are PrivacyLens AI, an expert privacy policy auditor and security engine.
Analyze the provided privacy policy text and evaluate the website across these 8 core pillars:
1. Information collected
2. Purpose of collection
3. Third-party sharing
4. Advertising and profiling
5. Data retention
6. International transfers
7. Security practices
8. User rights and deletion

Return ONLY a valid JSON object, with no markdown formatting or extra text, strictly matching this shape:
{
  "headline": "A short, punchy sentence summarizing how trustworthy this site's privacy stance is.",
  "summary": "A 3-sentence clear summary of what data they take, who they share it with, and your rights.",
  "score": 75,
  "grade": "B",
  "pillars": {
    "information_collected": "Specific details on what data is gathered.",
    "purpose_of_collection": "Why they collect the data.",
    "third_party_sharing": "Who receives the data externally.",
    "advertising_and_profiling": "Targeted ad practices and profiling status.",
    "data_retention": "How long data is kept.",
    "international_transfers": "Cross-border data movement details.",
    "security_practices": "Encryption and security measures.",
    "user_rights_and_deletion": "How users can access or delete their data."
  },
  "facts": {
    "data_collected": ["Email", "IP Address", "Device Info", "Cookies"],
    "shared_with_third_parties": true,
    "third_parties": ["Ad networks", "Analytics providers"],
    "retention_period": "As long as account is active",
    "can_delete_account": true
  },
  "reasons": [
    "Extensive third-party ad sharing identified.",
    "Clear account deletion mechanisms provided."
  ]
}
Rules: Be factual, concise, and base your answers strictly on the policy text. Use null if not stated."""

def analyze(policy_text: str, tracker_findings: list = None) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": policy_text[:MAX_POLICY_CHARS]}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4000},
    }
    
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")

    text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    return json.loads(text)