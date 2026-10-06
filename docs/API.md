# ZEN AI API contract

The server (`server/`) and the web app (`web/`) both build against this file. Change it first, then change the
code. Routing rules are in `POLICY.md`; this file only describes the HTTP shapes.

All bodies are JSON. All timestamps are ISO 8601 UTC. Field names are `snake_case`. A field marked `?` may be absent.

## Conventions

**Offices:** `IT`, `FINANCE`, `ACADEMICS`, `HOSTEL`, `CAMPUS_SERVICES`, `EMPLOYEES`, `STUDENT_SUPPORT`, `HELPDESK`.

**Intents:** `info`, `fix_or_complaint`, `record_request`, `course_specific`, `vague`, `no_owner`, `safety`,
`out_of_scope`.

**Actions:** `answer`, `not_found`, `clarify`, `handoff`, `refuse`, `safety`.

**Channels:** `email`, `punctualiti`.

**Stages:** `routed`, `submitted`, `seen`, `in_progress`, `resolved`, `confirmed`, `reopened`, `cancelled`.

**Students** are demo students only (`student1`, `student2`). `student_id` is sent by the client and is not
authenticated; there is no real student data anywhere.

**Staff** sign in per office. `POST /api/staff/login` sets an `HttpOnly` session cookie; every `/api/staff/*` call
(except login) needs it and only sees its own office. Calls from the browser use `credentials: "include"`; the
server allows the origin in `WEB_ORIGIN`.

**Errors** always have this shape, with a matching HTTP status:

```json
{"error": {"code": "approval_token_invalid", "message": "This approval link was already used."}}
```

| status | code | when |
|---|---|---|
| 400 | `bad_request` | a required field is missing or malformed |
| 401 | `not_signed_in` | staff call without a session |
| 403 | `wrong_office` | staff tries to touch another office's case |
| 404 | `not_found` | unknown case or session |
| 409 | `invalid_stage` | the case is not in a stage that allows this call |
| 409 | `approval_token_invalid` | token wrong, already used or expired |
| 429 | `rate_limited` | the LLM provider's quota is used up |
| 502 | `provider_error` | the LLM, search or email provider failed |

## Student chat

### `POST /api/chat`

Request:

```json
{"session_id": "s_8f2a", "student_id": "student1", "message": "wifi nahi chal raha hostel mein aur fees refund kab milega"}
```

`session_id` is optional; the server creates one on the first message and returns it. Later messages with the same
id share the conversation (a `clarify` answer from the student continues the earlier topic).

Response:

```json
{
  "session_id": "s_8f2a",
  "turns": [
    {
      "topic_id": "t_1",
      "topic_text": "wifi nahi chal raha hostel mein",
      "office": "CAMPUS_SERVICES",
      "second_office": "IT",
      "intent": "fix_or_complaint",
      "confidence": 0.82,
      "action": "handoff",
      "handoff": {
        "case_id": "c_31b9",
        "office": "CAMPUS_SERVICES",
        "channel": "punctualiti",
        "ticket": {"category": "Network or wifi", "location": null, "description": "wifi not working in hostel room"},
        "missing_fields": ["location"],
        "approval_token": "tok_9d41..."
      }
    },
    {
      "topic_id": "t_2",
      "topic_text": "fees refund kab milega",
      "office": "FINANCE",
      "second_office": null,
      "intent": "info",
      "confidence": 0.91,
      "action": "answer",
      "answer": {
        "text": "Refunds are processed as described in the refund policy [1].",
        "citations": [
          {"n": 1, "title": "Fee refund policy", "source_url": "https://example.edu/refund", "last_updated": "2026-06-01",
           "snippet": "Refunds are processed within ...", "office": "FINANCE"}
        ]
      }
    }
  ]
}
```

One turn per topic, in the order the topic appears in the message. Fields of a turn:

| field | type | notes |
|---|---|---|
| `topic_id` | string | stable within the session |
| `topic_text` | string | the part of the message about this topic |
| `office` | office | the owning office; for `no_owner` it is `HELPDESK`; for `safety` it is `STUDENT_SUPPORT`; for `refuse` it may be `null` |
| `second_office` | office or null | a second team the topic also needs |
| `intent` | intent | |
| `confidence` | number 0 to 1 | |
| `action` | action | decides which optional object is present, below |
| `answer?` | object | present when `action` is `answer` (and for `safety`, see below) |
| `warning?` | `{text, citation?}` | present on an `answer` when documents disagree or the best one is old; `citation` has the citation shape |
| `clarify?` | `{question, candidate_offices: [office]}` | present when `action` is `clarify` |
| `handoff?` | object | present when `action` is `handoff`, `not_found` or `safety` |
| `refuse_reason?` | string | present when `action` is `refuse`; says what ZEN AI can help with |

