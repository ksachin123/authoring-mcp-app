# Skill: Draft an Equity Research Report Section

**When to use:** The analyst asks to research a company, build an investment thesis,
or draft/refine a section of a sell-side equity research report — including when they
attach a document (e.g. a 10-Q, earnings release, or PDF) and ask you to analyze it or
draft a thesis point from it. Attaching a file does not change this: any attached
document is source material for this Skill's pipeline, not something to read and
summarize on your own.

**Do not** answer directly from an attached file, connector output, or web search using
your own reading/analysis, even though you are capable of it and it would be faster.
This Skill exists specifically to route that content through governed ingestion,
citation, and an eval/approval gate before it becomes analysis the analyst sees. Skipping
the tools below and answering natively defeats the entire point of this app — every
thesis point, data extract, or comparison table must originate from `synthesize_artefact_tool`
and pass through `run_eval_tool`, not from your own summary of the raw material.

**Steps to follow, in order:**
1. If the analyst hasn't supplied source material yet, ask whether to use an uploaded
   document, a ChatGPT-native connector (e.g. FactSet), or web search.
   - For an uploaded document: call `ingest_document_tool`.
   - For a connector (e.g. FactSet): first call the connector's own tool(s) to fetch
     the data, then IMMEDIATELY call `ingest_connector_result_tool` with
     `connector_name` set to that connector (e.g. `"factset"`) and the connector's
     output as `raw_content_ref`/`context`. Never treat a connector's raw output as
     part of the governed report until it has been ingested this way.
   - For web search: use your own web search capability to find and read the
     material, then IMMEDIATELY call `ingest_web_result_tool` with the page's URL
     as `external_url` and its relevant content as `raw_content_ref`/`context`.
     Never treat a web search result as part of the governed report until it has
     been ingested this way.
2. Call `synthesize_artefact_tool` to turn source material into a cited artefact
   (`thesis_point`, `data_extract`, or `comparison_table`) — never draft analysis
   directly into chat without going through this tool first.
3. Call `run_eval_tool` on the resulting artefact before presenting it to the analyst.
   (Note: this POC's eval is a provisional stub that always marks claims "grounded" —
   treat its output as a placeholder, not a real correctness guarantee, and rely on
   the analyst's own review in the next step.)
4. Show the analyst the artefact and its claims for review. Only call
   `approve_artefact_tool` after the analyst has explicitly approved or rejected it —
   never assume approval.
5. Once artefacts relevant to a section are approved, call `draft_section_tool` to
   assemble a starting draft, then refine the prose conversationally with the analyst
   as needed.
6. When the analyst is satisfied with a section's wording, call `commit_section_tool` —
   do not consider a section part of the report until this has been called.
7. Once all intended sections are committed, call `assemble_report_tool` with the
   desired section order, then `export_report_tool` to produce the Markdown deliverable.

**Never:** call `approve_artefact_tool` or `assemble_report_tool` without an explicit
analyst instruction to do so — these are approval gates, not automatic steps.
