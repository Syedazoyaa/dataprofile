# Raven: One-Pass Global Implementation Instruction

Use this instruction together with `raven_opencode_backend_improvement_spec.md` and the web-research instruction.

## Objective

Complete the Raven backend improvement across the entire supported global country set in one coordinated implementation. Do not stop after an eight-country pilot, proof of concept, or partial country rollout.

The target is **all 193 supported countries** (or the exact supported-country count found in the current repository). Every country must be assessed, included in the reference-data coverage matrix, and supported by the generation pipeline.

This does NOT mean inventing data to force every country to have verified coverage. It means delivering global technical coverage with honest evidence-quality labels.

## Non-negotiable requirements

1. Research all supported countries, not just a selected pilot group.
2. Build one common reference-data architecture and use it for every country.
3. For every country-indicator pair, record one of:
   - VERIFIED
   - ESTIMATED
   - REFERENCE_ONLY
   - MISSING
4. Include source URL, organization, dataset, reference year, indicator definition, population scope, unit, retrieval date and limitations wherever applicable.
5. Do not fabricate country statistics, distributions, regional breakdowns, platform availability or citations.
6. Do not silently copy one country's distribution to another.
7. Where no defensible country-specific data exists, use a clearly labelled fallback model and report it as uncalibrated. Do not call it verified.
8. Preserve minority, migrant and unusual-but-valid individual profiles. Country priors must never become deterministic identity rules.
9. Do not make live internet calls during normal profile generation. Research and acquire snapshots during development/data preparation; load local versioned reference data at runtime.
10. Preserve the existing 510-field schema and public API by default. Any proposed breaking change must be explained and justified before implementation.
11. Preserve authentication, authorization, deployment configuration and unrelated functionality.
12. Do not run destructive database operations or migrations.

## Global research coverage

Assess every supported country against every relevant indicator below. If a source does not cover a country, mark that country-indicator pair accordingly.

### Population and demographics
- Age distribution
- Sex distribution, where the source and schema definitions support it
- Education attainment
- Household size and composition
- Marital/family structure where reliable data exists
- Urban/rural/settlement distribution

### Economic and employment
- Income distribution and percentiles
- Income inequality
- Employment/unemployment
- Labour-force participation
- Industry and occupation composition
- Informal employment where available
- Regional economic variation where supported

### Language and society
- Main and regional languages
- Multilingualism where measurable
- Religion/non-religious affiliation only where reliable, appropriate and population scope is clear

### Infrastructure and consumer context
- Internet and device access
- Payment rails and payment adoption
- Housing tenure and housing type
- Transport modes
- E-commerce and shopping channels
- Streaming/media platform availability
- Food delivery and relevant consumer services

Do not imply that a country has reliable data for every indicator. Report the actual evidence.

## Research method

Use web search and page retrieval to find primary and reputable sources. Prefer:
- National statistical offices and census agencies
- World Bank and World Development Indicators
- UN Population Division and UN agencies
- ILOSTAT
- UNESCO Institute for Statistics
- ITU
- OECD where applicable
- DHS and other recognized survey programmes
- Official central banks, payment regulators and service-provider documentation for payment/platform availability

Prefer reusable global datasets and official APIs that cover many countries, then supplement with national sources for gaps and subnational detail.

Do not search for 193 isolated articles if one authoritative global dataset provides consistent comparable indicators. Check definitions, years and coverage before combining sources.

For every source, verify that its indicator definition matches the Raven field being calibrated. Do not use GDP per capita as personal salary, internet availability as individual adoption, or platform availability as proof of usage.

Respect source licensing and terms. Record attribution and redistribution constraints. Do not commit datasets that cannot legally be redistributed. Where necessary, commit a reproducible acquisition script, source manifest and instructions instead of restricted raw data.

## All-country implementation architecture

Implement the reference-data model once, not as 193 unrelated hardcoded branches.

Use:
- normalized country identifiers (ISO codes)
- normalized indicator identifiers
- consistent category mappings
- source/provenance records
- reference periods and units
- explicit quality status
- versioned snapshots
- validated loaders and caches
- fallback policy
- coverage reporting

