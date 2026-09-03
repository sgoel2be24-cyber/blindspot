# Evidence reliability contract · v1 · 2026-09-03

Secondary sensitivity analysis. The original model, sampling policies, HT estimator and full-data benchmark remain unchanged. This extension is specified after seeing the primary benchmark; it is not a new untouched test set or evidence of production performance.

## Judge-visible workflow

1. Freeze a randomized review queue and record its commitment.
2. Accept a batch with exactly one record for every selected row: `resolved` with a binary evidence label, or `pending` with no label. Reject missing, duplicate, unselected or mismatched records.
3. Keep pending reviews in the denominator. Do not pretend completed reviews are a random subsample or silently multiply propensities by observed response rate.
4. Show a conservative block-precision range under arbitrary missingness and an explicit error assumption. Compare it to a user-chosen policy-audit threshold: evidence below target, above target, or insufficient. This never approves a payment.
5. Reveal offline truth separately to test whether the range covered it. Show all stress settings and draws, not just a successful scene.

## Assumptions

- The complete population has known, strictly positive independent Bernoulli selection probabilities. Fixed-size, adaptive and outcome-dependent selection are not covered.
- For a fixed as-of time, each row has a potential evidence status and label, fixed independently of the realized verification draw. Status may depend arbitrarily on truth. Workload-dependent delays or investigator decisions changed by queue composition violate this condition.
- At most `epsilon * N` rows in the **whole declined population** have resolved evidence labels that disagree with truth. Epsilon is an externally justified sensitivity assumption, not measured sample error, a confidence level, or an inferred production guarantee. If it cannot be bounded, set epsilon to one; the answer is uninformative.
- Confidence is pointwise for one fixed population, policy, budget, cutoff and error assumption. Repeated peeking or choosing a flattering scenario does not preserve simultaneous 95% coverage.

## Conservative envelope

For each row let `L_i = 1[resolved and evidence says fraud]` and `U_i = 1[pending or evidence says fraud]`. With perfect resolved labels, `L_i <= Y_i <= U_i`. With the error budget above, the population fraud share lies between `mean(L)-epsilon` and `mean(U)+epsilon`.

Only selected evidence is used to estimate endpoints:

```text
L_hat = sum_selected L_i / pi_i / N
U_hat = sum_selected U_i / pi_i / N
V = sum_all (1-pi_i) / pi_i
b = max_all_non_census max(1, (1-pi_i)/pi_i)
t = log(2/alpha)
r = (b*t/3 + sqrt(2*V*t + (b*t/3)^2)) / N
range = [clip(L_hat-r-epsilon, 0, 1), clip(U_hat+r+epsilon, 0, 1)]
```

The radius follows the bounded independent Bernstein tail inequality. For either endpoint coefficient `a_i` in `[0,1]`, the centered HT summand `(S_i/pi_i-1)*a_i` has variance at most `(1-pi_i)/pi_i` and absolute bound at most `max(1,(1-pi_i)/pi_i)`. Bernstein gives one-sided tail at most `exp(-x^2/(2*(V+b*x/3)))`. Inverting at `alpha/2` and union-bounding the two endpoint errors gives at least `1-alpha` coverage under the stated assumptions. No outcome-derived plug-in variance is used.

At a true census, radius is zero and pending labels still leave an identification range. If nothing is resolved, return `[0,1]` explicitly. This conservative envelope is deliberately wider than the original normal interval; it must not be called a more accurate point estimator. There is no single point estimate when outcomes remain unidentified.

Mathematical reference: [MIT 18.465, Lecture 6: Bernstein's inequality](https://ocw.mit.edu/courses/18-465-topics-in-statistics-statistical-learning-theory-spring-2007/50b28fb3952ea4067a53ac9949a49a34_lecture06.pdf) gives the bounded-sum tail and its inverted radius. Its application to the two HT endpoint totals and the label-error envelope above is this project's derivation, not an endorsement or a new named estimator. Independent nonidentical summands follow by multiplying the individual moment-generating-function bounds and summing their variances.

## Local evidence import

`python -m blindspot.audit prepare` consumes only the label-free decline pool, commits a queue and writes a pending evidence template. `python -m blindspot.audit ingest` validates a separately supplied review CSV and writes an immutable aggregate receipt. It does not read source outcomes or sealed truth. A CSV interface is implemented; external evidence authentication, analyst tools, dispute feeds, access control and workload-dependent evidence collection are not integrated. No simulated label should be represented as a real analyst decision.

The naive completed-review comparison is `sum_resolved(evidence/pi) / sum_resolved(1/pi)`. It has neither a missingness correction nor a confidence guarantee. Its error is exposed only in offline tests.

## Fixed stress matrix

Use the original five primary budgets (0.25%, 0.5%, 1%, 2%, 5%), both original policies, 200 consecutive draw seeds 1729–1928, and fixed evidence seed 90203. No retraining. Simulated potential evidence is generated once per scenario before the verification draws:

- Immediate perfect evidence; epsilon 0.
- Outcome-independent 30% missing evidence; epsilon 0.
- Outcome-dependent missingness: 60% of fraudulent versus 10% of legitimate cases pending; epsilon 0.
- Delayed evidence: fraud waits 14 days, legitimate evidence 2 days; evaluate fixed cutoffs day 1, day 7, day 30; epsilon 0.
- Exactly `floor(0.05*N)` randomly located labels flipped; epsilon 5%.
- Same corrupted labels with an incorrectly asserted epsilon 0, visibly labeled an assumption-violation test.

Eight scenarios × five budgets × two policies × 200 draws = 16,000 retained stress trials. Resolution, pending fraction, conservative width/coverage, naive error and unsupported-threshold claims are reported together. Runtime can be optimized without changing these settings. Hash and bind each stress bundle to the original run and source exports; refuse overwrites.

## Acceptance gates

- No evaluator/oracle import added to selection or dashboard code.
- Evidence packet rejects commitment tampering, duplicates, unknown/unselected IDs, missing records, invalid statuses and labels on pending records.
- Empty/no-evidence range is full; census with pending rows is not falsely exact; complete census is exact; epsilon and missingness cannot narrow a fixed draw's bounds.
- Exact enumeration of all Bernoulli draws on tiny fixed populations meets the nominal coverage lower bound under valid assumptions.
- Same evidence, row order canonicalization and seed replay identically.
- Dashboard fails closed on mismatched source run or corrupted reliability exports; offline coverage/truth requires the existing benchmark reveal.
- Existing no-key synthetic tests remain green. No new service, LLM, database, payment action or public data distribution.
