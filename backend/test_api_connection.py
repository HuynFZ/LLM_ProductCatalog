import os
import requests
import json
from dotenv import load_dotenv

load_dotenv("backend/.env")

gemini_key = os.getenv("GEMINI_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

print("--- Testing OpenAI ---")
if openai_key:
    headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Return a json object with key sql_query and value SELECT 1"}],
        "response_format": {"type": "json_object"}
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
    print("OpenAI Status:", r.status_code)
    if r.status_code == 200:
        print("OpenAI Output:", r.json()["choices"][0]["message"]["content"])
    else:
        print("OpenAI Error:", r.text)

print("\n--- Testing Gemini ---")
if gemini_key:
    # Try gemini-2.5-flash-lite or gemini-flash-latest
    candidates = ["gemini-2.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    for model_name in candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": "Return a json object with key sql_query and value SELECT 1"}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=20)
            print(f"Gemini ({model_name}) Status:", r.status_code)
            if r.status_code == 200:
                text = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print(f"Gemini ({model_name}) Output:", text.strip())
                break
            else:
                print(f"Gemini ({model_name}) Error:", r.text[:150])
        except Exception as e:
            print(f"Gemini ({model_name}) Exception:", e)

