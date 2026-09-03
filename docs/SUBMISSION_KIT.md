# BlindSpot submission control sheet

Track 02 — AI Risk Manager. Frozen thesis: verify the quality of fraud-policy declines whose outcomes are otherwise unseen.

## One-sentence positioning

BlindSpot helps a risk team check whether its fraud rules are blocking good payments—and tells the team when it needs more evidence.

Use [the plain-language guide](PLAIN_LANGUAGE_GUIDE.md) for explanations and [the revised pitch script](PITCH_SCRIPT.md) for recording. Technical claims below support questions from judges; they are not the opening pitch.

## Judge's walkthrough

Risk lead question: “Can I defend this decline policy, or do I need more evidence and a policy review?”

1. Blocked payments: 5,158 payments blocked by the test model, answers hidden. Being blocked does not prove fraud.
2. Check a sample: show how the review list was picked before seeing the answers. Turn on Show review results.
3. Can we trust the result?: compare finding good payments in a sample with estimating the whole group. They are different jobs; equal-chance reviews remain a strong baseline.
4. Try an example: day 1 → day 7 → day 30 on the same review list. Show why missing answers cannot be ignored. Explain the range and the next question for a human reviewer.
5. Download review summary. Keep the separate experiment answer key and simulation labels clear.

## Claim / proof register

| Claim | Actual evidence | Qualification |
|---|---|---|
| Runs on real transaction data | Full 590,540-row IEEE-CIS run and identical replay | Historical controlled censoring, not Razorpay traffic |
| Measurement is reproducible | Seven primary export hashes, original plan commitments, all 3,200 draws | Hashes are tamper evidence, not authentication |
| Weighted review queue enriches false-decline discovery | At 5% budget, discovery precision 80.20% vs 69.18% uniform; recall 5.82% vs 5.02% | Means across 200 draws; not classifier accuracy or population BP |
| Population estimation is evaluated honestly | BP RMSE 5.21 pp weighted vs 4.90 pp uniform | Do not claim weighted superiority; normal CIs remain approximate |
| Pending/wrong evidence is handled explicitly | 16,000 fixed stress trials, bounds and abstention rates; scenario controls | Conservative and often wide; simulated mechanisms and externally assumed error allowance |
| Review evidence can be ingested without oracle access | `blindspot.audit prepare` / `ingest`, batch validation and immutable receipt tests | Local CSV interface; no authenticated production connector |
| False-positive cost is transparent | Oracle false-decline amount 599,035.699 CU; selectable margin/review/exposure assumptions | Amount/margin at risk, not realized revenue recovered or INR |
| Defense-only | No transaction approval, rescue action or offensive capability | Human policy audit and escalation only |

## Required delivery checklist

The [official Razorpay page](https://razorpay.com/buildathon/) asks for a public repository, a five-minute pitch video and architecture, with held-out precision/recall and honest false-positive cost for Track 02. Exact portal fields and submission deadline still need verification; internal build dates are not official deadlines.

- [x] Frozen engineering spec and architecture explanation in repository.
- [x] Working three-screen local application.
- [x] Full-data proof, all-seed results and explicit limitations.
- [x] Local evidence ingestion and reliability stress demonstration.
- [x] Pitch script and screen-by-screen storyboard.
- [ ] Record and review the five-minute video; no finished video exists yet.
- [x] Include current source, tests and aggregate reports in the reviewed repository revision. GitHub sync authorized by Shikhar on 2026-09-03; raw/row-level data excluded.
- [ ] Obtain approval to make the existing private repository public.
- [x] Verify isolated source-copy installation with a fresh environment: all 40 tests, no-key demo, new CLI entrypoints and documented 50,000-row/3,200-trial synthetic benchmark pass. No licensed data or original artifacts were copied.
- [ ] Recheck the final published checkout/link after release; the isolated source-copy check is not a public-access check.
- [ ] Verify actual portal requirements, eligibility, deadline and submission receipt.
- [ ] Obtain approval for final submission.

## Publication boundary

Keep IEEE-CIS raw data, decline records, selected labels, sealed outcomes and complete generated bundles private and gitignored. Use a generated synthetic demo for unrestricted public access. Real-data aggregate findings may accompany it with source/license caveats; do not assume the data license permits redistributing row-level evidence. Public repo visibility changes and final form submission are not authorized yet.

## Feature freeze

No rescue scorer, new classifier tuning, LLM, agent framework or platform rewrite. Next work should finish judge access, video, clarity and failure recovery. Do not respond to these honest metric limitations by selecting favorable seeds or altering the held-out benchmark.

## Shikhar's rehearsal checks

Before recording, explain in your own words: why 94.3% classifier accuracy is misleading; why discovery precision differs from block precision; why verification probabilities matter; why uniform may beat weighting; why pending cases cannot be dropped; what the error allowance assumes; why 100% stress coverage is not accuracy; and what BlindSpot explicitly does not do. If any answer is unclear, practice it before presenting.
