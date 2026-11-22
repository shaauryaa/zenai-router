# P2 grounded answer, v2 (JSON output)

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
