_STUB_RATIONALE = (
    "Stub evaluation: automated groundedness checking is not yet implemented "
    "in this POC. Claim is provisionally marked grounded pending manual "
    "review before approval."
)


def evaluate_claim_groundedness(*, claim_text: str, source_excerpt: str) -> dict:
    """Deterministic, non-AI groundedness stub (POC).

    Always returns a provisional 'grounded' verdict — this proves the
    eval-gate sequencing (every claim scored, results persisted, artefact
    transitioned) without making any real correctness judgment. A future
    real (LLM-as-judge) implementation will replace this with the same
    signature.
    """
    return {"status": "grounded", "score": 1.0, "rationale": _STUB_RATIONALE}
