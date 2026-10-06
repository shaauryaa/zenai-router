# Retrieval: the knowledge base, ingestion and search

`kb/` holds the documents, `retrieval/` ingests and searches them. Answers (Prompt 9) are built only from what this
layer returns. Routing is untouched: the router and kNN still use Gemini embeddings; the knowledge base uses the Azure
`embed` deployment (1536 dimensions). The two kinds of vectors are never mixed.

## The INDEX.md contract

Every folder `kb/<FOLDER>/` (the eight in `config/offices.yaml`: IT, FINANCE, ACADEMICS, COURSE_SPECIFIC, HOSTEL,
CAMPUS_SERVICES, EMPLOYEES, STUDENT_SUPPORT) has an `INDEX.md` whose YAML front matter lists every file in it:

```yaml
---
documents:
- file: bennett-fee-structure.md      # path inside the folder; subfolders allowed
  title: Bennett University fee structure
  source_url: https://www.bennett.edu.in/admission/fee-structure/
  last_updated: '2026-10-06'
  date_kind: fetched_on                # optional: `updated` (default) or `fetched_on`
  public_or_permission: public         # public | office-provided | team-written
  collector: ZEN AI team
  course: CS101                        # optional (COURSE_SPECIFIC)
---
```

Rules, checked by `python -m retrieval.ingest` (any error stops the run before anything is written):

| rule | result |
|---|---|
| entry has no `title` | error |
| no `source_url` or no `last_updated` | error, except when `public_or_permission` is `office-provided` |
| `public_or_permission` missing or not one of the three values; `last_updated` not `YYYY-MM-DD` | error |
| file listed twice, or a path outside the folder | error |
| folder with files but no `INDEX.md` | error |
| listed file does not exist, unsupported type, unreadable, or a scanned PDF | warning, file skipped |
| file in the folder but not listed in `INDEX.md` | warning, file not indexed |
| folder under `kb/` that is not one of the eight (including `kb/HELPDESK`) | warning, skipped |
| no `collector`, or an unknown field | warning |

Nothing is ignored silently. Names starting with a dot (`.gitkeep`) and `INDEX.md` itself are not files to index.
A `.md` or `.txt` file may start with YAML front matter using the same fields; it fills only fields `INDEX.md` leaves
blank (INDEX.md wins when both say something).

`last_updated` is the date the document states. If the page states none, use the day it was fetched and set
`date_kind: fetched_on`; citations then show it as a fetch date, not an update date. Never guess a date.

### Adding a document

1. Put the file in the right folder: PDF, `.md`, `.txt` or `.html`. Only real, public or office-provided documents, or
   documents the team wrote. Never student records.
2. `python -m retrieval.index_stub kb/HOSTEL` writes a skeleton `INDEX.md` with an entry for every file found
   (it refuses to overwrite an existing `INDEX.md` unless `--force`; for an existing folder, copy the new entries into
   the file by hand). Fill in `title`, `source_url`, `last_updated`, `public_or_permission`, `collector`. A `.md` or
   `.txt` file with front matter pre-fills them. The blanks are deliberate: ingestion refuses an entry until they are
   filled in.
3. `python -m retrieval.ingest --dry-run` validates and chunks without calling any service. Read the warnings.
4. `python -m retrieval.ingest --backend both` (or `local` / `azure`).
5. `python -m retrieval.inspect "a question the document should answer" --department HOSTEL`.

### Team-compiled documents

A document with `public_or_permission: team-written` was written by the team from other sources, so it is not an
official document. Its `source_url` must say what it was compiled from (it is text, not a URL). Every citation of it
carries `team_compiled: true`, `provenance: "team-written"` and a label ending `[team-compiled]`, for example
`Hostel rules [team-compiled]`. The answer layer must show that label and must not describe the document as official.

## Ingestion

`python -m retrieval.ingest [--backend local|azure|both] [--rebuild] [--dry-run]`

1. Validate every `INDEX.md` (above).
2. Extract text: PDF with `pypdf`, one section per page, page numbers kept. A PDF averaging fewer than 30 characters
   per page is treated as scanned: a warning says OCR is needed, and nothing is indexed from it. HTML uses
   readability-style extraction (scripts, menus, footers dropped; main content kept; headings, lists and tables
   written as markdown; a "heading" that is really a sentence stays plain text; a label repeated under every
   programme, such as `Hostel Fees`, is nested under the programme heading before it). Markdown and text keep their headings.
3. Chunk: split by heading, then into chunks of about 400 tokens with about 60 tokens of overlap (tokens estimated as
   characters / 4; sizes in `config.yaml`). A table is never cut mid-row and its header rows are repeated when it
   continues in the next chunk. Empty or near-empty chunks are dropped.
4. Embed `title + heading path + text` with the Azure `embed` deployment through `zenai/providers.py` (cached, batched).
5. Write to the backend(s). Re-running replaces chunks with the same id and deletes chunks an edited file no longer
   produces. `--rebuild` first removes every chunk (documents only: the Azure index and its schema are never created,
   altered or deleted) and says what it will delete before it does.

