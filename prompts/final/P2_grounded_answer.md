# P2 grounded answer, FINAL = v2 (copy of prompts/v2/P2_grounded_answer.md)

P2 v5 (prompts/v5/P2_grounded_answer.md) was tried on 24 Nov and rejected (run test-data/runs/final_20261124-173053); FINAL stays v2 (from 24 Nov with search routed5_all3_prog and two topics).

Chosen after Milestone 2 step 4: with router P1 v2 and the 5+3 search, P2 v2 scored 22/24 final actions (run test-data/runs/step3_P1v2_search8_P2v2_20261122-192957) and P2 v4 21/24 (run test-data/runs/step4_P1v2_search8_P2v4_20261122-193227). In the final pipeline `{sections}` holds the 8 chunks from `kb_search.search_routed_plus_all(P1 v2 search_query, P1 v2 domain)`. No further tuning on test-data/questions.csv.

Original v2 file below.

Settings:
- Model: gemini-3.5-flash-lite through the cached provider (code/zenai/providers.py), temperature 0, reasoning_effort minimal
- Output: JSON mode (`Provider.chat_json`, response_format json_object)
- Sent as: one user message, the template below with `{question}` and `{sections}` filled in by code/helpdesk/pipeline.py
- `{sections}`: the 5 chunks from `kb_search.search_for_route(question, router domain, k=5)`, each labelled with doc title, office, page and source_url
- Parsing (code): the JSON object; valid only if it has all six keys and "found" is true or false
- Change from v1: same rules, but the reply is one JSON object, so found / quote / document / page / language are fields
  instead of free text that code has to guess from. Why: v1's plain text has to be parsed by searching for a fixed
  sentence and the first pair of double quotes, which breaks whenever the model words the refusal differently or
  quotes something else first.

Everything after the marker line below is the template, sent verbatim once the placeholders are filled.

<!-- TEMPLATE -->
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the student's language (English or Hinglish), in under 120 words.
Reply in JSON only, in exactly this format:
{"found": true/false, "answer": "...", "quote": "exact sentence copied from the sections", "doc_title": "...", "page": "...", "language": "en|hinglish"}
If the documents do not contain the answer, set "found" to false, put the "I couldn't find this" reply in "answer" and leave "quote", "doc_title" and "page" empty.
DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
