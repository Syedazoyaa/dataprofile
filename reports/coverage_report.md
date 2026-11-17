# Raven reference-data coverage report

Countries: 193 (all supported). Snapshot retrieved 2026-11-17 from the World Bank WDI API.

Statuses: **verified** = direct country observation; **estimated** = documented model on verified inputs;
**reference_only** = context, never a generation prior; **missing** = no defensible value (documented fallback applies).

## Indicator coverage

| Indicator | verified | estimated | reference_only | missing | oldest year | newest year |
|---|---|---|---|---|---|---|
| population_total | 192 | 0 | 0 | 1 | 2025 | 2025 |
| female_population_share | 192 | 0 | 0 | 1 | 2025 | 2025 |
| age_0_14_share | 192 | 0 | 0 | 1 | 2025 | 2025 |
| age_15_64_share | 192 | 0 | 0 | 1 | 2025 | 2025 |
| age_65plus_share | 192 | 0 | 0 | 1 | 2025 | 2025 |
| urban_population_share | 192 | 0 | 0 | 1 | 2025 | 2025 |
| internet_use_share | 192 | 0 | 0 | 1 | 2004 | 2025 |
| mobile_subscriptions_per100 | 192 | 0 | 0 | 1 | 2021 | 2024 |
| gdp_per_capita_ppp_intld | 188 | 0 | 0 | 5 | 2011 | 2025 |
| tertiary_enrollment_gross | 188 | 0 | 0 | 5 | 1986 | 2025 |
| unemployment_rate | 177 | 0 | 0 | 16 | 2021 | 2025 |
| labour_force_participation | 177 | 0 | 0 | 16 | 2021 | 2025 |
| employment_agri_share | 177 | 0 | 0 | 16 | 2021 | 2025 |
| employment_industry_share | 177 | 0 | 0 | 16 | 2021 | 2025 |
| employment_services_share | 177 | 0 | 0 | 16 | 2021 | 2025 |
| income_inequality_gini | 168 | 0 | 0 | 25 | 1992 | 2025 |
| fixed_broadband_per100 | 0 | 0 | 191 | 2 | 2021 | 2024 |
| gdp_per_capita_usd_nominal | 0 | 0 | 191 | 2 | 2011 | 2025 |
| adult_literacy_rate | 0 | 0 | 161 | 32 | 1970 | 2024 |
| education_attainment_distribution | 0 | 0 | 0 | 193 | None | None |
| household_size_and_composition | 0 | 0 | 0 | 193 | None | None |
| marital_status_distribution | 0 | 0 | 0 | 193 | None | None |
| religion_affiliation_distribution | 0 | 0 | 0 | 193 | None | None |
| language_distribution | 0 | 0 | 0 | 193 | None | None |
| housing_tenure_distribution | 0 | 0 | 0 | 193 | None | None |
| transport_mode_distribution | 0 | 0 | 0 | 193 | None | None |
| payment_method_adoption | 0 | 0 | 0 | 193 | None | None |
| consumer_channel_usage | 0 | 0 | 0 | 193 | None | None |
| media_platform_usage | 0 | 0 | 0 | 193 | None | None |
| electricity_access | 0 | 0 | 0 | 193 | None | None |
| secondary_education_enrollment | 0 | 0 | 0 | 193 | None | None |
| gdp_per_worker | 0 | 0 | 0 | 193 | None | None |

## Per-country evidence counts (top/bottom)

| Code | verified | reference_only | missing |
|---|---|---|---|
| AE | 16 | 3 | 13 |
| AL | 16 | 3 | 13 |
| AM | 16 | 3 | 13 |
| AO | 16 | 3 | 13 |
| AR | 16 | 3 | 13 |
| AT | 16 | 2 | 14 |
| AU | 16 | 2 | 14 |
| AZ | 16 | 3 | 13 |
| BA | 16 | 3 | 13 |
| BB | 16 | 3 | 13 |
| ... | | | |
| PW | 10 | 3 | 19 |
| SM | 10 | 3 | 19 |
| LI | 9 | 2 | 21 |
| MC | 9 | 2 | 21 |
| VA | 0 | 0 | 32 |

Total verified country-indicator observations: **2965** across 193 countries and 32 tracked indicators.

Vatican City (VAT) has no World Bank data (not a member): all its indicators are
explicitly `missing` and every generator accessor falls back to the documented legacy model.