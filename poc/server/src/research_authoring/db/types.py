from dataclasses import dataclass
from typing import Optional


@dataclass
class Source:
    id: str
    type: str  # 'upload' | 'web_search' | 'connector:factset'
    retrieved_at: str
    retrieved_by: str
    context: str
    raw_content_ref: str
    external_url: Optional[str]


@dataclass
class Claim:
    id: str
    text: str
    source_id: str
    source_excerpt: str
    eval_status: str  # 'pending' | 'grounded' | 'unsupported' | 'conflicting'
    eval_score: Optional[float]
    eval_run_id: Optional[str]


@dataclass
class Artefact:
    id: str
    version: int
    type: str  # 'thesis_point' | 'data_extract' | 'comparison_table'
    content: str
    claim_ids: list[str]
    status: str  # 'draft' | 'pending_approval' | 'approved' | 'rejected'
    approved_by: Optional[str]
    approved_at: Optional[str]


@dataclass
class ReportSection:
    id: str
    version: int
    report_id: str
    section_type: str
    content: str
    claim_ids: list[str]
    status: str  # 'draft_in_chat' | 'committed' | 'approved'
    committed_by: Optional[str]
    committed_at: Optional[str]


@dataclass
class Report:
    id: str
    version: int
    template_id: str
    section_ids: list[str]
    status: str  # 'in_progress' | 'ready_for_export' | 'exported'
    exported_at: Optional[str]
    export_ref: Optional[str]


@dataclass
class AuditLogEntry:
    id: str
    actor: str
    action: str
    target_type: str
    target_id: str
    target_version: Optional[int]
    timestamp: str
    eval_run_id: Optional[str]
    diff: Optional[str]
