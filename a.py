import os
import json
import requests                 #type: ignore
from dotenv import load_dotenv  #type: ignore

# Load .env variables
load_dotenv(load_dotenv(dotenv_path="api.env"))

api_key = os.getenv("NVIDIA_API_KEY")

request_content = "Explain the working procedure of LLMs in simple terms."

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "model": "qwen/qwen3-next-80b-a3b-thinking",
    "messages": [{f"role": "user", "content": request_content}],
}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(response.json())

# Write the full response JSON to a file so the HTML can fetch and display it live
try:
    out = response.json()
    # include a fetched_at timestamp so the file changes on each run even if the API body is identical
    out_top = {"fetched_at": __import__("time").time(), "response": out}
    with open("response.json", "w", encoding="utf-8") as f:
        json.dump(out_top, f, indent=2, ensure_ascii=False)
    print("Wrote response.json")
    # Also write a small JS file that assigns the response to a global variable.
    try:
        with open("response_data.js", "w", encoding="utf-8") as jf:
            # window.__RESPONSE will be available when opening response.html via file://
            jf.write("window.__RESPONSE = ")
            json.dump(out_top, jf, ensure_ascii=False)
            jf.write(";\n")
        print("Wrote response_data.js")
    except Exception as e:
        print("Failed to write response_data.js:", e)
except Exception as e:
    print("Failed to write response.json:", e)
