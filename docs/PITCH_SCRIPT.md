# Five-minute pitch · plain-language version

Target: roughly five minutes including interaction pauses. Rehearse and time before recording. This is a script, not a completed video. Use the full local IEEE-CIS bundle privately; do not publish row-level competition records without confirming permission. A public recording can use synthetic queue identifiers and clearly label real-data aggregate result slides separately.

## 0:00–0:40 · The problem

**Screen: 1. Blocked payments. Both answer switches off.**

“Imagine a genuine customer trying to pay. The fraud system says no.

Blocking fraud is important. But blocking good payments can also hurt a business. How does the risk team find out whether its blocking rule is making too many mistakes?

That is what BlindSpot checks. It reviews a sample of blocked payments, estimates how many good payments may have been blocked, and says clearly when it does not have enough information. It does not approve payments or replace the fraud model.”

## 0:40–1:20 · What we built

“Here are the payments blocked by our test model. We know the model said no. That alone does not tell us whether it was right.

We tested this using about 590,000 historical transactions from IEEE-CIS. The model learned from older payments and was tested on later ones. We hid the answers for blocked payments from the code choosing reviews.

The blocking is simulated. This is not connected to Razorpay's live payments. We keep the historical answers separate so we can later check whether our estimates were any good.”

## 1:20–2:00 · Check a sample

**Screen: 2. Check a sample. Turn on Show review results.**

“Checking every blocked payment may take too much time. So we pick a sample. Every payment has a chance of being picked, and we fix that list before looking at the answers.

We compare two ways of choosing: give every payment an equal chance, or check more payments near the model's cutoff.

When some payments are picked more often, simply counting the answers can mislead us. BlindSpot accounts for those different chances before estimating the whole group.”

## 2:00–2:35 · What the test actually showed

**Screen: 3. Can we trust the result? Turn on Show experiment answer key.**

“The focused reviews found a higher share of good payments in the sample. But they did not give a better estimate of the whole group than equal-chance reviews.

We show both results. Finding more good payments during review and accurately measuring all blocked payments are different jobs.

We also show a range around each estimate. If the range is wide, we should be cautious. More test runs do not magically make a weak sample reliable.”

## 2:35–3:50 · The important demonstration

**Choose Equal chance for every payment and 5%. Under Try an example, choose Late answers: day 1, day 7, then day 30. The display seed remains 1729.**

“Now imagine some review answers arrive late. This example is simulated: fraud answers arrive later than the others.

We asked for 244 reviews. On day one, none have arrived. BlindSpot says we do not know enough.

On day seven, 165 answers have arrived and 79 are still missing. The answers received so far show no fraud. If we ignore the missing ones, we could wrongly conclude that none of the blocked payments were fraud.

But the separate answer key says about 31% were fraud. The late answers matter.

BlindSpot does not throw them away. It keeps them marked as missing and widens the range. Even when every answer arrives on day thirty, a sample still leaves uncertainty.

Against the example target shown here, the result tells a person to review the blocking rule. It does not tell the system to approve a payment.”

## 3:50–4:30 · A result someone can check

**Click Download review summary. Briefly show the simple architecture or the existing local review-file workflow.**

“The downloadable summary records what was checked, what is missing, the assumptions and the result. A local file-based workflow also accepts review answers and checks that they belong to the original review list.

We tested missing, late and wrong answers in 16,000 simulated trials. Sometimes the useful answer is simply: we still do not know enough.

We have not connected a live review service. Before real use, we would need to check where the answers come from and how often those answers are wrong.”

## 4:30–5:00 · Why it matters

“The aim is simple: help a risk team spot when its fraud rules may be blocking good payments, without pretending missing answers are known.

That gives the team a reason to investigate, a way to plan further reviews, and a record it can check. We show possible costs with clear assumptions; we do not claim money has already been saved.

BlindSpot checks the blocked payments—and tells us when we need to know more.”

## Recording checks

- Do not replace fixed seed 1729 with a prettier run.
- Keep simulation and offline-oracle disclosures visible.
- Do not call 80.2% discovery precision “fraud detection accuracy.”
- Do not claim the conservative envelope is narrower than the original normal CI.
- Explain CU as dataset currency units, never INR.
- Show at least one real click, pending state and audit receipt.
- Record locally first; review permissions and data exposure before uploading.
