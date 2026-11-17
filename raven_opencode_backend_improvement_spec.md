# Raven Backend Improvement Specification for OpenCode

## Role

Act as a senior Python backend engineer, data-quality engineer, and synthetic-data modelling specialist. You are modifying the existing Raven backend repository. Your task is to improve the realism, country localization, financial coherence, behavioural coherence, and validation of generated profiles.

This is an implementation task, not a request for a high-level review. Inspect the current repository first, understand its architecture, and then make carefully scoped changes.

## Critical rules

1. **Do not rewrite Raven from scratch.** Preserve the current architecture and reuse the existing modules wherever possible.
2. **Do not add more profile columns just to make the output look richer.** Raven already has a 510-field schema. Improve the generation of existing fields first.
3. **Do not invent country statistics, distributions, sources, or platform availability.** Never present a guess as verified reference data.
4. **Do not make all countries look statistically identical.** Country and, where evidence permits, subnational differences must influence generation.
5. **Do not overfit tiny samples.** A few generated profiles cannot establish that a country distribution is accurate.
6. **Preserve API compatibility and the existing schema by default.** Do not rename or remove fields, change response structures, or break exports unless a change is essential and explicitly justified.
7. **Do not modify login, signup, authentication, authorization, deployment secrets, or unrelated infrastructure.**
8. **Do not run destructive database operations or migrations.** Do not delete user data or generated artifacts.
9. **Do not silently change the meaning of existing fields.** If two fields are aliases or have overlapping meanings, document that and preserve compatibility.
10. Work in small, testable steps. Before changing code, report the files and functions you intend to change. Then implement and test.

## Repository context to verify

The current backend includes modules such as:

- `app/generator.py`
- `app/geography.py`
- `app/geography_world.py`
- `app/coherence.py`
- `app/rules.py`
- `app/metadata.py`
- `app/analytics.py`
- `app/schemas.py`
- `app/derived.py`
- `app/utils.py`
- `data/metadata/country_indicator_records.json`

The previous code review found a modular generator, a 510-field schema, deterministic seeded generation, local currency handling, metadata provenance support, and hard validation. Preserve these strengths.

The previous review also found the following risks. Re-check each against the current repository before acting; do not assume the code has remained unchanged:

- Country configuration lists for religion, industries, OTT/platforms, housing and shopping ecosystems were highly generic.
- Religion selection used unweighted choice from the country's available options.
- Geography selected a city and then independently sampled Urban/Rural using a country-level urban share.
- City-language affinity covered only a limited number of cities, with generic fallback behaviour.
- Country reference metadata was sparse. The reviewed snapshot had 174 records across four indicators, with GDP-per-capita and Gini records not approved for generation.
- Income generation used broad shared multipliers and a largely shared coefficient of variation rather than country-specific empirical distributions.
- Financial support labels could permit positive expenses with zero personal income without modelling the actual support amount or source of funds.
- Household generation and validation did not fully model country-specific household composition.
- Behavioural interest, usage and purchase-intent values were generated from related but insufficiently conditional scores.
- Several pairs of fields were exact duplicates in the inspected sample:
  - `region` / `cultural_context`
  - `marital_status` / `relationship_status`
  - `education_level` / `highest_degree`
  - `research_before_purchase` / `research_intensity`
  - `research_before_purchase` / `analytical_orientation`
  - `research_intensity` / `analytical_orientation`
  - `information_seeking` / `reading_frequency`
- Hard validation did not include all behavioural or population-level calibration checks.
- The uploaded archive did not clearly provide a comprehensive automated test suite or dependency manifest. Verify the actual working repository before concluding that these are absent.

## Phase 0: Establish the actual repository state

Before editing:

1. Inspect the repository tree, current branch, working-tree status, recent commits and existing uncommitted changes.
2. Read the current schema and all generation, geography, metadata, coherence, validation, analytics and export modules.
3. Identify the actual entry points and call graph for:
   - country selection
   - profile generation
   - demographic generation
   - geography generation
   - income and expense generation
   - household generation
   - behavioural generation
   - validation
   - analytics and quality reporting
4. Locate the current test suite, dependency files, CI configuration and deployment configuration.
5. Run the existing tests and a baseline generation run before changing anything.
6. Save baseline results, including:
   - number of profiles generated
   - supported countries and countries actually sampled
   - hard validation pass/fail counts
   - schema field count
   - deterministic reproducibility result
   - generation time and peak memory if available
   - country-level distributions for selected important fields
7. Produce a short implementation plan identifying exact files/functions and risks.

Do not overwrite or discard existing user changes. If the working tree is dirty, preserve those changes and work around them.

