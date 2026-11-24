# Quote check v2: false-accept check (quote_check_v2_20261124-145802)

18 verified quotes from `test-data/runs/final_20261122-201923`, `test-data/runs/fresh_20261122-214926`; each mutated and checked against the same row's retrieved sections with `pipeline.verify_quote` (v2). No API call. Mutation definitions: docstring of `code/helpdesk/quote_mutations.py`. A mutated quote that is accepted is a false accept.

| Mutation | Kind | Tried | n/a | Wrongly accepted (exact) | Wrongly accepted (near) | Rows |
|---|---|---|---|---|---|---|
| original (not a mutation) | baseline accepted (should be all) | 18 | 0 | 18 | 0 | Q01, Q02, Q03, Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q14, F03, F04, F05, F08 |
| number | requested | 8 | 10 | 0 | 2 | Q12, F05 |
| word | requested | 18 | 0 | 0 | 9 | Q01, Q02, Q03, Q04, Q10, Q11, Q12, Q14, F04 |
| other_doc | requested | 18 | 0 | 0 | 0 | - |
| number_in_section | stress | 8 | 10 | 0 | 8 | Q01, Q03, Q04, Q12, Q14, F03, F05, F08 |
| negation | stress | 7 | 11 | 2 | 5 | Q01, Q02, Q04, Q09, Q10, Q13, Q14 |

Requested mutations: 11 of 44 wrongly accepted.

## Every mutation