**Citation:** `{n, title, source_url, last_updated, snippet, office}`, plus these optional fields: `page` (PDF page or
null), `heading` (heading path or null), `provenance` (`public`, `office-provided` or `team-written`), `team_compiled`
(true for `team-written`), `date_kind` (`updated`, or `fetched_on` when `last_updated` is the day the page was
fetched) and `label` (what to display, e.g. `Fee structure, p. 3`; it ends `[team-compiled]` for a team-written
document, which must never be presented as official). For a team-written document `source_url` is text saying what
it was compiled from, not a link. `n` is the number used in the answer text, as
`[1]`. Every `answer` has at least one citation. If the documents do not contain the answer the action is
`not_found`, never an answer without a citation.

**`answer`:** `{text, citations: [Citation]}`. For `action: "safety"` the `answer` holds the helpline text retrieved
from `kb/STUDENT_SUPPORT`, quoted with its citation; if none was retrieved, `answer` is absent and the handoff
tells the student to contact Student Support directly.

**`handoff`:**

| field | type | notes |
|---|---|---|
| `case_id` | string | the case this handoff created (stage `routed`) |
| `office` | office | receiving office. For a `course_specific` topic with no course document it is `ACADEMICS` and the draft is addressed to the course faculty |
| `channel` | `email` or `punctualiti` | |
| `draft?` | `{to, subject, body}` | for `email`. `to` is the office's demo mailbox |
| `ticket?` | `{category, location, description}` | for `punctualiti`. `category` comes from the office's category list |
| `missing_fields` | array of strings | required fields (from `config/offices.yaml`) the student has not given yet; may be empty |
| `approval_token` | string | one-time token for `POST /api/cases/{id}/approve` |

For `not_found`, the handoff carries the draft of the unanswered question. For `no_owner`, `office` is `HELPDESK`.

**Nothing is sent by `/api/chat`.** The language model drafts; only `POST /api/cases/{id}/approve` with a valid
one-time token sends an email.

## Student cases

### `GET /api/cases?student_id=student1`

```json
{"cases": [{"case_id": "c_31b9", "office": "CAMPUS_SERVICES", "channel": "punctualiti", "stage": "routed",
            "summary": "wifi not working in hostel room", "created_at": "...", "updated_at": "..."}]}
```

Newest first.

### `GET /api/cases/{case_id}`

```json
{
  "case_id": "c_31b9", "student_id": "student1", "office": "CAMPUS_SERVICES", "second_office": "IT",
  "channel": "punctualiti", "intent": "fix_or_complaint", "stage": "in_progress",
  "summary": "wifi not working in hostel room",
  "draft": null,
  "ticket": {"category": "Network or wifi", "location": "Block C, 214", "description": "..."},
  "ticket_no": "PN-20413",
  "missing_fields": [],
  "timeline": [
    {"at": "2026-10-06T09:12:03Z", "stage": "routed", "by": "zenai", "note": null},
    {"at": "2026-10-06T09:14:40Z", "stage": "submitted", "by": "student1", "note": "ticket PN-20413"},
    {"at": "2026-10-06T09:40:00Z", "stage": "in_progress", "by": "CAMPUS_SERVICES", "note": "engineer assigned"}
  ]
}
```

`by` is `zenai`, a student id, or an office. The draft or ticket is whichever the channel uses; the other is `null`.

### `POST /api/cases/{case_id}/approve`

Email cases only. Request: `{"approval_token": "tok_9d41...", "subject?": "...", "body?": "...", "fields?": {"room_no": "214"}}`.
`subject` and `body` are the student's edits to the draft; `fields` fills `missing_fields`. The server sends the
email to the office mailbox and moves the case `routed` to `submitted`. Response:

```json
{"case_id": "c_31b9", "stage": "submitted", "sent_to": "name+hostel@gmail.com", "sent_at": "..."}
```

The token works once. A wrong, used or expired token gives `409 approval_token_invalid` and nothing is sent. For a
`punctualiti` case use the ticket call below; `approve` on it gives `409 invalid_stage`.

### `POST /api/cases/{case_id}/cancel`

The student withdraws the case. Allowed in `routed` and `submitted`. Moves the case to `cancelled`. Response: `{"case_id", "stage"}`.

### `POST /api/cases/{case_id}/punctualiti-ticket`

Request: `{"ticket_no": "PN-20413"}`. For `punctualiti` cases: the student filed the ticket themselves and pastes
the number back. Moves `routed` to `submitted` and stores `ticket_no`. Response: `{"case_id", "stage", "ticket_no"}`.

