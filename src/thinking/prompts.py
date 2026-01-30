"""Prompt templates for the Thinking Partner.

All prompts embed Recovery-first guardrails.
"""


def build_analysis_prompt(
    summary: str,
    memories: list[dict],
    question: str,
) -> str:
    """Build the full analysis template.

    This is used by NoLLMClient directly as the output,
    and by future LLM clients as the prompt input.
    """
    memory_section = ""
    if memories:
        memory_lines = []
        for i, mem in enumerate(memories, 1):
            memory_lines.append(
                f"  {i}. **{mem.get('title', 'Untitled')}**\n"
                f"     - Tags: {mem.get('tags', 'none')}\n"
                f"     - Match reason: {mem.get('match_reason', 'keyword overlap')}\n"
                f"     - Link: {mem.get('url', '')}"
            )
        memory_section = "\n".join(memory_lines)
    else:
        memory_section = "  (No related memories found)"

    return f"""## Analysis

### (A) Summary
{summary}

### (B) Related Memories
{memory_section}

### (C) Observations
- **Interpretation 1**: Based on the available context, one reading is that this connects to existing threads in your knowledge base.
- **Interpretation 2**: Alternatively, this may represent a new thread not yet captured in your system.
- **What is unknown**: {question} — this requires further context or data to answer definitively. Consider what specific information would clarify.

### (D) Next Steps (max 2)
1. Review the related memories above for overlapping themes.
2. If this is actionable, add it to the relevant category for tracking.

---
*Recovery-first: no rush. This is context, not a mandate.*
"""


def build_summary_prompt(text: str) -> str:
    """Build a short summary (5-10 lines max)."""
    # For NoLLMClient, we just truncate intelligently
    lines = text.strip().split("\n")
    kept = []
    char_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if char_count + len(stripped) > 800:
            break
        kept.append(stripped)
        char_count += len(stripped)
        if len(kept) >= 10:
            break

    if not kept:
        return text[:500]

    return "\n".join(kept)
