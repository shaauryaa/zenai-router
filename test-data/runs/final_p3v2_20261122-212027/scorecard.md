# Final test table, handoff-draft rows only, re-run with P3 v2 (final_p3v2_20261122-212027)

Base run `test-data/runs/final_20261122-201923/`. Rows: Q15, Q16, Q17, Q18, Q19. API calls 0, cache hits 14.

| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass/Fail |
|---|---|---|---|---|---|
| Q15 | wat cgpa do i need to get the 10% academic scholarshp in... | Edge | answer; key fact "8.0 and above in programmes offered under other Schools", quote verified | not_found; draft to finance@zenai-demo.example: "Query regarding SCSET 10% academic scholarship..." | Fail |
| Q16 | Can I share my wifi login with my roommate? And what time... | Edge | answer (topic 1 of 2); key fact "Once shared, a password is considered compromised and mus...", quote verified | not_found; draft to it@zenai-demo.example: "Inquiry regarding WiFi login sharing and campus..."; multi-topic note (1 more topic) | Fail |
| Q17 | What are the swimming pool timings on Sundays? | Edge | not_found; handoff draft | not_found; draft to services@zenai-demo.example: "Inquiry regarding Sunday swimming pool timings" | Pass |
| Q18 | Is there a college bus from campus to Pari Chowk metro af... | Edge | not_found; handoff draft | not_found; draft to services@zenai-demo.example: "Inquiry regarding college bus availability to P..." | Pass |
| Q19 | How much fee is still pending on my account for this seme... | Edge | handoff; handoff draft | handoff; draft to finance@zenai-demo.example: "Inquiry regarding pending semester fee" | Pass |
