from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from schemas import ReviewAnalysis, WeeklyInsights

CLASSIFY_SYSTEM = """You are a customer-feedback analyst for a restaurant and food-delivery business.
Reviews may be in English, Tamil, Tanglish (Tamil typed in English letters), Hindi, Hinglish,
Telugu, Kannada, Malayalam (native script or romanized), Spanish, German, French or other languages.

Fill every field using these rules.

sentiment: positive | neutral | negative. For mixed reviews pick the dominant feeling;
use the star rating as a tie-breaker.

category (pick the ONE main issue or praise):
- food_quality: taste, freshness, spice, oil, hygiene (hair, insects, stale or expired food)
- delivery: late, food cold because of delay, cancelled, not delivered, missing items, rider would not come to the door
- price: expensive, extra charges, delivery/platform/packing fees, small portion for the price, value for money
- staff: rude or polite delivery person or restaurant staff, dine-in service, ambience
- packaging: spilled, leaking, broken or cracked containers, melted, neat or eco-friendly packing
- app: ordering app, coupons, payment, double charge, refunds, customer support chat or bot

urgency:
- high: health or hygiene risk, wrong order (especially veg/non-veg), refund or double charge pending,
  order not delivered or cancelled, abusive or rude behaviour
- medium: a clear complaint that should be fixed but is not urgent (late, cold, small portion, extra charges, spill)
- low: positive or neutral feedback, minor suggestions

language: the language as the customer wrote it, e.g. "English", "Tamil", "Tanglish", "Hindi",
"Hinglish", "Telugu (Romanized)", "Spanish".

summary: ONE short sentence in English, even when the review is in another language.
Translate the meaning; do not copy the original words.

suggested_reply: 1-3 polite sentences in English from the brand. Apologise for problems and thank for praise.
For high urgency, ask the customer to DM their order ID. Never promise a specific refund amount."""

classify_prompt = ChatPromptTemplate.from_messages([
    ("system", CLASSIFY_SYSTEM),
    ("human", "Platform: {platform}\nStar rating: {rating}/5\nReview: {review_text}"),
])

REPORT_SYSTEM = """You write a short weekly customer-feedback report for a restaurant operations manager.
You receive the top complaint and praise categories (already ranked) with one-line review summaries.
Rules:
- Use ONLY the information given. Do NOT write any numbers, counts or percentages; the app adds those.
- For each complaint category given, write a 2-5 word headline naming the most common specific issue,
  and one sentence of detail (e.g. which platform or dish it shows up in).
- Do the same for each praise category.
- Write exactly 3 action items: concrete steps the manager can take this week. Start each with a verb."""

report_prompt = ChatPromptTemplate.from_messages([
    ("system", REPORT_SYSTEM),
    ("human",
     "Report period: {period}\n\n"
     "TOP COMPLAINT CATEGORIES (most negative reviews first):\n{complaints}\n\n"
     "TOP PRAISE CATEGORIES (most positive reviews first):\n{praises}\n\n"
     "High-urgency reviews this period: {urgent_count}"),
])


def get_llm() -> ChatOpenAI:
    # max_retries here handles network errors / rate limits (429) automatically
    return ChatOpenAI(model=OPENAI_MODEL, temperature=0, api_key=OPENAI_API_KEY,
                      timeout=60, max_retries=3)


def build_classify_chain():
    """Per-review MAP chain: prompt | LLM forced into the ReviewAnalysis schema."""
    return classify_prompt | get_llm().with_structured_output(ReviewAnalysis)


def build_report_chain():
    """REDUCE chain: reads aggregated results and writes the weekly insights."""
    return report_prompt | get_llm().with_structured_output(WeeklyInsights)