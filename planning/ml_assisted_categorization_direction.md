# ML-Assisted Categorization Direction

**Status:** Approved product direction; implementation intentionally deferred  
**Owner decision date:** 2026-10-02

## Purpose

Preserve the product direction established during ML/AI engineering exploration without prematurely implementing machine learning.

Family Finance OS should be able to evaluate a future **local ML-assisted categorization** capability, particularly for item-level purchase categorization. This is not authorization to add ML code, models, dependencies, hosted services, APIs, GPU requirements, or other implementation groundwork now.

Future engineering passes should discover this document before making product-shaping categorization changes.

## Why this direction exists

Transaction-level merchant categorization is often intrinsically ambiguous. A single retailer transaction can contain groceries, pet supplies, household goods, medical items, clothing, electronics, and other categories. Family Finance OS already treats item-level detail as enrichment rather than replacement ledger transactions, making item-level categorization a more useful potential learning target than simply predicting a category for an entire mixed-basket transaction.

The current cold-start constraint is not lack of raw financial history. It is lack of sufficiently trustworthy labeled ground truth. The product can improve that position over time through normal human review.

## Near-term product direction

Without implementing ML, categorization and review designs should preserve enough provenance to distinguish outcomes such as:

- human assigned;
- human confirmed;
- human corrected;
- exact historical match;
- deterministic rule;
- future ML suggestion accepted;
- future ML suggestion corrected.

Human-confirmed and human-corrected categorization decisions are potentially useful future training labels. This does **not** mean all existing categorization data should automatically be treated as ground truth.

When future work touches the relevant schemas or review flows, prefer clean boundaries that can retain this provenance without speculative ML-specific implementation.

## Candidate future architecture

A future experiment should favor a hybrid hierarchy rather than replacing deterministic behavior:

1. Exact known item/category match when available.
2. Approved deterministic categorization rules.
3. Optional ML classifier for unresolved cases.
4. Human review for ambiguous or low-confidence cases.
5. Confirmed/corrected human decisions become candidate ground-truth examples for later training.

The ML layer should initially be feature-flagged and non-authoritative. A prediction should carry at least the conceptual equivalents of:

- proposed category;
- confidence or model score;
- model/version provenance;
- suggestion/review state.

A model prediction must not silently overwrite authoritative financial categorization.

## Evaluation standard

ML earns production responsibility only if measured results justify the added complexity.

At minimum, compare:

- deterministic matching/rules alone; versus
- deterministic matching/rules plus ML assistance.

Useful product measures include:

- percentage of items/transactions categorized correctly without manual intervention;
- manual-review reduction;
- incorrect automatic categorization rate;
- performance by category, including rare categories;
- confidence calibration or equivalent threshold behavior;
- performance on held-out/future data rather than training examples.

Prefer temporal evaluation where practical, such as training on earlier confirmed examples and testing against later confirmed examples.

The key product question is:

> Does ML meaningfully reduce manual categorization while preserving Family Finance OS's truth, auditability, and review requirements?

If the improvement is marginal or errors are unacceptable, deterministic rules plus human review remain the product behavior.

## Data-volume expectations

There is no approved minimum dataset size. The useful unit is the number, quality, diversity, and class balance of trustworthy labeled examples rather than days of transaction history.

Small datasets may be sufficient for learning experiments, but production usefulness must be demonstrated empirically. Item-level examples from repeated household purchasing may allow useful experimentation with hundreds or thousands of confirmed labels, but this is an expectation to test, not a product assumption.

## Cost and runtime assumptions to validate

The initial candidate should be a small classical ML classifier where practical, not an LLM or large neural model. Household-scale inference and periodic retraining are expected to be compatible with ordinary CPU hardware, but actual resource requirements must be measured before adoption.

Do not introduce:

- paid ML infrastructure;
- hosted inference;
- external financial-data transmission;
- GPU requirements;
- model-provider APIs;
- substantial new runtime dependencies

without a separate owner-approved architecture/cost/privacy decision.

Local-first privacy and the existing data-handling policy remain controlling requirements.

## Explicit non-scope

This direction does **not** authorize:

- ML implementation now;
- database/schema migrations solely for speculative ML;
- model training against real household data before the applicable real-data validation boundary permits it;
- treating inferred labels as confirmed truth;
- replacing deterministic rules that already solve a case reliably;
- bypassing review queues;
- committing training data derived from real household finances to Git;
- expanding the product into general-purpose AI/LLM infrastructure.

## Future discovery note

When a future coding pass works on categorization, item-level enrichment, review provenance, or automated high-confidence decisions, revisit this document and the current product requirements. The intended sequence is:

**collect trustworthy provenance and labels -> establish deterministic baseline -> run feature-flagged ML experiment -> evaluate on held-out data -> decide whether ML earns a production role.**

This direction follows the repository's broader principle of building narrowly in scope while preserving clean architectural boundaries for justified future capability.
