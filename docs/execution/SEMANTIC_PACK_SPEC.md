# SEMANTIC PACK SPEC

## 1. Purpose

A Semantic Pack is the source-of-truth YAML document that describes how a data domain should be understood by external LLMs, agents, and apps.

It captures physical schema context, business terminology, value dictionaries, metrics, joins, policies, verified queries, and unresolved reverse questions.

## 2. Design Requirements

- YAML-first for human review and git diffability
- deterministic IDs for cards and policies
- explicit versioning
- safe handling of sensitive values
- LLM-generated hypotheses must be distinguishable from human-confirmed definitions
- compatible with Registry search and MCP tool responses
- no requirement for a production VDB in MVP


## 2.1 Phase 0 Contract Boundary

Phase 0 implements only the contract surface needed to validate a demo Semantic Pack.

Phase 0 may include:

- Semantic Pack schema/types
- YAML loading and validation
- demo pack fixture
- SQL guard validation contract and tests

Phase 0 must not include:

- Registry runtime
- MCP server runtime
- Builder scanner runtime
- query execution
- dashboard or confirmation UI

## 3. Top-Level Shape

```yaml
semantic_pack:
  id: demo_company.revenue
  version: 0.1.0
  status: draft | reviewed | approved
  title: Demo Company Revenue Context
  description: Revenue/customer/campaign semantic context for demo use.
  locale: ko-KR
  owners:
    - role: data_owner
      name: Demo Data Team
  source_refs:
    - type: file | postgresql | bi_doc | query_log
      name: demo_source
      safe_reference: true
  spaces:
    - id: revenue
      title: Revenue Analysis
  tables: []
  columns: []
  value_dictionaries: []
  metrics: []
  business_terms: []
  join_recipes: []
  policies: []
  verified_queries: []
  reverse_questions: []
  metadata:
    created_at: "2026-05-08"
    updated_at: "2026-05-08"
```

## 4. Card Types

### 4.1 Table Card

```yaml
tables:
  - id: table.orders
    space_id: revenue
    physical_name: orders
    title: Orders
    description: Customer order fact table.
    role: fact | dimension | bridge | event | unknown
    grain: one row per order
    primary_key: order_id
    columns:
      - order_id
      - customer_id
      - ordered_at
      - status
    pii_level: none | low | moderate | high
    status: draft | confirmed
    confidence: 0.8
```

### 4.2 Column Card

```yaml
columns:
  - id: column.orders.status
    table: orders
    name: status
    data_type: string
    nullable: false
    semantic_type: status_code
    description: Order lifecycle status.
    profile:
      null_ratio: 0.0
      cardinality: 4
      top_values_safe: true
    pii:
      is_candidate: false
      raw_value_storage: allowed | blocked
    status: draft | confirmed
    confidence: 0.7
```

### 4.3 Value Dictionary

Use only for safe categorical values. Do not store raw PII values.

```yaml
value_dictionaries:
  - id: value_dict.orders.status
    table: orders
    column: status
    values:
      - value: PAID
        label: 결제 완료
        description: Payment completed order.
        count: 1200
        source: profiler | human | verified_query
        status: draft | confirmed
      - value: CANCELLED
        label: 주문 취소
        status: draft
```

### 4.4 Metric

```yaml
metrics:
  - id: metric.net_revenue
    name: net_revenue
    label: 순매출
    description: Gross payment amount minus refunds and discounts.
    formula_sql: payments.amount - refunds.amount - discounts.amount
    date_basis: payments.paid_at
    required_tables:
      - payments
      - refunds
    default_filters:
      - payments.status = 'PAID'
    status: draft | confirmed
    owner: finance
```

### 4.5 Business Term

```yaml
business_terms:
  - id: term.new_customer
    term: 신규 고객
    aliases:
      - new customer
    definition: First paid date falls within the analysis period.
    sql_condition: customers.first_paid_at >= {start_date} AND customers.first_paid_at < {end_date}
    related_tables:
      - customers
      - payments
    related_metrics:
      - metric.net_revenue
    ambiguity_policy: ask_if_date_basis_missing
    status: draft | confirmed
```

### 4.6 Join Recipe

```yaml
join_recipes:
  - id: join.orders_customers
    left_table: orders
    right_table: customers
    join_type: many_to_one
    condition: orders.customer_id = customers.customer_id
    recommended: true
    warnings:
      - Use customers.customer_id, not email, for joins.
```

### 4.7 Policy