| Row | Mutation | Accepted | Rule | Mutated quote |
|---|---|---|---|---|
| Q01 | number | False | - | For Withdrawal/Cancellation requests received after 40 September 2026 and up to 31 October 2026, the refund shall be processed after deducti... |
| Q01 | word | True | near | For Withdrawal/Cancellation requests received after 30 September 2026 and up to 31 October 2026, the refund giraffe be processed after deduc... |
| Q01 | other_doc | False | - | The continuation of the Admission Scholarship in subsequent academic years shall be subject to the student achieving the minimum CGPA requir... |
| Q01 | number_in_section | True | near | For Withdrawal/Cancellation requests received after 2 September 2026 and up to 31 October 2026, the refund shall be processed after deductio... |
| Q01 | negation | True | near | For Withdrawal/Cancellation requests received after 30 September 2026 and up to 31 October 2026, the refund shall be processed after deducti... |
| Q02 | number | n/a | - |  |
| Q02 | word | True | near | The continuation of the Admission Scholarship in subsequent academic years shall be subject to the student achieving the minimum CGPA requir... |
| Q02 | other_doc | False | - | Students who fail to clear their dues by the prescribed deadline may be permitted to register during the Late Registration Window (25 July 2... |
| Q02 | number_in_section | n/a | - |  |
| Q02 | negation | True | near | The continuation of the Admission Scholarship in subsequent academic years shall be subject to the student achieving the minimum CGPA requir... |
| Q03 | number | False | - | Students who fail to clear their dues by the prescribed deadline may be permitted to register during the Late Registration Window (35 July 2... |
| Q03 | word | True | near | Students who fail to clear their dues by the prescribed deadline may be permitted to register during the giraffe Registration Window (25 Jul... |
| Q03 | other_doc | False | - | No out pass is required to move out of campus on working days from 05:00 PM to 07:00 PM and on Sunday/Holidays from 09:00 AM to 07:00 PM. |
| Q03 | number_in_section | True | near | Students who fail to clear their dues by the prescribed deadline may be permitted to register during the Late Registration Window (1 July 20... |
| Q03 | negation | n/a | - |  |
| Q04 | number | False | - | No out pass is required to move out of campus on working days from 15:00 PM to 07:00 PM and on Sunday/Holidays from 09:00 AM to 07:00 PM. |
| Q04 | word | True | near | No out pass is required to move out of campus on giraffe days from 05:00 PM to 07:00 PM and on Sunday/Holidays from 09:00 AM to 07:00 PM. |
| Q04 | other_doc | False | - | Hostel shall have deemed to be vacated only after taking clearance from Warden/Hostel In-charge. |
| Q04 | number_in_section | True | near | No out pass is required to move out of campus on working days from 07:00 PM to 07:00 PM and on Sunday/Holidays from 09:00 AM to 07:00 PM. |
| Q04 | negation | True | exact | out pass is required to move out of campus on working days from 05:00 PM to 07:00 PM and on Sunday/Holidays from 09:00 AM to 07:00 PM. |
| Q05 | number | n/a | - |  |
| Q05 | word | False | - | Hostel shall have deemed to be vacated only after giraffe clearance from Warden/Hostel In-charge. |
| Q05 | other_doc | False | - | Reveal a password to any other individual, even those claiming to be an IT support technician (over the phone or in-person). |
| Q05 | number_in_section | n/a | - |  |
| Q05 | negation | n/a | - |  |
| Q06 | number | n/a | - |  |
| Q06 | word | False | - | Reveal a password to any other individual, even those giraffe to be an IT support technician (over the phone or in-person). |
| Q06 | other_doc | False | - | A student must have a minimum attendance of |
| Q06 | number_in_section | n/a | - |  |
| Q06 | negation | n/a | - |  |
| Q07 | number | n/a | - |  |
| Q07 | word | False | - | All guests will be required to register at the reception giraffe and provide a valid photo ID. |
| Q07 | other_doc | False | - | A student must have a minimum attendance of |
| Q07 | number_in_section | n/a | - |  |
| Q07 | negation | n/a | - |  |
| Q08 | number | n/a | - |  |
| Q08 | word | False | - | A student must have a giraffe attendance of |
| Q08 | other_doc | False | - | Students shall be provided with the telephone numbers of the Anti-Ragging Helpline and all the important functionaries in the University inc... |
| Q08 | number_in_section | n/a | - |  |
| Q08 | negation | n/a | - |  |
| Q09 | number | n/a | - |  |
| Q09 | word | False | - | No makeup examination is allowed for end giraffe examination and policy for same is laid down separately. |
| Q09 | other_doc | False | - | Students shall be provided with the telephone numbers of the Anti-Ragging Helpline and all the important functionaries in the University inc... |
| Q09 | number_in_section | n/a | - |  |
| Q09 | negation | True | exact | makeup examination is allowed for end semester examination and policy for same is laid down separately. |
| Q10 | number | n/a | - |  |
| Q10 | word | True | near | Students shall be provided with the telephone numbers of the Anti-Ragging Helpline and all the important functionaries in the University inc... |
| Q10 | other_doc | False | - | The employee/student may use the complaint mechanism and file a written complaint to the Internal Committee. |
| Q10 | number_in_section | n/a | - |  |
| Q10 | negation | True | near | Students shall be provided with the telephone numbers of the Anti-Ragging Helpline and all the important functionaries in the University inc... |
| Q11 | number | n/a | - |  |
| Q11 | word | True | near | The employee/student may use the complaint giraffe and file a written complaint to the Internal Committee. |
| Q11 | other_doc | False | - | 1. Login to the helpdesk at https: //helpdesk.bennett.edu.in/open.php. 2. Opt for Registry Helpdesk under the department section. 3. Select ... |
| Q11 | number_in_section | n/a | - |  |
| Q11 | negation | n/a | - |  |
| Q12 | number | True | near | 2. Login to the helpdesk at https: //helpdesk.bennett.edu.in/open.php. 2. Opt for Registry Helpdesk under the department section. 3. Select ... |
| Q12 | word | True | near | 1. Login to the helpdesk at https: //helpdesk.bennett.edu.in/open.php. 2. Opt for giraffe Helpdesk under the department section. 3. Select t... |
| Q12 | other_doc | False | - | Visitors including parents are not allowed to go inside the hostel rooms. |
| Q12 | number_in_section | True | near | 25.09.2024. Login to the helpdesk at https: //helpdesk.bennett.edu.in/open.php. 2. Opt for Registry Helpdesk under the department section. 3... |
| Q12 | negation | n/a | - |  |
| Q13 | number | n/a | - |  |
| Q13 | word | False | - | Visitors including parents are not giraffe to go inside the hostel rooms. |
| Q13 | other_doc | False | - | Refund shall be processed within 15 working days of receipt of the complete application and completion of the no-dues process, |
| Q13 | number_in_section | n/a | - |  |
| Q13 | negation | True | near | Visitors including parents are allowed to go inside the hostel rooms. |
| Q14 | number | False | - | Refund shall be processed within 25 working days of receipt of the complete application and completion of the no-dues process, |
| Q14 | word | True | near | Refund shall be processed within 15 working days of giraffe of the complete application and completion of the no-dues process, |
| Q14 | other_doc | False | - | Dinner 8:00 pm to 10:00 pm |
| Q14 | number_in_section | True | near | Refund shall be processed within 1000 working days of receipt of the complete application and completion of the no-dues process, |
| Q14 | negation | True | near | Refund shall be processed within 15 working days of receipt of the complete application and completion of the -dues process, |
| F03 | number | False | - | Dinner 9:00 pm to 10:00 pm |
| F03 | word | False | - | giraffe 8:00 pm to 10:00 pm |
| F03 | other_doc | False | - | Minimum Password length shall be set to 8 characters. |
| F03 | number_in_section | True | near | Dinner 7:00 pm to 10:00 pm |
| F03 | negation | n/a | - |  |
| F04 | number | n/a | - |  |
| F04 | word | True | near | Only the following items are permitted in the hostel rooms: Computer/Laptop, giraffe Charger, Personal musical instruments, Hair dryers and ... |
| F04 | other_doc | False | - | Minimum Password length shall be set to 8 characters. |
| F04 | number_in_section | n/a | - |  |
| F04 | negation | n/a | - |  |
| F05 | number | True | near | Minimum Password length shall be set to 9 characters. |
| F05 | word | False | - | Minimum Password length giraffe be set to 8 characters. |
| F05 | other_doc | False | - | Triple Sharing / ₹ 1,70,000 PA |
| F05 | number_in_section | True | near | Minimum Password length shall be set to 1 characters. |
| F05 | negation | n/a | - |  |
| F08 | number | False | - | Triple Sharing / ₹ 2,70,000 PA |
| F08 | word | False | - | Triple giraffe / ₹ 1,70,000 PA |
| F08 | other_doc | False | - | For Withdrawal/Cancellation requests received after 30 September 2026 and up to 31 October 2026, the refund shall be processed after deducti... |
| F08 | number_in_section | True | near | Triple Sharing / ₹ 1 PA |
| F08 | negation | n/a | - |  |
