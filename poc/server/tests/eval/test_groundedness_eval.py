from research_authoring.eval.groundedness_eval import evaluate_claim_groundedness


def test_always_returns_a_provisional_grounded_verdict():
    result = evaluate_claim_groundedness(
        claim_text="Consensus FY26 EPS is $7.42", source_excerpt="FY26 EPS estimate: 7.42"
    )
    assert result["status"] == "grounded"
    assert result["score"] == 1.0
    assert "not yet implemented" in result["rationale"].lower() or "stub" in result["rationale"].lower()


def test_returns_the_same_stub_shape_regardless_of_input():
    result_a = evaluate_claim_groundedness(claim_text="Anything", source_excerpt="Unrelated excerpt")
    result_b = evaluate_claim_groundedness(claim_text="Something else entirely", source_excerpt="")
    assert result_a == result_b
