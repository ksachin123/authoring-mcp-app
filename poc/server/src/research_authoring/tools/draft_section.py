from research_authoring.db.types import Artefact


def draft_section(*, report_id: str, section_type: str, approved_artefacts: list[Artefact]) -> dict:
    draft_content = "\n\n".join(a.content for a in approved_artefacts)
    claim_ids = [claim_id for a in approved_artefacts for claim_id in a.claim_ids]
    return {"section_type": section_type, "draft_content": draft_content, "claim_ids": claim_ids}