## Phase 1: Country reference-data architecture

Create or improve a centralized, versioned country reference-data layer. Do not scatter country-specific constants across generator functions.

### 1.1 Reference-data design

For each country and indicator, support fields equivalent to:

- country ISO code
- indicator name
- value or distribution
- unit
- source organization
- source title or dataset
- source URL
- reference year or period
- retrieval/publication date where known
- geographic scope
- population scope
- methodology or definition
- confidence / quality status
- whether the value is approved for generation
- known limitations

Use a clear status model, for example:

- `verified`: source and scope are sufficiently clear for generation
- `reference_only`: useful context but not safe to use as a generation prior
- `estimated`: derived from documented evidence and clearly marked
- `missing`: no defensible value available

Do not use `reference_only`, `estimated` or `missing` values as if they were verified facts. If estimated values are used as fallback priors, the output and QA report must identify that fallback.

### 1.2 Indicator coverage

Design the layer to support these indicators where reliable sources are available:

- age distribution
- sex/gender distribution where appropriate and legally/culturally suitable
- education attainment
- household size and household composition
- urban/rural and settlement distribution
- income distribution and income inequality
- employment status and industry composition
- language distribution
- religious affiliation, only where reliable and appropriate
- internet access and device access
- payment methods
- transport modes
- housing tenure and housing type
- consumer channel and marketplace availability
- media/streaming platform availability

Do not block the whole generator if an indicator is unavailable. Use an explicit, documented fallback and report its quality. Never silently fall back to an identical global distribution for every country.

### 1.3 Source discipline

Prefer reputable statistical sources appropriate to the indicator, such as national statistical offices, World Bank, UN agencies, ITU, UNESCO, ILO, OECD, DHS, census publications and other recognized public datasets.

Do not scrape or fabricate figures just to fill coverage. Do not use one source's value for a different definition without documenting the mismatch.

If internet access or source files are unavailable in the current environment:
- build the schema, loader, validation and provenance framework;
- use only already-present evidence-backed data;
- leave unsupported country-indicator combinations explicitly missing;
- create a prioritized data-acquisition checklist;
- do not invent values.

### 1.4 Coverage report

Add a command or script that reports, by indicator:
- number and percentage of countries with verified coverage
- reference-only coverage
- estimated coverage
- missing coverage
- oldest and newest reference years
- countries using fallback values

The report must distinguish *country coverage* from *population representativeness*.

## Phase 2: Country- and region-conditioned generation

Make the generator use the reference-data layer in a consistent way.

### 2.1 Hierarchical conditioning

Where data exists, use this hierarchy:

`country -> administrative region/state/province -> city/municipality -> locality/settlement -> individual`

Not every country will have data at every level. Use the most specific supported level and record the level used. Do not fabricate locality data.

### 2.2 Geography correctness

Fix the current risk of selecting a major city and then independently assigning `Rural`.

- Settlement classification must be derived from the selected geographic unit or its documented classification.
- Support `Urban`, `Peri-urban` and `Rural` only if the schema permits. If the schema only allows Urban/Rural, preserve it and document how peri-urban cases are mapped.
- Do not use a country's national urban share to override a known city/locality classification.
- Distinguish city tier from urban/rural settlement type.
- Validate that city, region and country belong together.
- Validate city-language combinations where reference evidence exists.
- Use explicit fallback quality when the location is sampled only from a country-level list.

Do not claim exact geospatial accuracy unless the data supports it.

### 2.3 Language

- Model primary language separately from additional languages if the existing schema supports both.
- Use regional or city-level distributions when reliable data exists.
- Allow multilingual profiles.
- Do not infer an individual's language solely from nationality, religion, ethnicity or name.
- Keep migration, expatriate and minority-language cases possible.
- Avoid making English the default primary language in countries where that is not a reasonable general-population prior, unless the profile's context supports it.

### 2.4 Religion and sensitive attributes

Religion is a sensitive personal attribute. Handle it carefully.

- Do not infer religion from name, nationality, ethnicity, language or location.
- Treat it as an optional, probabilistic attribute.
- Include non-religious, other, undisclosed and prefer-not-to-say options where schema-compatible.
- Use country-level distributions only where credible, recent-enough sources exist and the population scope matches.
- Preserve minority and migrant possibilities. Do not force an individual to match a majority.
- If no reliable source exists, use an explicitly uncalibrated/unknown fallback or leave the field unset if the schema allows.
- Do not claim the resulting distribution is representative without validation against an external reference.

### 2.5 Industries and occupations

