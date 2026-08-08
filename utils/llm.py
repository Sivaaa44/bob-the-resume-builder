import os
from dotenv import load_dotenv

load_dotenv()

def validate_groq_key() -> str:
    """
    Validates GROQ_API_KEY presence in environment.
    Raises ValueError with clear message if missing or empty.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or not groq_key.strip():
        raise ValueError(
            "GROQ_API_KEY is missing or empty in your .env file!\n"
            "Please open .env in the project root and set your Groq API key:\n"
            "  GROQ_API_KEY=gsk_..."
        )
    return groq_key.strip()

def get_llm():
    """
    Returns configured ChatGroq LLM instance if GROQ_API_KEY is set and non-empty.
    Returns None if key is missing/empty (enabling heuristic fallback mode for testing/dry-runs).
    """
    try:
        groq_key = validate_groq_key()
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=groq_key, temperature=0.2)
    except ValueError:
        return None
