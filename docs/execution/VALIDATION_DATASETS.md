# Validation Datasets

## Purpose

This project is intended to work across many business/data domains, not only the
small demo revenue fixture. Therefore, whenever a change affects scanning,
profiling, Semantic Pack draft generation, Registry search/retrieval, MCP tool
behavior, SQL validation, Weaviate/VDB projection, or LLM hypothesis generation,
verification should use as many relevant local/reference datasets as practical.

The goal is not to make every phase process every file on every run. The goal is
to avoid overfitting to one tiny fixture and to prove that the Semantic Data
Context System can generalize across domains while preserving safety boundaries.

## Canonical repository locations

Reference datasets live under:

```text
docs/reference/test_datasets/
```

Generated artifacts must not be written back into these source folders. Write
scan reports, profiles, draft packs, indexing manifests, and audit outputs under
`runtime/**` or another explicitly assigned output directory.

## Source and copy policy

- Source dataset files are read-only inputs.
- If an approved source dataset exists outside the repo and is missing here,
  copy it into `docs/reference/test_datasets/**` before using it in repeatable
  verification.
- Preserve original filenames where possible.
- Do not mutate the external source locations.
- Do not store raw PII values in generated profiles, Semantic Packs, vector
  payloads, feedback logs, prompts, or test reports.
- If a connector cannot read a file type, record that limitation explicitly; do
  not silently skip the dataset or claim coverage.
- If the limitation is resolvable within the current scope and environment,
  resolve it before accepting a fallback. Examples include installing a declared
  optional parser dependency outside the repo, correcting a stale dataset path,
  or fixing a command invocation. If it cannot be resolved safely, record the
  attempted remediation, fallback/skip reason, and evidence.

## Dataset inventory

### 1. Minimal deterministic demo data

Location:

```text
examples/demo_data/
```

Files:

- `users.csv`
- `payments.json`
- `subscriptions.xlsx`

Primary use:

- fast smoke tests
- connector unit tests
- PII raw-value blocking checks
- CLI pipeline checks
- generated draft Semantic Pack validation

Expected current support:

- CSV: supported
- JSON/JSONL: supported
- XLSX: supported with `openpyxl`

### 2. Sinagong Tableau 2026 reference datasets

Repository location:

```text
docs/reference/test_datasets/sinagong_tableau_2026/
```

Original source location:

```text
/Users/jtm427/Desktop/경영정보시각화 능력/2026 시나공_경영정보시각화능력_실기_태블로_실습 및 예제파일
```

Current repository copy count:

- 20 `.xlsx` files recursively
  - 16 top-level `.xlsx` workbooks
  - 4 nested `.xlsx` workbooks under `와일드카드유니온실습/`

Representative domains covered:

- retail / sales / payment history
- HR / employee data
- population and demographic statistics
- online shopping transaction amount by channel/product group
- weather time series
- subway ridership
- store/location data
- amusement park visitors
- appliance product categories
- delivery app usage

Primary use:

- broad XLSX scanner validation
- multi-sheet workbook handling
- Korean column/table naming behavior
- column profile robustness across numeric/date/category-heavy datasets
- PII candidate detection on HR/customer-like datasets
- join/key candidate discovery across related business workbooks
- LLM semantic hypothesis and reverse-question tests using realistic Korean
  business/statistical domains
- Weaviate semantic projection tests once VDB support is approved

Current file list is maintained in:

```text
docs/reference/test_datasets/DATASET_MANIFEST.md
```

Recommended benchmark domain split:

| Benchmark family | Representative files | Primary validation focus |
|---|---|---|
| `sinagong_seil_sales` | `SEILOneCompany_Sales데이터.xlsx`; optional yearly files under `와일드카드유니온실습/` | payment/sales measures, customer join key, customer PII blocking |
| `sinagong_seil_hr` | `SEILOneCompany_HR데이터.xlsx` | HR/person PII, employment dates/status, strict raw-value suppression |
| `sinagong_population_demographics` | `우리나라인구수_2021_2024.xlsx`, `시도별연간인구수.xlsx`, `2008_2024_연령별인구현황.xlsx`, `인구동태건수_2019_2023.xlsx` | public demographic time series and wide/narrow workbook shapes |
| `sinagong_weather_timeseries` | `서울날씨_최고기온.xlsx` | year-sheet time-series profiling and matrix-like data |
| `sinagong_subway_ridership` | `서울지하철승하차인원.xlsx` | larger row count, station/line categories, ridership metrics |
| `sinagong_starbucks_locations` | `스타벅스매장데이터.xlsx` | multi-region sheets, geo/location columns, address safety boundary |
| `sinagong_online_shopping` | `온라인쇼핑몰_판매매체별_상품군별거래액_2017_2024.xlsx` | wide monthly transaction matrix, product/category/media dimensions |
| `sinagong_usage_and_visitors` | `배달앱이용현황.xlsx`, `에버랜드입장객데이터.xlsx` | small public aggregate usage/visitor fixtures |
| `sinagong_series_examples` | `여름가전종목.xlsx` | two-series workbook behavior and numeric time-series profiling |

### 3. Tableau Sample Superstore

Repository location:

```text
docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls
```

Original source location:

```text
/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls
```

Primary use:

