import pandas as pd

from chains import build_classify_chain, build_report_chain
from config import BATCH_SIZE, MAX_ATTEMPTS, MAX_CONCURRENCY, REQUIRED_COLUMNS
from schemas import SENTIMENTS, ReviewAnalysis

OUTPUT_COLS = ["sentiment", "category", "urgency", "language", "summary", "suggested_reply"]


# ---------- 02 VALIDATE ----------
def validate_reviews(raw: pd.DataFrame):
    df = raw.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

        # Keep only the input columns, so re-uploading an exported (enriched) CSV still works
    keep = REQUIRED_COLUMNS + (["language"] if "language" in df.columns else [])
    df = df[keep]

    if "language" in df.columns:  # keep the file's own language column separately
        df = df.rename(columns={"language": "source_language"})

    before = len(df)
    df = df.dropna(subset=["review_text"])
    df["review_text"] = df["review_text"].astype(str).str.strip()
    df = df[df["review_text"] != ""]
    df = df.drop_duplicates(subset="review_id")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    return df.reset_index(drop=True), before - len(df)


# ---------- 03 CLASSIFY (batch + retry) ----------
def analyse_reviews(df: pd.DataFrame, progress_callback=None) -> pd.DataFrame:
    chain = build_classify_chain()
    inputs = [{"platform": r["platform"], "rating": r["rating"], "review_text": r["review_text"]}
              for _, r in df.iterrows()]
    total = len(inputs)
    results = [None] * total
    pending = list(range(total))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not pending:
            break
        failed = []
        for start in range(0, len(pending), BATCH_SIZE):
            chunk = pending[start:start + BATCH_SIZE]
            outputs = chain.batch(
                [inputs[i] for i in chunk],
                config={"max_concurrency": MAX_CONCURRENCY},
                return_exceptions=True,  # one bad review doesn't crash the batch
            )
            for i, out in zip(chunk, outputs):
                if isinstance(out, ReviewAnalysis):
                    results[i] = out
                else:
                    failed.append(i)  # invalid value / parse error → retry next pass
            if progress_callback:
                progress_callback(sum(r is not None for r in results), total, attempt)
        pending = failed

    rows = []
    for res in results:
        if res is None:
            rows.append({c: "needs_review" if c in ("sentiment", "category", "urgency") else ""
                         for c in OUTPUT_COLS} | {"status": "needs_review"})
        else:
            rows.append(res.model_dump() | {"status": "ok"})
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# ---------- 04 AGGREGATE (pandas = exact numbers) ----------
def compute_stats(enriched: pd.DataFrame) -> dict:
    ok = enriched[enriched["status"] == "ok"]
    n = len(ok)
    sent = ok["sentiment"].value_counts().reindex(SENTIMENTS, fill_value=0)
    sent_df = sent.rename_axis("sentiment").reset_index(name="count")
    sent_df["pct"] = (sent_df["count"] / max(n, 1) * 100).round(1)
    cat_df = ok.groupby(["category", "sentiment"]).size().reset_index(name="count")
    return {
        "total": len(enriched),
        "analysed": n,
        "needs_review": len(enriched) - n,
        "sentiment": sent_df,
        "category": cat_df,
        "high_urgency": int((ok["urgency"] == "high").sum()),
    }


# ---------- 05 REPORT (reduce chain + pandas numbers) ----------
def _category_block(sub: pd.DataFrame, counts: pd.Series, max_examples: int = 25) -> str:
    if counts.empty:
        return "None"
    blocks = []
    for cat in counts.index:
        rows = sub[sub["category"] == cat].head(max_examples)
        examples = "\n".join(f"- [{p}] {s}" for p, s in zip(rows["platform"], rows["summary"]))
        blocks.append(f"Category: {cat}\n{examples}")
    return "\n\n".join(blocks)


def build_report(enriched: pd.DataFrame, period: str) -> str:
    stats = compute_stats(enriched)
    ok = enriched[enriched["status"] == "ok"]
    neg = ok[ok["sentiment"] == "negative"]
    pos = ok[ok["sentiment"] == "positive"]
    top_complaints = neg["category"].value_counts().head(3)
    top_praises = pos["category"].value_counts().head(3)

    insights = build_report_chain().invoke({
        "period": period,
        "complaints": _category_block(neg, top_complaints),
        "praises": _category_block(pos, top_praises),
        "urgent_count": stats["high_urgency"],
    })

    pct = stats["sentiment"].set_index("sentiment")["pct"]
    lines = [
        f"WEEKLY FEEDBACK REPORT | {period}",
        f"Total reviews: {stats['total']}   Positive {pct['positive']}%   "
        f"Neutral {pct['neutral']}%   Negative {pct['negative']}%",
    ]
    if stats["needs_review"]:
        lines.append(f"Needs manual review (AI could not tag): {stats['needs_review']}")

    def section(title, counts, subset, items, unit):
        out = ["", title]
        lookup = {i.category: i for i in items}
        for n, (cat, cnt) in enumerate(counts.items(), 1):
            ins = lookup.get(cat)
            headline = ins.headline if ins else cat.replace("_", " ").title()
            platform = subset.loc[subset["category"] == cat, "platform"].value_counts().idxmax()
            out.append(f"{n}. {headline + ' ':.<30} {cnt} {unit} (mostly {platform})")
            if ins and ins.detail:
                out.append(f"   {ins.detail}")
        return out

    lines += section("TOP COMPLAINTS", top_complaints, neg, insights.top_complaints, "reviews")
    lines += section("TOP PRAISE", top_praises, pos, insights.top_praises, "mentions")
    lines += ["", f"URGENT: {stats['high_urgency']} reviews need a reply within 24 hours",
              "", "ACTION ITEMS"]
    lines += [f"{n}. {a}" for n, a in enumerate(insights.action_items[:3], 1)]
    return "\n".join(lines)


# ---------- 06 EXPORT ----------
def to_excel_csv(df: pd.DataFrame) -> bytes:
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    # utf-8-sig = Excel shows Tamil/Hindi/Telugu text correctly instead of ????
    return out.to_csv(index=False).encode("utf-8-sig")