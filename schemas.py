from typing import List, Literal, get_args
from pydantic import BaseModel, Field, field_validator

Sentiment = Literal["positive", "neutral", "negative"]
Category = Literal["food_quality", "delivery", "price", "staff", "packaging", "app"]
Urgency = Literal["low", "medium", "high"]

SENTIMENTS = list(get_args(Sentiment))
CATEGORIES = list(get_args(Category))
URGENCIES = list(get_args(Urgency))


class ReviewAnalysis(BaseModel):
    """Structured analysis of ONE customer review."""
    sentiment: Sentiment = Field(description="Overall customer mood")
    category: Category = Field(description="The ONE main topic of the review")
    urgency: Urgency = Field(description="How fast the team must respond")
    language: str = Field(description="Language of the review, e.g. English, Tamil, Tanglish, Hindi, Hinglish")
    summary: str = Field(description="One short sentence in English")
    suggested_reply: str = Field(description="Polite, ready-to-post reply in English")

    @field_validator("summary", "suggested_reply")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class Insight(BaseModel):
    category: Category = Field(description="Category this insight is about")
    headline: str = Field(description="2-5 word label, e.g. 'Late delivery'")
    detail: str = Field(description="One sentence describing the pattern, using only the data given")


class WeeklyInsights(BaseModel):
    """Narrative part of the weekly report. All numbers are added by pandas, not the LLM."""
    top_complaints: List[Insight]
    top_praises: List[Insight]
    action_items: List[str] = Field(description="Exactly 3 concrete action items, each starting with a verb")