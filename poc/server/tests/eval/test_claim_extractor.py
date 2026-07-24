from research_authoring.eval.claim_extractor import extract_claims


def test_splits_multi_sentence_text_into_one_claim_per_sentence():
    claims = extract_claims(
        generated_text="Revenue grew 12% YoY. Gross margin was 41%.",
        source_excerpt="Revenue increased 12% year-over-year on a gross margin of 41%.",
    )

    assert claims == [
        {
            "text": "Revenue grew 12% YoY.",
            "source_excerpt": "Revenue increased 12% year-over-year on a gross margin of 41%.",
        },
        {
            "text": "Gross margin was 41%.",
            "source_excerpt": "Revenue increased 12% year-over-year on a gross margin of 41%.",
        },
    ]


def test_single_sentence_text_produces_a_single_claim():
    claims = extract_claims(
        generated_text="Consensus FY26 EPS is $7.42.",
        source_excerpt="FY26 EPS estimate: 7.42",
    )

    assert claims == [{"text": "Consensus FY26 EPS is $7.42.", "source_excerpt": "FY26 EPS estimate: 7.42"}]


def test_ignores_blank_segments_from_trailing_punctuation_or_whitespace():
    claims = extract_claims(generated_text="One claim only.   ", source_excerpt="src")
    assert claims == [{"text": "One claim only.", "source_excerpt": "src"}]
