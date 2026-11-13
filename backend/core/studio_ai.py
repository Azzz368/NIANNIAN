import os

from openai import OpenAI


def model() -> str:
    return os.getenv("APIMART_STUDIO_MODEL", "").strip() or "gpt-6-luna"


def client() -> OpenAI:
    key = os.getenv("APIMART_API_KEY", "").strip()
    if not key:
        raise ValueError("请先配置 APIMART_API_KEY，再使用影像制作台 AI")
    base_url = os.getenv("APIMART_BASE_URL", "").strip() or "https://api.apimart.ai/v1"
    return OpenAI(api_key=key, base_url=base_url.rstrip("/"))