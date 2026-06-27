import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

LLM_MODEL = os.environ["LLM_MODEL"]
LLM_PROVIDER = os.environ["LLM_PROVIDER"]