```yaml
policies:
  - id: policy.marketing_safe_revenue
    applies_to:
      roles:
        - marketing_analyst
    allowed_tables:
      - orders
      - payments
      - campaigns
    blocked_columns:
      - customers.email
      - customers.phone
      - customers.address
    notes:
      - Aggregated revenue is allowed; raw PII is blocked.
```

### 4.8 Verified Query

```yaml
verified_queries:
  - id: verified_query.new_customer_revenue_by_campaign
    question: 지난달 신규 고객 순매출을 캠페인별로 보여줘
    sql: |
      SELECT campaign_id, SUM(net_revenue) AS net_revenue
      FROM demo_revenue_view
      WHERE first_paid_at >= {start_date}
        AND first_paid_at < {end_date}
      GROUP BY campaign_id
    related_terms:
      - term.new_customer
    related_metrics:
      - metric.net_revenue
    status: confirmed
```

### 4.9 Reverse Question

```yaml
reverse_questions:
  - id: rq.revenue.date_basis
    target: metric.net_revenue
    question: 월별 매출 집계 시 주문일, 결제일, 정산일 중 어떤 날짜를 기준으로 하나요?
    reason: Multiple candidate date columns were detected.
    status: open | answered | dismissed
    answer: null
```

## 5. MCP Tool Contracts

All tools must return deterministic JSON-compatible objects.

### 5.1 `list_semantic_spaces`

Input:

```json
{}
```

Output:

```json
{
  "spaces": [
    {
      "space_id": "demo_company.revenue",
      "title": "Demo Company Revenue Context",
      "version": "0.1.0",
      "status": "draft"
    }
  ]
}
```

### 5.2 `search_semantic_context`

Input:

```json
{
  "space_id": "demo_company.revenue",
  "query": "신규 고객 순매출",
  "filters": {
    "card_types": ["business_term", "metric", "table", "column", "value_dictionary"],
    "limit": 10
  }
}
```

Output:

```json
{
  "results": [
    {
      "card_id": "term.new_customer",
      "card_type": "business_term",
      "title": "신규 고객",
      "snippet": "First paid date falls within the analysis period.",
      "score": 0.91,
      "source_pack": "demo_company.revenue@0.1.0"
    }
  ]
}
```

### 5.3 `resolve_business_terms`

Input:

```json
{
  "space_id": "demo_company.revenue",
  "terms": ["신규 고객", "순매출"]
}
```

Output:

```json
{
  "resolved_terms": [
    {
      "input": "신규 고객",
      "term_id": "term.new_customer",
      "definition": "First paid date falls within the analysis period.",
      "sql_condition": "customers.first_paid_at >= {start_date} AND customers.first_paid_at < {end_date}",
      "status": "confirmed"
    }
  ],
  "unresolved_terms": []
}
```

### 5.4 `plan_data_query`

This tool plans tables, metrics, joins, filters, and ambiguity questions. It does not execute SQL.

Input:

```json
{
  "space_id": "demo_company.revenue",
  "question": "지난달 신규 고객 순매출을 캠페인별로 보여줘",
  "role": "marketing_analyst"
}
```

Output:

```json
{
  "intent": "revenue_by_campaign",
  "required_terms": ["term.new_customer"],
  "required_metrics": ["metric.net_revenue"],
  "candidate_tables": ["customers", "payments", "campaigns"],
  "join_recipes": ["join.payments_customers", "join.payments_campaigns"],
  "filters": ["last_month", "new_customer"],
  "policy_notes": ["PII columns are blocked for marketing_analyst."],
  "ambiguities": [],
  "execution_allowed": false
}
```

### 5.5 `validate_sql`

Input:

```json
{
  "space_id": "demo_company.revenue",
  "sql": "SELECT campaign_id, SUM(amount) FROM payments GROUP BY campaign_id",
  "role": "marketing_analyst"
}
```

Output:

```json
{
  "valid": true,
  "execution_allowed": false,
  "checks": {
    "select_only": "pass",
    "multi_statement": "pass",
    "allowed_tables": "pass",
    "blocked_columns": "pass"
  },
  "referenced_tables": ["payments"],
  "referenced_columns": ["payments.campaign_id", "payments.amount"],
  "warnings": ["SQL was validated but will not be executed by the MVP server."]
}
```

Failure output example:

```json
{
  "valid": false,
  "execution_allowed": false,
  "checks": {
    "select_only": "fail",
    "multi_statement": "fail",
    "allowed_tables": "unknown",
    "blocked_columns": "unknown"
  },
  "errors": [
    {
      "code": "SQL_MULTI_STATEMENT_BLOCKED",
      "message": "Only a single SELECT statement is allowed."
    }
  ]
}
```