- canonical BI/order-management style validation
- legacy Excel `.xls` connector validation
- semantic-gold sales/order/customer/product hypothesis tests
- dashboard-oriented business term and metric discovery tests

Current support note:

- The file is copied into the repo as a reference target.
- Phase 4 Builder supports legacy `.xls` through the explicit `xlrd`
  dependency.
- This dataset is now an active semantic-gold benchmark target.
- It is the canonical multi-sheet legacy Excel fixture for the Phase 4 sheet
  splitting supplement: `Orders`, `People`, and `Returns` must be discovered as
  separate table datasets instead of silently using only the active/first sheet.

## Supplemental Phase 4 Excel sheet-splitting validation

When a change touches Excel scanning, profiling, or draft-pack generation,
validate the worksheet split behavior with the bounded fixtures below:

1. `examples/demo_data/subscriptions.xlsx`
   - single-sheet `.xlsx` compatibility fixture
   - expected behavior: existing workbook-stem table naming remains stable
2. `docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls`
   - multi-sheet `.xls` compatibility and regression fixture
   - expected behavior: each non-empty worksheet becomes a distinct dataset
     with deterministic collision-safe names such as `sample_superstore_orders`,
     `sample_superstore_people`, and `sample_superstore_returns`
3. One representative `.xlsx` workbook from
   `docs/reference/test_datasets/sinagong_tableau_2026/**` when feasible
   - broader Korean business/statistical dataset check
   - expected behavior: multiple non-empty worksheets are reported separately
     and any skipped/unsupported sheet is recorded with an explicit reason

Generated scan/profile/draft-pack outputs for these checks must be written
under `runtime/**`. They must not be written back into source dataset folders,
and they must preserve the Phase 0/4 safety boundary: no database execution, no
LLM calls, no MCP runtime expansion, no VDB indexing, and no raw PII value
storage in validation artifacts.

## Validation matrix by feature area

| Feature area | Minimum dataset | Broader dataset expectation | Pass evidence |
|---|---|---|---|
| File connectors | `examples/demo_data/**` | at least one Sinagong `.xlsx`; Superstore `.xls` | scan report includes expected tables/sheets and row/column counts for semantic-gold benchmark inputs |
| Column profiler | `examples/demo_data/**` | one numeric/date-heavy dataset and one category-heavy dataset | profile JSONL includes type guess, null ratio, cardinality, safe top-N/pattern summaries |
| PII safety | `users.csv`; HR/customer-like datasets | SEIL HR/Sales or any dataset with name/customer-like columns | no raw PII values in profiles, draft packs, prompts, vector payloads, or logs |
| Draft Semantic Pack builder | `examples/demo_data/**` | one selected real workbook/domain per change | generated YAML validates with `semantic_contracts`; blocked columns/policies are present |
| Registry search/retrieval | demo pack plus generated draft pack | multiple generated draft packs from different domains when available | keyword search returns relevant cards without breaking demo pack defaults |
| MCP tools/resources | demo pack | optionally generated draft pack for additional smoke tests | tool outputs remain structured and validation-only; no execution path appears |
| SQL Guard | demo pack | generated packs with policy hints when available | non-SELECT/multi-statement/blocked columns/unknown tables are rejected |
| LLM hypothesis | one small deterministic fixture | at least two distinct real domains | hypotheses include source evidence, confidence, unknowns, and no raw PII payloads |
| Reverse questions | one small deterministic fixture | at least two distinct real domains | questions identify ambiguous terms, metrics, joins, policy/PII confirmations |
| Weaviate/VDB | projection unit fixture | generated semantic cards from multiple domains | indexed payload excludes PII; explicit Weaviate errors are returned when unavailable; keyword search only runs when selected explicitly |

## Dataset selection rule

For each phase or substantial change, select datasets in this order:

1. Always run the minimal deterministic fixture if the feature touches Builder,
   Registry, MCP, or validation behavior.
2. Add one or more real reference datasets from
   `docs/reference/test_datasets/**` when the feature can reasonably process
   them.
3. Prefer diversity over size: choose different domains rather than many similar
   files.
4. For performance-heavy runs, create a bounded sample/manifest under
   `runtime/**` and report what was included/excluded.
5. If a dataset is skipped because of unsupported format, dependency, runtime
   cost, or safety concern, record the skip reason explicitly.

## Weaviate/VDB-specific rules

Weaviate is the intended VDB baseline for future semantic retrieval work. Before
implementation, define and test:

- the semantic text projection format for tables, columns, metrics, terms,
  joins, policies, verified queries, and reverse questions
- fields that must never be indexed because of PII or policy concerns
- stable object IDs and versioning behavior
- local/offline test strategy
- explicit fallback behavior when Weaviate is unavailable
- keyword search parity so the system does not silently pretend VDB coverage
- no silent keyword fallback after a Weaviate configuration/dependency failure

No Weaviate phase should pass unless it proves that raw PII values are excluded
from vectorized/indexed payloads.

## Current known limitations

- `.xlsx` is supported and verified with `openpyxl`.
- legacy `.xls` is supported and verified with `xlrd` against Tableau Sample
  Superstore.
- Large workbook validation should be bounded and reported; do not turn every
  local development test into a full corpus scan unless the phase explicitly
  requires it.
