# POLICY

# ZEN AI routing policy

**Status: team defaults, 6 Oct 2026, confirm.** Every rule below is a team default, not a confirmed university
rule. Change a rule here first; the router prompt, the evaluation labels, `config/offices.yaml` and
`docs/API.md` follow this file, never the other way round.

ZEN AI takes one student message (English or Hinglish), splits it into topics, and for each topic decides which
office owns it and what to do. It never answers from memory: an answer must come from retrieved documents and
carry citations, or ZEN AI says it cannot answer and hands the question to a person.

## 1. Vocabulary

**Offices** (who a case is handed to): `IT`, `FINANCE`, `ACADEMICS`, `HOSTEL`, `CAMPUS_SERVICES`, `EMPLOYEES`,
`STUDENT_SUPPORT`, `HELPDESK`.

**Knowledge folders** (where documents live, `kb/<FOLDER>/`): `IT`, `FINANCE`, `ACADEMICS`, `COURSE_SPECIFIC`,
`HOSTEL`, `CAMPUS_SERVICES`, `EMPLOYEES`, `STUDENT_SUPPORT`. There is no `kb/HELPDESK`: HELPDESK holds no
documents. `COURSE_SPECIFIC` has no office of its own; its handoff office is `ACADEMICS`.

**Intents** (what the student is asking for):

| intent | meaning |
| --- | --- |
| `info` | An official document could answer it for everyone (timings, rules, steps, fee structure). |
| `fix_or_complaint` | Something is broken or wrong and someone must act (a fault, a complaint, a request to change something). |
| `record_request` | Needs the student’s own records or a document issued to them (status of a refund, a certificate). |
| `course_specific` | About one course: its syllabus, one exam’s portion, one teacher’s policy or availability. |
| `vague` | Too unclear to route; ask one question. |
| `no_owner` | A real campus question that no knowledge folder clearly owns. Goes to HELPDESK. |
| `safety` | Someone reports ragging, harassment, a health emergency or a mental-health crisis. |
| `out_of_scope` | Not a campus question, or asks for another person’s records. |

**Actions** (what ZEN AI does with a topic): `answer`, `not_found`, `clarify`, `handoff`, `refuse`, `safety`.

v1 (frozen, tag `v1-routing-frozen`) used the domains IT, FEES, ACADEMICS, HOSTEL, CAMPUS_SERVICES,
OUT_OF_SCOPE and the actions answer, clarify, handoff, refuse. v1 keeps those names; v2 maps FEES to FINANCE.

## 2. How a message is decided

1. **Safety first.** If any part of the message is a report of ragging, harassment, a health emergency or a
mental-health crisis, that topic is `safety`.
2. **Split into topics**, one per distinct request, in the order written. Each topic becomes one turn.
3. **For each topic**, in this order: `out_of_scope`; `vague`; `course_specific`; the office rules in section 3;
otherwise `no_owner`.
4. **Choose the action** from intent and evidence:
    - `info` and the retrieved documents contain the answer: `answer`, with citations.
    - `info` and they do not: `not_found`, which becomes a handoff to the owning office (HELPDESK for `no_owner`).
    - `fix_or_complaint`, `record_request`, `no_owner`: `handoff` with a draft or ticket. These always need a person.
    - `vague`: `clarify` with one question and the candidate offices.
    - `safety`: `safety`, immediate handoff, see section 5.
    - `out_of_scope`: `refuse`, see section 6.
5. **A handoff is only a draft** until the student approves it. The model never sends anything.
6. Confidence thresholds for auto-routing are tuned on the dev set only and then frozen (see CLAUDE.md).

Each topic carries a first `office` and optionally a `second_office` (a message can need two teams).

## 3. Office rules (team defaults, 6 Oct 2026, confirm)

**Network and accounts**

- Wifi or network outage, or a slow connection, in a building or hostel room: `CAMPUS_SERVICES` (a Punctualiti
ticket); `second_office` IT.
- Wifi, ERP, Outlook or LMS account or login problems: `IT`.
- ERP showing wrong data (fees paid but shown due, courses missing): `IT` first; the data owner (`FINANCE` for
fees, `ACADEMICS` for courses) is the `second_office`.

**Course-specific** (folder `COURSE_SPECIFIC`, intent `course_specific`)

- One course’s syllabus, one exam’s portion, one teacher’s policy or availability.
- ZEN AI answers only if `kb/COURSE_SPECIFIC` actually contains that course’s information, with a citation.
- If it does not, the topic is handed to the faculty through the `ACADEMICS` queue, and the draft is addressed to
the course faculty.
- A course-specific question is never answered from general, non-course documents, even when a general document
sounds close.

