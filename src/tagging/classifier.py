"""Rule-based classifier using keyword matching."""
from src.tagging.taxonomy import TAXONOMY, CATEGORY_MAP


def classify(title: str, content: str = "") -> tuple[str, list[str]]:
    """Classify text into category and tags using keyword matching.

    Priority: Work subcategories > Personal > Other.
    Returns (category, tags_list).
    """
    text = f"{title} {content}".lower()
    scores: dict[str, int] = {}

    for _group, subcategories in TAXONOMY.items():
        for sub_name, sub_data in subcategories.items():
            score = 0
            for kw in sub_data["keywords"]:
                if kw.lower() in text:
                    score += 1
            if score > 0:
                scores[sub_name] = score

    if not scores:
        return ("Other", [])

    # Sort by score descending; Work categories get priority via taxonomy order
    work_subs = set(TAXONOMY["Work"].keys())
    personal_subs = set(TAXONOMY["Personal"].keys())

    best_work = max(
        ((name, sc) for name, sc in scores.items() if name in work_subs),
        key=lambda x: x[1],
        default=None,
    )
    best_personal = max(
        ((name, sc) for name, sc in scores.items() if name in personal_subs),
        key=lambda x: x[1],
        default=None,
    )

    # Collect all matched tags
    all_tags: list[str] = []
    for name in scores:
        group = "Work" if name in work_subs else "Personal"
        all_tags.extend(TAXONOMY[group][name]["tags"])

    # Dedupe tags preserving order
    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in all_tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    # Priority: Work > Personal
    if best_work:
        category = CATEGORY_MAP[best_work[0]]
    elif best_personal:
        category = CATEGORY_MAP[best_personal[0]]
    else:
        category = "Other"

    return (category, unique_tags)
