# Stock Lobster System Contract

## 1. Architecture Layers (STRICT)

L0 Data Access Contract Layer
L1 Analysis Snapshot Layer
L2 Primitive Function Layer
L3 Label Snapshot Layer
L4 Strategy DSL Layer
L5 Signal Engine Layer
L6 Backtest Engine Layer

RULE:
- lower layer must not depend on upper layer
- upper layer only consumes lower layer outputs
- no cross-layer bypass allowed
- this system does not produce canonical factual data
- all factual data must come from external data production contracts

---

## 2. Core Data Assets

### ExternalDataContract
- describes available external data assets
- includes tables, fields, date formats, update frequency, quality status
- produced by external data production systems
- consumed by L0 only

### AnalysisSnapshot
- versioned analytical view built from external data contracts
- may include ma, atr, rs, volatility, volume, fundamental, macro, industry fields
- not a canonical factual data source
- must record external data dependencies

### LabelSnapshot
- deterministic pattern evaluation result
- must be versioned
- must be reproducible

### StrategyDSL
- only references LabelSnapshot fields
- no raw price data allowed

### StrategySignal
- generated ONLY by L5

### BacktestResult
- generated ONLY by L6

---

## 3. Primitive Rules (L2)

- must be pure functions
- input: AnalysisSnapshot only
- output: boolean or score
- no state allowed
- no direct external data access

---

## 4. Label Rules (L3)

- derived from primitives
- must be snapshot-based
- must include label_version + run_id

---

## 5. Strategy Rules (L4)

- only operate on LabelSnapshot
- must be deterministic
- must support versioning

---

## 6. Agent Rules (L7/L8 if used)

- agents cannot produce factual data
- agents cannot modify external data
- agents cannot become a source of truth
- agents cannot compute canonical features
- agents cannot modify primitives
- agents cannot bypass DSL or backtest engine
- agents can propose candidate primitives, labels, and strategies
- agents only orchestrate tools, data access, analysis, explanation, and review workflows
