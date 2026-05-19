from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY=os.getenv("GROQ_API_KEY")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")


llm = ChatOpenAI(
    model="",
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_retries=4
)