- Use country-specific industry priors only when backed by data.
- Keep occupation, industry, education, field of study, employment status and career level conditionally coherent.
- Do not use a single generic industry distribution for all countries.
- Include informal employment where appropriate and supported by evidence.
- Avoid impossible or highly unlikely combinations, but preserve legitimate exceptions.

### 2.6 Platforms, commerce and payments

- Distinguish global platforms from country-specific services.
- Maintain explicit availability/market-presence status, source and last-verified date.
- Do not assume that a platform is available simply because its name is in a generic list.
- Do not force a user in a country to use a locally popular platform.
- Payment options must be country-appropriate and should distinguish availability from individual adoption.
- Keep India-specific services such as UPI and JioHotstar localized to India unless verified evidence supports availability elsewhere.
- Add tests to ensure country-exclusive services do not leak into unrelated countries.

## Phase 3: Financial model and cash-flow invariants

Improve financial coherence without changing the existing public schema unnecessarily.

### 3.1 Separate financial concepts

Inspect the existing fields and distinguish, where possible:

- personal earned income
- household income
- spouse/partner contribution
- family transfers or allowances
- scholarship/stipend
- pension
- government benefits
- business/self-employment income
- savings withdrawals
- borrowing/debt proceeds
- monthly expenses
- savings contribution
- debt repayments

If the current schema lacks fields for a concept, do not immediately add columns. First determine whether existing fields can represent it without changing their meaning. If a schema addition is truly necessary, document the exact need, compatibility impact, migration/export implications and obtain approval before implementing it.

### 3.2 Cash-flow validation

A profile with zero personal earned income can legitimately have expenses, but the funding source must be modelled.

Build a coherent monthly cash-flow calculation:

`available inflows + planned savings drawdown/borrowing = expenses + savings contribution + debt repayment`

Use a documented tolerance for rounding. Do not treat a text label such as `Self-funded` or `Family support` as proof that funds exist.

### 3.3 Income distributions

- Retain currency-aware values.
- Do not compare raw nominal income amounts across countries as if they were equivalent.
- Separate nominal local currency, exchange-rate conversion and purchasing-power comparisons.
- Use country-specific empirical percentiles or documented priors where available.
- Avoid one shared coefficient of variation for every country if evidence supports country differences.
- Keep regional cost-of-living adjustments distinct from national income distributions.
- Do not claim a profile is statistically representative based only on a country income multiplier.

## Phase 4: Household and life-stage coherence

Improve conditional relationships among:

- age
- education status and highest completed qualification
- employment status
- career level and experience
- marital/relationship status
- household size
- dependents
- children
- parents living in the household
- family type
- housing tenure

Important semantic rules:

- `highest_degree` should mean highest completed qualification, not necessarily current education level.
- Current study status should not be overwritten by highest completed degree.
- Define whether `household_size` includes the respondent.
- Define whether `dependents_count` includes only people living in the household or also dependents living elsewhere.
- A dependent count greater than household size is not automatically invalid if the definitions permit off-household dependents. Validate according to explicit semantics.
- `parents_in_household` and `family_type` should agree unless a documented family-type definition permits an exception.
- Do not impose one country's household structure on another.

## Phase 5: Behavioural generation

Review the existing behavioural feature generation rather than simply adding more random noise.

For each product/service domain, model distinct concepts:

- awareness
- interest
- current usage/ownership
- usage frequency
- need or trigger
- affordability
- purchase intent
- research behaviour
- channel preference

Use conditional dependencies. For example, purchase intent may be influenced by need, replacement cycle, household requirement, affordability, availability and existing ownership. Interest alone should not determine purchase intent.

Requirements:

- Do not force all behaviour scores to agree. Real people can have low interest but high purchase intent for essential products.
- Do not make all behavioural variables copies or simple aliases of one another.
- Give `research_before_purchase`, `research_intensity` and `analytical_orientation` distinct definitions and generation logic if they are separate schema fields.
- Give `information_seeking` and `reading_frequency` distinct definitions.
- Preserve deterministic generation under a fixed seed.
- Add tests for both coherent typical cases and legitimate exceptions.

## Phase 6: Validation architecture

Keep hard validation separate from soft plausibility assessment.

### 6.1 Hard validation

Hard failures should cover objectively invalid data, such as:
- invalid schema types or missing required fields
- impossible dates or age/DOB mismatch
- invalid ISO country/currency combinations
- city/region/country mismatch when reference data exists
- invalid enum values
- mathematically impossible financial calculations
- impossible negative counts or amounts where not permitted

Do not turn uncertain demographic or behavioural assumptions into hard failures.

### 6.2 Soft validation