Support hierarchical conditioning where evidence exists:

`country -> administrative region -> city/municipality -> locality/settlement -> individual`

Do not fabricate missing subnational records. Record the most specific geographic level actually supported.

## Generator integration

Connect the reference data to the existing Raven generator. Do not merely create unused JSON or CSV files.

Use evidence-backed country/region priors for the existing fields relating to:
- demographics
- education
- employment
- household composition
- geography and settlement
- language
- religion where appropriate
- income and expenses
- housing
- transport
- payments
- shopping and media ecosystems

Use conditional generation for cross-field dependencies. Retain deterministic seeded behaviour.

For attributes without reliable population distributions, such as individual personality or personal preferences, use a documented probabilistic model. Do not pretend those values are census-calibrated.

## Global coverage and honest fallbacks

Every country must have a row in the country coverage matrix.

For each indicator, show:
- country
- status
- source
- reference year
- definition/scope
- whether used by generation
- fallback method, if any
- known limitations

Fallbacks must be explicit and conservative. A fallback must not be represented as country-specific empirical evidence. Where a global prior is used because no better evidence exists, label it as a global fallback and expose that fact in QA output.

Do not fail the whole global generation request because one country's indicator is missing. Do not silently disguise missing evidence either.

## Validation and tests

Add:
- reference-data schema/provenance tests
- all-country ISO coverage tests
- indicator coverage report tests
- country-specific sampling tests
- city/region/country consistency tests
- settlement consistency tests
- currency and financial cash-flow invariants
- household semantic tests
- behavioural dependency tests
- country-exclusive platform/payment leakage tests
- deterministic-seed tests
- API/schema/export regression tests
- batch statistical QA with sample-size warnings

Run tests for all supported countries where possible. Use fixed seeds and offline fixtures. Distribution tests must use adequate sample sizes and sensible tolerances; do not write brittle tests that expect tiny samples to match population percentages exactly.

## Execution plan: one coordinated delivery

You may divide the work internally into research and implementation batches to manage context, rate limits and file sizes. However:

- Do not stop after the first batch.
- Do not ask the user to approve each country.
- Do not declare completion while countries remain unassessed.
- Maintain a persistent progress ledger in the repository so work can resume safely if context or tool limits are reached.
- Complete all batches before presenting the final implementation report.
- If a genuine external limitation prevents completion (API quota, unavailable source, licensing restriction, missing credentials, context/runtime limit), record exactly what remains and continue with all work that can be completed. Never fabricate the missing result.

Recommended internal workflow:
1. Inventory the actual supported countries and existing repository state.
2. Identify global datasets that cover many countries.
3. Build a source and indicator catalogue.
4. Acquire and normalize all usable data.
5. Assess every country-indicator pair and create the complete coverage matrix.
6. Integrate the reference-data layer into the generator.
7. Improve geography, demographics, finances, households and behaviour.
8. Add hard, soft and batch-level validation.
9. Run country and global regression tests.
10. Produce before/after reports.

## Required final deliverables

Do not finish without producing:

1. Updated backend implementation.
2. Versioned reference-data files or reproducible acquisition scripts, subject to licensing.
3. Source catalogue with URLs and methodology.
4. Complete coverage matrix for all supported countries.
5. Per-indicator coverage summary: verified, estimated, reference-only and missing.
6. List of countries still using fallbacks and the exact indicators affected.
7. Global and selected-country QA reports.
8. Before/after generation comparisons.
9. Full test results and commands.
10. Performance and memory comparison.
11. API/schema compatibility report.
12. Remaining limitations and recommended next data-acquisition work.

## Definition of done

The task is complete only when:

- Every supported country has been assessed.
- Every relevant indicator has an explicit evidence status for every country.
- The generator actually consumes the reference-data layer.
- Missing evidence is visible and never presented as verified.
- Global generation still works.
- Existing API and schema compatibility is verified.
- Tests pass, or every failure is explicitly explained.
- Country-level calibration claims are limited to what the evidence and sample sizes support.

**Do the entire global implementation in one coordinated project. Internal batching is allowed; partial delivery disguised as completion is not.**