### `POST /api/cases/{case_id}/confirm`

The student says it is fixed. Allowed in `resolved`. Moves the case to `confirmed`.

### `POST /api/cases/{case_id}/reopen`

The student says it is not fixed. Allowed in `resolved` and `confirmed`. Moves the case to `reopened`, which
appears in the office queue again. Optional body: `{"note": "still not working"}`.

## Staff

### `POST /api/staff/login`

Request: `{"office": "HOSTEL", "password": "..."}`. Sets the session cookie. Response: `{"office": "HOSTEL", "display_name": "Hostel Wardens"}`.
Wrong password: `401 not_signed_in`.

### `POST /api/staff/logout`

Clears the cookie. Response: `{"ok": true}`.

### `GET /api/staff/queue`

Cases for the signed-in office (stage `submitted`, `seen`, `in_progress`, `reopened`), oldest first.
`routed` cases are not shown: the student has not sent them yet.

```json
{"office": "HOSTEL", "cases": [{"case_id": "c_31b9", "student_id": "student1", "stage": "submitted",
                                "intent": "fix_or_complaint", "summary": "...", "age_minutes": 12}]}
```

### `GET /api/staff/cases/{case_id}`

Same shape as the student's case detail, plus `student_id`, the full `draft` or `ticket`, and `messages`: the email
thread (`[{"at", "from", "body"}]`, from the student, from staff replies).

### `POST /api/staff/cases/{case_id}/stage`

Request: `{"stage": "in_progress", "note?": "..."}`. Staff may set `seen`, `in_progress`, `resolved`.
Allowed moves: `submitted` to `seen`; `submitted`, `seen` or `reopened` to `in_progress`; `submitted`, `seen`,
`in_progress` or `reopened` to `resolved`. Anything else gives `409 invalid_stage`. The move is added to the timeline.

### `POST /api/staff/cases/{case_id}/reply`

Request: `{"body": "..."}`. Emails the student (the student's demo mailbox) and adds a timeline entry. Does not
change the stage.

### `POST /api/staff/cases/{case_id}/reassign`

Request: `{"to_office": "FINANCE", "reason": "fee data issue"}`. Moves the case to the other office's queue,
keeps its stage, and adds a timeline entry with the reason. Response: `{"case_id", "office"}`.

## Service

### `GET /api/health`

```json
{"status": "ok", "provider": "azure", "chat_model": "gpt-4.1-mini", "embed_model": "embed", "embed_dim": 1536,
 "retriever": "azure", "email_provider": "smtp", "kb_chunks": 412, "demo_mode": true}
```

`provider` is the active LLM provider (`gemini` or `azure`); `kb_chunks` is the number of indexed chunks.

### `GET /api/metrics`

Counts since the server started, for the demo dashboard:

```json
{"messages": 42, "turns": 57,
 "actions": {"answer": 30, "not_found": 4, "clarify": 6, "handoff": 14, "refuse": 2, "safety": 1},
 "cases_by_stage": {"routed": 3, "submitted": 5, "seen": 2, "in_progress": 2, "resolved": 1,
                    "confirmed": 1, "reopened": 0, "cancelled": 0},
 "emails_sent": 5, "median_chat_latency_ms": 2100}
```

## Case stages

| stage | meaning | how it is reached |
|---|---|---|
| `routed` | ZEN AI created the case and a draft; nothing has been sent | `POST /api/chat` |
| `submitted` | sent to the office (email approved) or Punctualiti ticket number recorded | `approve`, `punctualiti-ticket` |
| `seen` | the office has opened it | staff `stage` |
| `in_progress` | the office is working on it | staff `stage` |
| `resolved` | the office says it is done | staff `stage` |
| `confirmed` | the student agrees it is done | `confirm` |
| `reopened` | the student says it is not done; back in the queue | `reopen` |
| `cancelled` | the student withdrew it | `cancel` |

`confirmed` and `cancelled` are final. A `resolved` case with no student reply stays `resolved`.

## Rules the server must keep

- The language model never sends email. Only `approve` with a valid one-time token does.
- Every `answer` has citations taken from retrieved chunks. No retrieved evidence means `not_found`, not an answer.
- A `course_specific` topic is answered only from `kb/COURSE_SPECIFIC`; otherwise it is handed to the faculty
  through the `ACADEMICS` queue.
- `safety` turns are an immediate handoff to `STUDENT_SUPPORT`; the helpline text comes from retrieved documents only.
- Demo students only: no real student data is stored, sent or logged.
