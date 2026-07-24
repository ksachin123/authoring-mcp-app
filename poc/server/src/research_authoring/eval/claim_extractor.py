import re


def extract_claims(*, generated_text: str, source_excerpt: str) -> list[dict]:
    """Deterministic, non-AI claim decomposition (POC stub).

    Splits on sentence-ending punctuation and maps every resulting claim to
    the full source excerpt, since identifying the specific supporting
    substring per claim is deferred to a future real (LLM-based) extractor.
    """
    segments = re.split(r"(?<=[.!?])\s+", generated_text.strip())
    return [
        {"text": segment.strip(), "source_excerpt": source_excerpt}
        for segment in segments
        if segment.strip()
    ]