### 5.6 `record_feedback`

Input:

```json
{
  "space_id": "demo_company.revenue",
  "feedback_type": "missing_context | wrong_term_resolution | sql_validation_issue | user_note",
  "message": "순매출 정의에 쿠폰 할인 제외 여부가 명확하지 않습니다.",
  "related_card_ids": ["metric.net_revenue"],
  "severity": "low | medium | high"
}
```

Output:

```json
{
  "recorded": true,
  "feedback_id": "fb_20260508_000001",
  "path": ".runtime/feedback/demo_company.revenue.jsonl"
}
```

## 6. SQL Guard MVP Rules

Required checks:

1. single statement only
2. statement type must be `SELECT`
3. referenced tables must be in `allowed_tables`
4. referenced columns must not be in `blocked_columns`
5. output must explain validation decisions
6. output must set `execution_allowed: false`

Blocked examples:

- `DROP TABLE customers`
- `SELECT * FROM customers; DELETE FROM customers`
- `SELECT email FROM customers`
- `SELECT * FROM unknown_table`

## 7. PII / Sensitive Value Rules

- PII raw values must not be stored in Semantic Packs.
- PII raw values must not be embedded.
- For PII candidate columns, store only metadata, policy, and masking notes.
- Low-cardinality values may be stored only when they are safe categorical values.
- High-cardinality values should store pattern/statistics, not exhaustive raw values.


## 7.1 Human Confirmation Contract

Human-in-the-loop is represented as pack metadata and card status, not as an MVP UI.

Required contract concepts:

- `status: draft | reviewed | approved | confirmed` where applicable
- `confidence` for LLM/profiler hypotheses
- `source: profiler | llm | human | verified_query` where applicable
- reverse question `status: open | answered | dismissed`
- reverse question `answer` when a domain owner has responded

A card should not be treated as final business truth unless its status/source indicates human confirmation or verified-query evidence.

## 7.2 Context Retrieval / VDB Contract Boundary

The original plan's VDB/domain-memory concept is preserved as the direction for retrieval, but MVP retrieval is defined as local Registry search over Semantic Pack cards.

MVP retrieval may be lexical or structured. A production vector database, embedding pipeline, or vector index service is not required for MVP validity.

## 8. Validation Requirements

A pack is valid when:

- top-level metadata exists
- IDs are unique
- referenced IDs resolve
- policies reference known tables/columns
- metrics reference known tables/columns or explicitly marked external views
- SQL in verified queries passes MVP SQL guard or is marked as reference-only
- PII candidate columns do not include raw value dictionaries
- status/confidence fields distinguish draft from confirmed knowledge

## 9. Demo Dataset Mapping: Sample Superstore

The first concrete demo dataset should use the local Tableau Sample Superstore workbook:

```text
/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls
```

Verified workbook sheets:

| Sheet | Rows | Semantic role | Notes |
|---|---:|---|---|
| `Orders` | 10,194 | fact-like order line table | order/customer/product/category/sales/profit fields |
| `People` | 4 | region manager dimension | maps `Region` to `Regional Manager` |
| `Returns` | 296 | return lookup/fact | maps returned `Order ID` values |

Initial Semantic Pack candidates:

### Tables

- `orders` from `Orders`
- `people` from `People`
- `returns` from `Returns`

### Value dictionaries

Safe categorical columns from `Orders`:

- `Ship Mode`
- `Segment`
- `Country/Region`
- `Region`
- `Category`
- `Sub-Category`

Safe categorical columns from `Returns`:

- `Returned`

### Metric candidates

- `metric.sales` from `Orders.Sales`
- `metric.profit` from `Orders.Profit`
- `metric.quantity` from `Orders.Quantity`
- `metric.discount_rate` from `Orders.Discount`
- `metric.return_count` from `Returns.Returned = 'Yes'`

### Join recipe candidates

- `Orders.Region = People.Region`
- `Orders.Order ID = Returns.Order ID`

### Business term candidates

- sales
- profit
- discounted order
- returned order
- customer segment
- product category
- regional manager

### Safety notes

- Treat names such as `Customer Name` and manager names as sample data for demo purposes.
- Name-like columns in sample workbooks must still be flagged as PII candidates by contracts/tests.
- Do not create value dictionaries or embedding payloads from raw personal-name values.
- Do not generalize sample personal names into production PII handling.
- In Builder tests, prefer profiling categorical values and aggregate metrics over storing arbitrary high-cardinality raw values.

