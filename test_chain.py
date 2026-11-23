import json
import pandas as pd
from chains import build_classify_chain
from config import MAX_CONCURRENCY

df = pd.read_csv("data/food_portal_reviews_multilingual.csv")
# Tamil refund, Tanglish, English wrong order, Hindi insect, one-word "meh"
ids = ["R-1002", "R-1003", "R-1009", "R-1011", "R-1098"]
sample = df[df["review_id"].isin(ids)]

chain = build_classify_chain()
inputs = [{"platform": r.platform, "rating": r.rating, "review_text": r.review_text}
          for r in sample.itertuples()]

results = chain.batch(inputs, config={"max_concurrency": MAX_CONCURRENCY})

for rid, text, res in zip(sample["review_id"], sample["review_text"], results):
    print(f"\n{rid} | {text}")
    print(json.dumps({"review_id": rid, **res.model_dump()}, indent=2, ensure_ascii=False))