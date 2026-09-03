# BlindSpot contributor contract

These instructions apply to the entire `blindspot/` repository.

## Frozen product

- Track 02 — AI Risk Manager and the BlindSpot thesis are frozen.
- Build a false-positive verifier, not a fraud-decision or rescue product.
- Do not add RiskTwin, a rescue scorer, policy generation, autonomous actions, an agent framework, RAG, a vector database, or an LLM dependency.
- Prefer the smallest deterministic implementation that satisfies `docs/ENGINEERING_SPEC_V1.md`.
- Use simple language in the app, pitch and user explanations: problem, review, result, uncertainty and next human step. Keep technical details in expandable sections or linked documents. Never simplify away material assumptions, simulation labels or limitations. See `docs/PLAIN_LANGUAGE_GUIDE.md`.

## Statistical boundary

- `isFraud`/`is_fraud` is an offline oracle outcome. Keep it in trusted experiment inputs, sealed truth, evaluator code and tests. The sole UI exception is evaluator-exported observations for already-committed selected rows, displayed only after sample reveal; never full-population row-level truth.
- Code under `src/blindspot/product/` must never import `blindspot.evaluation` or `blindspot.experiment`.
- Product artifacts must contain no outcome alias or declared incumbent-private feature.
- Verification policies must be randomized with known first-order propensities strictly greater than zero for every declined row.
- Do not report raw targeted-sample precision as population block precision. Use the estimator contract in the spec.
- Discovery recall is offline-only because its denominator requires sealed oracle truth.
- Dashboard code must not import the evaluator/experiment or read sealed files. Use allowlisted, hash-checked exports and a separate explicit gate for offline benchmark aggregates.
- Keep every registered seed, including empty/unstable draws. Report fallback intervals alongside coverage; never equate full-range coverage with useful precision.
- Keep the secondary reliability experiment separate from the frozen primary benchmark. Evidence batches retain every committed ID, including pending cases. Label-error allowances concern the whole declined population and require external justification; never infer them from the sealed oracle in a real audit. Bounds are pointwise under fixed potential evidence, not anytime-valid or a live production guarantee.

## Data and reproducibility

- Never commit IEEE-CIS raw files, derived labeled artifacts, secrets, or credentials.
- Use chronological splits by `TransactionDT`; never replace them with random train/test splitting.
- Derive feature schemas on train only and freeze thresholds before evaluation.
- Record seeds and keep deterministic ordering. Same input/config/seed must replay.
- The no-API-key synthetic flow must remain green.

## Working discipline

- Run relevant tests after every boundary change.
- Add or update tests when contracts change.
- Record only actual failures in `FAILURE_LOG.md`; do not manufacture a hackathon story.
- Update `BUILD_STATE.md` with verified evidence and the next narrow action.
- Preserve the root project mirror and everything under its `sources/` directory.