Chunk ids are `<folder>-<10 hex of sha1(folder/file)>-<position>`, so the same file and position always give the same
id. Every chunk keeps: id, department (the folder), title, source_url, last_updated, page, heading path, content,
provenance, file, course.

The default backend is `RETRIEVER` in `.env` (`azure` or `local`), else `kb.retriever` in `config.yaml`.

## Two backends, one interface

| | local | azure |
|---|---|---|
| store | `.cache/kb_local/` (`chunks.jsonl`, `vectors.npy`) | the existing Azure AI Search index `zenai-kb` |
| keyword | BM25 (`rank_bm25`) | Azure BM25 (`search_text`) |
| vector | numpy cosine | Azure HNSW (`content_vector`, 1536-d) |
| needs | nothing once ingested | `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_ADMIN_KEY` in `.env` |
| page, heading, date, provenance | stored as fields | stored in the first line of `content` |

**Why the local backend exists.** It works with no network after ingestion (search falls back to keyword-only if the
query cannot be embedded), it needs no Azure quota or keys for development and tests, and it is a reference the Azure
results can be compared against. It is a derived cache: delete `.cache/kb_local/` and re-ingest to rebuild it.

**What Azure does not have.** The existing index has only `id`, `content`, `department`, `title`, `source_url` and
`content_vector`, and its schema is never changed. So `Chunk.to_azure_doc` writes a first line into `content`:
`ZENAI-META {"f":"refund.pdf","p":2,"h":"...","u":"2026-03-02","v":"public"}` (file, page, heading path, last_updated,
provenance, plus `k` and `c` when set). `Chunk.from_azure_doc` reads it back, so a search result from Azure has the
same page, heading, date and provenance as one from the local store. Never edit that line by hand.

## Search

```python
from retrieval.search import search
results = search("hostel curfew kab hai", departments=["HOSTEL"], k=8)
```

`departments` are folder names; `None` means all. Unknown names (and `HELPDESK`, which has no documents) raise
`ValueError`.

**Department filtering.** Each chunk's `department` is its folder. The filter is applied inside the backend before
ranking: Azure gets `search.in(department, 'HOSTEL,FINANCE', ',')` with `vectorFilterMode=preFilter`; the local backend
masks other departments before ranking. A HOSTEL-filtered search can never return a FINANCE chunk.

**Hybrid search.**
1. Keyword ranking (BM25) and vector ranking (cosine) each return up to 50 candidates. The keyword query also gets the
   long forms of abbreviations listed in `kb.search.aliases` (`cse` adds `computer science engineering`); the vector
   query is the text as typed.
2. Reciprocal rank fusion: a chunk at rank r in a list gains 1 / (60 + r); gains from the two lists are added. Ranks,
   not raw scores, are fused, because BM25 and cosine scores are not comparable.
3. The top k are returned. The local tokenizer lower-cases, drops dots inside abbreviations (`B.Tech` = `BTech`) and a
   trailing plural `s`.

**Scores**, all 0 to 1, the same on both backends (`SearchResult`):
- `score`: fused value divided by the largest possible fused value, so 1.0 means ranked first in every list. It orders
  results for this query; it says nothing about how good the best match is.
- `vector_score`: (1 + cosine similarity) / 2. The only absolute relevance signal; use it to decide whether anything
  retrieved is relevant enough to answer from. `None` if the query could not be embedded or the chunk was not a vector
  candidate.
- `keyword_score`: BM25 divided by the best BM25 candidate for the query.
- `mode`: `hybrid`, or `keyword-only` when the query could not be embedded.

## Citations

A result's `chunk.citation(n)` is the citation object of `docs/API.md`: `title`, `source_url`, `last_updated`, a
snippet, the owning `office`, plus `page`, `heading`, `provenance`, `team_compiled`, `date_kind` and `label`.
`chunk.citation_label()` is what to show: `Fee structure, p. 3` for a PDF page, the title alone for a page without page
numbers, and `... [team-compiled]` appended for a team-written document. Source URL, date and page always come from the
chunk, never from the model.

## Inspecting

```bash
python -m retrieval.inspect "hostel curfew kab hai" --department HOSTEL
python -m retrieval.inspect "BTech CSE fees kitni hai"
python -m retrieval.inspect "fees" --department FINANCE --department IT -k 5 --backend azure
```

Prints department, title, scores, page, heading path, citation label and a 200-character snippet for each chunk.

## Azure storage guard

Before uploading, the ingester reads the index's current storage and estimates the new size (text plus 4 bytes per
vector dimension per chunk). If the total would pass `kb.azure_search.storage_limit_mb` (45 MB, under the 50 MB
free-tier limit) it stops before uploading anything and says so. The estimate is a lower bound (the HNSW graph adds
some), and Azure's storage statistics can lag a few minutes behind the document count.
