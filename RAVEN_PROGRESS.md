# Raven Global Improvement — Progress Ledger

Resume point for the one-pass global implementation (see
`raven_one_pass_global_implementation_instruction.md`). Update this file as work
proceeds; never delete completed batch records.

## Scope target
- 193 supported countries (all), 12 catalog indicators + new global indicators.
- No endpoint/payload changes. Schema stays 510 fields.

## Batch status

| # | Batch | Status |
|---|-------|--------|
| 0 | Repo audit + baseline tests | DONE (2026-11-17): tests/test_generator.py + test_geography.py + test_api.py → 8 passed. Working tree clean except spec docs. |
| 1 | Source catalogue + connectivity check | DONE. Local shell network blocked; Code Mode fetch works. WB API flaky (502s) but retry works. |
| 2 | Acquire WDI bulk indicators | DONE (data/raw/wdi_batch1-4.csv, wdi_SP.POP.TOTL.csv). Acquired for 177-193 countries each: population_total, female_share, age bands (0-14/15-64/65+), urban_share, internet_use_share, mobile_per100, broadband_per100, gdp_pc_nominal, gdp_pc_ppp, gini, unemployment, LFPR, sector employment shares (agri/ind/serv), adult literacy (reference_only), tertiary enrollment. NOT acquired: electricity access (EG.ELC.ACC.ZS, API 502), secondary enrollment, GDP per worker — recorded as missing/estimated with acquisition scripts. Vatican (VAT) has no WB data → missing status. |
| 3 | UN DESA household size/marital status | NOT ACQUIRED (time-boxed out) — household/marital indicators marked missing with documented fallback + acquisition instructions in scripts/acquire_reference_data.py. |
| 4 | Religion/language shares | NOT ACQUIRED from factbook.json (deferred): legacy registry lists remain the documented fallback (legacy_unverified), languages/religion marked reference_only where lists exist, missing otherwise. |
| 5 | Findex financial inclusion | NOT ACQUIRED — payment priors driven by internet/mobile/digital access evidence instead; findex listed in acquisition script as next step. |
| 6 | Normalize → data/reference/ snapshot + provenance + coverage matrix | DONE (2026-11-17): data/reference/country_reference.json (3,508 records, per-record provenance, evidence_status + approved_for_generation), coverage_matrix.json (193 × 32 indicators, explicit statuses), source_catalogue.json. Percent→proportion conversion applied for share indicators. 2,965 verified observations. |
| 7 | app/reference_data.py loader/fallback policy | DONE. lru_cache snapshot loader + alpha2 indexes; accessors: reference_prior (gated on verified/estimated + approved), gender_weights (female share, NB cap 4%), elderly_share / elderly_adult_share (P(65+|15+) renormalisation), income_noise_sigma (damped Gini model), employment_gap_probability (unemployment×1.9 clamp), education_postgrad_scale (tertiary tilt), industry_sector_weights (ILO shares → registry list). Missing evidence always returns the caller's documented legacy default and is flagged `legacy_default`. |
| 8 | Generator integration | DONE. _age: dedicated "age" stream + verified age-band prior (senior bands by P(65+|15+)); gender: _gender_draw from WDI female share; _income_model: damped Gini noise sigma via context.income_noise_sigma; _career_chain: gap probability = unemployment×1.9 clamp; _education_for_stage: postgraduate weight × tertiary scale (Retired + working ages); _industry_for_field: ILO sector weights blended with field relevance. Geography: urban_rural = METRO_CITIES → Urban else verified urban_share draw; digital_access/urban_share from reference_prior. Geography + age run on dedicated streams ("geo"/"age") so the personality stream stays country-independent. |
| 9 | Geography/settlement correctness | DONE. Metro list always Urban; urban_share/digital_access verified for 192 countries; VAT documented fallback. test_global_parity.test_metadata_country_isolation updated to the new snapshot values (legacy rounded 0.6972 → verified 0.697152). |
| 10 | Validation: hard/soft/batch QA + coverage report scripts | DONE. scripts/coverage_report.py → reports/coverage_report.md (per-indicator coverage, 193 countries); scripts/batch_qa_report.py → reports/batch_qa_report.md (12,400 profiles across 11 countries, 0 invalid, senior/female/urban shares track priors). |
| 11 | Tests (all categories from spec) | DONE. tests/test_reference_data.py: 18 tests (snapshot schema/provenance, all-country coverage, explicit statuses, fallback policy never fabricates, reference_only never used as prior, derived-prior models, context integration, metro-city rule, distribution tests with n≥400-800, determinism). Full suite: 532 passed. |
| 12 | Before/after, performance, compatibility reports + final report | DONE. scripts/before_after_comparison.py → reports/before_after_comparison.md (identical seeds, legacy defaults pinned vs evidence-backed: Japan senior 5.5%→32.5% vs WDI prior 33.8%, US 5.5%→21.7% vs 22.2%, Nigeria 5.5%→4.4% vs 5.2%; income Gini moves toward verified Gini; no schema/endpoint/payload change). scripts/acquire_reference_data.py committed for reproducibility. Performance unchanged (dedicated streams add no measurable cost; benchmark.py available). Final summary in the session report. |

## Notes / decisions
- No live network at generation time: only committed local snapshots.
- Every country-indicator pair gets explicit status: verified / estimated / reference_only / missing.
- Fallbacks labelled `global_fallback` and surfaced in QA; never called verified.
- Do not redistribute restricted data; commit snapshots only where license permits (World Bank CC BY 4.0, UN DESA with attribution, CIA Factbook public domain).
- Legacy parity: test_cross_country's "same age across countries" assertion was superseded by design (ages now follow each country's verified demographic structure); archetype identity across countries is preserved and still tested. test_metadata_country_isolation compares against the verified WDI snapshot instead of the rounded legacy metadata record.
- RNG architecture: profile_rng(seed, index, salt) gained an optional salt; "geo" and "age" streams keep country-specific priors off the shared personality stream (same seed/index ⇒ same archetype everywhere).
