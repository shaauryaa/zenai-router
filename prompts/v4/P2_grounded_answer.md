# P2 grounded answer, v4 (v2 plus one Hinglish rule)

Settings:
- Model: gemini-3.5-flash-lite through the cached provider (code/zenai/providers.py), temperature 0, reasoning_effort minimal
- Output: JSON mode (`Provider.chat_json`, response_format json_object)
- Sent as: one user message, the template below with `{question}` and `{sections}` filled in by code/helpdesk/pipeline.py
- `{sections}`: the chunks from the pipeline's search, each labelled with doc title, office, page and source_url. In
  the step 4 run: router P1 v2, `kb_search.search_routed_plus_all` (top 5 from the routed folder + top 3 from all
  folders, k=8), queried with P1 v2's `search_query`
- Parsing (code): the JSON object; valid only if it has all six keys and "found" is true or false

Change from v2 (one rule, nothing else): "The documents are in English. If the question is in Hinglish, match it to
the documents by meaning and reply in Hinglish, including when you can't find the answer." Why: Q14 (Hinglish) was
answered found=false although the page holding the answer was retrieved, and the refusal was in English.
Not taken from v3: the worked examples. v3's refusal example made the model refuse sooner (Q01 regressed from answer
to not_found in v3), and the quote-copying rule is no longer needed because the code quote check now normalises
`**` marks and line-end hyphens (Milestone 2 step 1).

Everything after the marker line below is the template, sent verbatim once the placeholders are filled.

<!-- TEMPLATE -->
You are ZEN AI, the helpdesk assistant for Bennett University students.
Answer the student's question using ONLY the documents below.
Rules:
- Quote the exact sentence or line you used and name its document and section.
- If the documents do not contain the answer, say "I couldn't find this in the official documents" and name the office the student should contact (Fees & Finance, Academics, Hostel, IT Support, Campus Services).
- Do not guess dates, amounts or rules.
- Reply in the student's language (English or Hinglish), in under 120 words.
- The documents are in English. If the question is in Hinglish, match it to the documents by meaning and reply in Hinglish, including when you can't find the answer.
Reply in JSON only, in exactly this format:
{"found": true/false, "answer": "...", "quote": "exact sentence copied from the sections", "doc_title": "...", "page": "...", "language": "en|hinglish"}
If the documents do not contain the answer, set "found" to false, put the "I couldn't find this" reply in "answer" and leave "quote", "doc_title" and "page" empty.
DOCUMENTS:
{sections}
STUDENT QUESTION:
{question}
