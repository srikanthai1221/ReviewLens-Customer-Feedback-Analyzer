import os
from dotenv import load_dotenv

load_dotenv()  # reads .env so the key is never hard-coded

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))

MAX_ATTEMPTS = 3      # 1 try + 2 automatic retries before "needs_review"
BATCH_SIZE = 20       # reviews per batch (so the progress bar moves)

REQUIRED_COLUMNS = ["review_id", "date", "platform", "rating", "review_text"]