Add weighted warnings for:
- country-distribution drift
- unsupported fallback usage
- suspicious language/geography combinations
- unusual household relationships
- unusual education/career combinations
- financial alignment concerns
- platform/payment availability uncertainty
- behavioural tensions

Every warning should include:
- stable issue code
- severity
- affected field(s)
- explanation
- whether it is a hard error or soft warning
- evidence/reference identifier where applicable

### 6.3 Country-level statistical QA

Add batch-level validation that compares generated distributions with the reference distributions actually used.

Report:
- sample count per country
- sample count per indicator
- reference year and source
- generated distribution
- expected/reference distribution
- absolute percentage-point difference
- a suitable distribution distance where sample size permits
- confidence/sample-size warning

Do not flag a tiny sample as definitively inaccurate. Do not claim population-level representativeness from a small synthetic batch.

Separate these quality dimensions in the API/reporting:
1. schema validity
2. cross-field consistency
3. country localization coverage
4. statistical calibration
5. reference-data provenance

Do not combine them into one misleading score.

## Phase 7: Duplicate and overlapping fields

Audit the 510 schema fields for exact aliases and semantic overlap.

For each suspected pair:
- inspect schema descriptions and actual generation logic;
- determine whether the fields are intended aliases, separate concepts, or accidental duplicates;
- preserve existing field names and API output;
- if aliases are required for compatibility, mark them explicitly in schema metadata/documentation;
- if separate concepts, give them distinct generation logic;
- add tests that prevent accidental equality where fields are intended to be independent.

Do not blindly remove fields or change the schema.

## Phase 8: Determinism, performance and API compatibility

- Preserve fixed-seed reproducibility.
- Ensure separate profile RNG streams remain deterministic.
- Avoid network calls during normal profile generation.
- Load and validate reference data once, with safe caching.
- Avoid loading huge datasets repeatedly for each profile.
- Avoid expensive per-profile scans of all reference records.
- Preserve existing endpoints, request parameters, response structures and export formats.
- Add backward-compatibility tests for API and CSV/JSON exports.
- Do not silently change default generation behaviour without documenting it.

## Phase 9: Required tests

Create or extend automated tests. At minimum:

### Unit tests
- reference-data schema and provenance validation
- missing/unsupported reference-data fallback
- country-specific weighted sampling
- regional language sampling
- city/settlement consistency
- currency and income calculations
- cash-flow consistency
- household semantics
- behavioural dependency logic
- alias/duplicate-field definitions
- stable issue codes and severity

### Property/invariant tests
- age and DOB always agree
- generated country code and currency are valid
- selected city belongs to selected country/region when data exists
- known urban city is not randomly labelled rural
- all financial inflows/outflows reconcile within tolerance
- profile counts and schema remain stable
- deterministic output for the same seed
- no country-exclusive service leaks into an unsupported country

### Integration tests
- generate profiles for India, United States, Japan, Nigeria, Brazil, Saudi Arabia, Guatemala and Vatican City where supported by current data
- generate global profiles
- generate profiles for a country with missing reference data and verify transparent fallback behaviour
- validate exports and analytics
- verify existing API contracts

Use fixed seeds. Tests should not depend on live internet access.

### Distribution tests
Use sufficiently large samples for distribution checks. Avoid brittle assertions on tiny batches. Test broad tolerances and record the reference data/version used by the test.

## Phase 10: Deliverables

When implementation is complete, provide:

1. A concise summary of architectural changes.
2. Exact files changed and why.
3. Any schema/API compatibility impact.
4. Reference-data sources added, including URLs, years, definitions and limitations.
5. Indicators/countries still missing verified data.
6. Baseline-versus-after test results.
7. Test commands and pass/fail counts.
8. A country coverage report.
9. A sample country QA report.
10. Remaining risks and items that require human/data-source review.

Do not claim that Raven is globally representative unless there is an external validation methodology and evidence supporting that claim.

## Execution strategy

Implement in this order:

1. Baseline and repository audit.
2. Reference-data schema, loader, provenance and coverage reporting.
3. Geography and settlement correctness.
4. Country-conditioned religion/language/industry/platform options where evidence exists.
5. Financial cash-flow model.
6. Household and life-stage coherence.
7. Behavioural dependency model.
8. Hard/soft/batch validation.
9. Analytics quality reporting.
10. Full regression, performance and compatibility testing.

After each phase:
- run the relevant tests;
- summarize what changed;
- identify any assumptions;
- stop and report blockers rather than inventing data or silently weakening validation.

**Important final instruction:** Prefer a smaller amount of well-sourced, correctly used country data over broad but fabricated country coverage. Raven should be honest about what it knows, what it estimates, and what it does not know.
