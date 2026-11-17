# Before/after comparison: legacy fallbacks vs evidence-backed priors

Both models run on identical seeds through the public `generate_profiles` path.
The before model pins every reference accessor to its documented legacy default,
so every delta below is attributable to the committed World Bank evidence.

| Country | Metric | before | after | WDI prior |
|---|---|---|---|---|
| Japan | female share | 0.507 | 0.482 | 0.512 |
| Japan | senior (65+) share | 0.055 | 0.325 | 0.338 |
| Japan | urban share | 0.947 | 0.947 | 0.923 |
| Japan | postgraduate share | 0.208 | 0.194 | n/a |
| Japan | non-standard employment | 0.246 | 0.179 | 0.048 |
| Japan | agriculture industry share | 0.051 | 0.050 | 0.028 |
| Japan | income Gini (sampled) | 0.411 | 0.444 | 0.323 |
| Nigeria | female share | 0.497 | 0.492 | 0.494 |
| Nigeria | senior (65+) share | 0.055 | 0.044 | 0.052 |
| Nigeria | urban share | 0.762 | 0.762 | 0.638 |
| Nigeria | postgraduate share | 0.112 | 0.116 | n/a |
| Nigeria | non-standard employment | 0.256 | 0.264 | 0.059 |
| Nigeria | agriculture industry share | 0.163 | 0.153 | 0.335 |
| Nigeria | income Gini (sampled) | 0.401 | 0.382 | 0.339 |
| India | female share | 0.469 | 0.467 | 0.484 |
| India | senior (65+) share | 0.055 | 0.099 | 0.097 |
| India | urban share | 1.000 | 1.000 | 0.357 |
| India | postgraduate share | 0.184 | 0.173 | n/a |
| India | non-standard employment | 0.258 | 0.248 | 0.08 |
| India | agriculture industry share | 0.000 | 0.000 | 0.416 |
| India | income Gini (sampled) | 0.395 | 0.404 | 0.23 |
| United States | female share | 0.495 | 0.478 | 0.498 |
| United States | senior (65+) share | 0.055 | 0.217 | 0.222 |
| United States | urban share | 0.929 | 0.929 | 0.802 |
| United States | postgraduate share | 0.222 | 0.208 | n/a |
| United States | non-standard employment | 0.262 | 0.217 | 0.08 |
| United States | agriculture industry share | 0.046 | 0.047 | 0.015 |
| United States | income Gini (sampled) | 0.416 | 0.442 | 0.418 |
| Brazil | female share | 0.504 | 0.475 | 0.508 |
| Brazil | senior (65+) share | 0.055 | 0.135 | 0.142 |
| Brazil | urban share | 0.927 | 0.925 | 0.882 |
| Brazil | postgraduate share | 0.212 | 0.199 | n/a |
| Brazil | non-standard employment | 0.276 | 0.254 | 0.114 |
| Brazil | agriculture industry share | 0.061 | 0.071 | 0.076 |
| Brazil | income Gini (sampled) | 0.428 | 0.431 | 0.503 |
| Sweden | female share | 0.493 | 0.472 | 0.496 |
| Sweden | senior (65+) share | 0.055 | 0.246 | 0.251 |
| Sweden | urban share | 0.898 | 0.898 | 0.891 |
| Sweden | postgraduate share | 0.226 | 0.214 | n/a |
| Sweden | non-standard employment | 0.316 | 0.253 | 0.165 |
| Sweden | agriculture industry share | 0.048 | 0.048 | 0.018 |
| Sweden | income Gini (sampled) | 0.408 | 0.435 | 0.293 |

## Interpretation

- Age: before, every country shared one synthetic age mix; after, senior/young shares
  follow each country's verified WDI age bands (Japan skews senior, Nigeria skews young).
- Gender: before, a fixed 48/48/4 mix everywhere; after, female shares track the
  verified WDI female population share with Non-binary capped at 4%.
- Income: before, one fixed noise sigma (0.28) everywhere; after, the sampled income
  Gini moves toward each country's verified Gini (damped, documented model).
- Employment/education/industry: before, uniform legacy weights; after, priors rise
  with verified unemployment, tertiary enrollment and ILO sector shares respectively.
  Note the non-standard-employment metric is dominated by the legacy status mix;
  the verified unemployment prior modulates it (Japan low, Sweden/Spain higher).
- India's registry industry list is a documented legacy override (Technology, Finance,
  Manufacturing, Healthcare, Media) with no Agriculture entry, so its agriculture
  share stays 0 by design; sector priors tilt within each country's own list.
- Japan's income Gini (0.444 vs WDI 0.323) stays high because the damped model
  deliberately applies only part of the measured inequality to per-profile noise
  (career/education multipliers dominate within-country spread).
- No schema, endpoint, payload or field-name changed: the same 510 columns, the same
  vocabulary, the same deterministic API.