import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
print("API IS",API_BASE_URL)

def api_request(method, endpoint, token=None, json=None, params=None):
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.request(
        method=method,
        url=f"{API_BASE_URL}{endpoint}",
        headers=headers,
        json=json,
        params=params,
    )

    if response.status_code >= 400:
        raise Exception(response.text)

    return response.json()