**Everything else**

- Fees, refunds, scholarships, payment problems: `FINANCE`. Exception: the sports fee refund, see HOSTEL below.
- HR questions, appointment and employment policies (including professors of
practice): `EMPLOYEES`.
- Placements, clubs and fests, library: `ACADEMICS`.
- Mess, food outlets, maintenance, sports: `CAMPUS_SERVICES`.
- Laundry, curfew, outing, guests, room change, transport, and the sports fee refund (it is described in the hostel
  fees document): `HOSTEL`.

**No owner** (intent `no_owner`)

- A real campus question that none of the knowledge folders clearly owns (admission queries, lost and found,
unclear complaints, anything unusual): handoff to `HELPDESK`, the general queries desk. Never a refusal.

## 4. What each office handles

| office | what it is | answerable from documents | always needs a person |
| --- | --- | --- | --- |
| `IT` | The IT office. Owns ERP, college email (Outlook), LMS and network accounts. | How to connect to wifi, how to reset a password, where to log in, who to contact. | A locked or broken account, wrong ERP data, a university laptop fault. |
| `FINANCE` | The finance and accounts office. Owns fees, refunds and scholarships. | Fee structure, payment steps and deadlines, scholarship rules and how to apply. | A payment that failed or is not shown, a refund status, a student’s own dues. |
| `ACADEMICS` | The academics office. Owns exams, the calendar, attendance, registrar documents, placements, clubs and fests. Also the queue for faculty questions. | Academic calendar, exam and re-evaluation rules, attendance rules, how to get a document, placement and club information, library timings and rules. | A student’s own marks or attendance, a certificate being issued, a question only the course faculty can answer. |
| `HOSTEL` | The hostel wardens. Own hostel life and rules. | Curfew and in-time, outing and guest rules, laundry timings, transport routes and timings, the sports fee refund (from the hostel fees document), how to request a room change. | A room change decision, an outing or leave approval, a hostel complaint. |
| `CAMPUS_SERVICES` | The Punctualiti helpdesk. Owns maintenance and campus facilities. | Mess and outlet timings, sports facilities. | Any fault or maintenance request (electrical, plumbing, AC, network outage), lost property. |
| `EMPLOYEES` | HR. Owns staff and appointment matters. | HR policies, appointment and employment policies (including professors of practice). | An individual’s contract, payroll or leave, any case about a named staff member. |
| `STUDENT_SUPPORT` | The student support and wellbeing office. Owns anti-ragging, harassment and counselling support. | The anti-ragging and harassment policy, how to report, helpline numbers. | Any report of ragging, harassment, a health emergency or a mental-health crisis. |
| `HELPDESK` | The general queries desk. No documents of its own; receives what nobody else owns. | Nothing: it answers no questions by itself. | Everything it receives: `no_owner` topics and `not_found` handoffs that ZEN AI could not answer. |

## 5. Safety (team defaults, 6 Oct 2026, confirm)

- Intent `safety` covers someone **reporting** ragging, harassment, a health emergency or a mental-health crisis,
for themselves or for someone else.
- The action is an immediate handoff to `STUDENT_SUPPORT`. No clarifying question first, no waiting for
confidence, no advice from the model.
- The student sees the helpline text **retrieved from `kb/STUDENT_SUPPORT`**, shown as a quote with its citation.
ZEN AI never writes a phone number or advice from memory. If no helpline text is retrieved, the student is
told to contact the Student Support office directly and no number is shown.
- A **general question about the policy** (“what is the anti-ragging policy?”, “how do I report harassment?”) is
an ordinary `info` question, answered from `kb/STUDENT_SUPPORT` with citations.

## 6. Out of scope (team defaults, 6 Oct 2026, confirm)

- Only these are `out_of_scope`: things unrelated to campus (weather, homework help, general trivia) and anything
that asks for **another person’s records**.
- The refusal is polite and says what ZEN AI can help with (fees, exams, hostel, IT, campus services, and so on).
- A real campus question that nobody clearly owns is **not** out of scope: it is `no_owner` and goes to HELPDESK.

## 7. Answers and citations

- An `answer` states only what the retrieved chunks state, and every answer carries citations: title, source URL,
last-updated date and a snippet.
- If the chunks do not contain the answer, ZEN AI says it cannot answer and the topic becomes `not_found`, handed
to the office as a draft. It never fills the gap from memory.
- If the retrieved documents disagree, or the best document is old, the answer carries a `warning` with the
conflicting citation instead of picking silently.
- Demo students only. No real student data is stored or sent.