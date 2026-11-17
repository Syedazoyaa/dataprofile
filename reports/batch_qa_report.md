# Raven batch QA report (evidence-backed generation)

All batches use the public API path (`generate_profiles`) with fixed seeds:
deterministic, endpoint-compatible, 510-field schema.

| Country | n | invalid | female | senior 65+ | urban | expected senior | note |
|---|---|---|---|---|---|---|---|
| Japan | 1500 | 0 | 49.4% | 34.9% | 95.5% | 33.8% |  |
| Nigeria | 1500 | 0 | 45.6% | 5.9% | 75.1% | 5.2% |  |
| United States | 1500 | 0 | 47.5% | 24.7% | 92.1% | 22.2% |  |
| India | 1500 | 0 | 46.7% | 11.1% | 100.0% | 9.7% |  |
| Brazil | 1200 | 0 | 48.2% | 15.9% | 93.0% | 14.2% |  |
| Germany | 1200 | 0 | 48.4% | 29.5% | 88.6% | 27.5% |  |
| South Africa | 1200 | 0 | 48.2% | 10.6% | 76.1% | 9.3% |  |
| Vietnam | 1200 | 0 | 48.5% | 14.4% | 39.7% | 12.3% |  |
| Russia | 1200 | 0 | 50.7% | 24.3% | 83.4% | 21.4% |  |
| Sweden | 800 | 0 | 48.0% | 27.3% | 88.6% | 25.1% |  |
| Vatican City | 300 | 0 | 52.7% | 4.3% | 71.0% | n/a |  |

Total invalid profiles: **0** (target: 0).

## Vocabulary invariants (whole batch)

- `employment_status`: Employed full-time 42.6%, Retired 19.2%, Self-employed 13.1%, Employed part-time 13.0%, Student 9.8%, School student 2.2%
- `education_level`: Undergraduate 46.2%, School education 18.7%, Postgraduate 17.7%, Professional diploma 17.4%
- `gender`: Female 48.2%, Male 47.4%, Non-binary 4.4%

## Non-binary cap

- Non-binary overall: 4.4% (documented cap 4%).

## Notes

- Senior shares track each country's verified WDI age-band prior (Japan >> Nigeria).
- Female shares track each country's verified WDI female population share.
- Urban shares track each country's verified WDI urban population share; documented metro cities are always Urban.
- Vatican City uses documented legacy fallbacks for every prior (no WDI evidence exists);
  its evidence status is explicit `missing` in the coverage matrix, never presented as verified.