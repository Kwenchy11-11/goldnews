# Polymarket Market Matcher Design

**Purpose**
Build a deterministic matcher that maps an economic event to the most relevant Polymarket markets using only the existing `PolymarketClient` interface. The matcher must be explainable, reproducible, and safe against false positives. It should return the top matching markets or `no_consensus` when relevance is weak.

**Inputs**
- `event_name` (str): Human-readable event title (e.g., "US CPI")
- `category` (str): Event category (e.g., inflation, labor, fed_policy)
- `release_time` (datetime): Event release timestamp
- `country` (str): Country code/name (e.g., "USD", "US")

**Outputs**
- `MarketMatchResult`
  - `matches`: List of top matches (max `MAX_MATCHES`)
  - `no_consensus`: bool
  - `threshold`: int (current relevance threshold)
  - `rejected`: List of rejected candidates with reasons

**Data Model**
- `MarketMatch`
  - `market`: `MarketData`
  - `relevance_score`: int (0–100)
  - `score_breakdown`: Dict[str, float] (each weighted component)
  - `matched_queries`: List[str]
  - `rejection_reasons`: List[str]

- `MarketMatchResult`
  - `event`: Dict with normalized input fields
  - `matches`: List[`MarketMatch`]
  - `no_consensus`: bool
  - `threshold`: int
  - `rejected`: List[`MarketMatch`]

**Constants (tunable)**
- `DEFAULT_RELEVANCE_THRESHOLD = 60`
- `DEFAULT_MIN_LIQUIDITY = 1000`
- `DEFAULT_MIN_VOLUME = 1000`
- `MAX_MATCHES = 3`
- `MAX_SEARCH_RESULTS_PER_QUERY = 10`

**Deterministic Query Generation Rules**
1. Normalize text inputs to lowercase, strip punctuation, collapse whitespace.
2. Generate a base keyword set from `event_name` plus category-specific terms.
3. Add country variants (`us`, `united states`, `usd`) when country is US/USD.
4. Build a query list with de-duplication and stable ordering.
5. Use `PolymarketClient.search_markets(query, limit=MAX_SEARCH_RESULTS_PER_QUERY)` for each query.
6. Merge results by `market_id`, tracking which queries matched each market.

**Category-Specific Query Examples**
- CPI / inflation:
  - "us cpi", "consumer price index", "inflation rate", "core cpi"
- NFP / labor:
  - "nonfarm payrolls", "nfp jobs", "us jobs report", "employment report"
- FOMC / Fed rates:
  - "fomc", "fed rate decision", "federal reserve rate", "fed meeting"
- Unemployment:
  - "unemployment rate", "jobless rate", "us unemployment"
- Retail sales:
  - "retail sales", "us retail sales", "consumer spending"
- GDP:
  - "gdp", "gross domestic product", "us gdp growth"

**Hard Gates (Reject Before Scoring)**
1. **Closed markets**: Reject if `market.closed == True`.
2. **Low liquidity**: Reject if `market.liquidity < DEFAULT_MIN_LIQUIDITY`.
3. **Low volume**: Reject if `market.volume < DEFAULT_MIN_VOLUME`.
4. **Weak title/question relevance**:
   - Require at least one strong event keyword OR category keyword present in the title/question.
   - Avoid generic markets (e.g., "Will the Fed cut rates this year?") unless the event category is Fed/FOMC or relevance is clearly strong.
5. **Impossible end_date**:
   - Reject if `end_date` exists and is **before** `release_time`.
   - Do **not** reject missing `end_date`.

**Scoring (Only After Gates)**
Weights are constants (tunable later):
- Title/question keyword match: **35%**
- Category/query intent match: **25%**
- End-date proximity: **20%**
- Volume/liquidity quality: **15%**
- Description/tags support: **5%**

Scoring logic summary:
- **Title/question match**: token overlap against event keywords and category keywords.
- **Category/intent match**: bonus for explicit category terms (e.g., "CPI", "NFP", "FOMC").
- **End-date proximity**:
  - If missing end_date: apply a confidence penalty (reduced score, not rejection).
  - If end_date is after release_time but far in the future: penalize (do not reject unless clearly unrelated).
  - If end_date is close to release_time: score higher.
- **Volume/liquidity quality**: scaled score above minimums to favor deeper markets.
- **Description/tags support**: small bonus if tags/description include event keywords.

**Relevance Tiers and Thresholds**
- 80–100: Strong match, safe to use as consensus input
- 60–79: Usable, mark moderate relevance
- 40–59: Weak match, default to `no_consensus`
- 0–39: Irrelevant

`DEFAULT_RELEVANCE_THRESHOLD = 60` determines whether a match is returned. This should be configurable later via config/env overrides, but the initial implementation uses the constant.

**No-Consensus Behavior**
- If no candidate scores >= threshold, return `no_consensus=True` and include rejection details for all candidates.
- If there are no search results at all, return `no_consensus=True` with a single "no results" reason.

**Debuggability (Required)**
Every candidate (accepted or rejected) must preserve:
- `matched_queries`
- `score_breakdown`
- `rejection_reasons`
- `raw market_id` and `question`
- `final relevance_score`

**Edge Cases**
- Missing `end_date`: penalize proximity score only, never hard-reject.
- Stale `end_date`: reject if before release_time; otherwise penalize by distance.
- Ambiguous category: rely more heavily on event_name keyword expansion.
- Multiple query hits for the same market: merge and keep best score + combined reasons.
- Empty API responses: short-circuit to `no_consensus`.

**Test Plan**
- CPI match (strong): high relevance, passes threshold, top result ordered correctly.
- NFP/labor match (strong): passes threshold with correct category/keyword weights.
- FOMC/Fed match: passes with category intent terms.
- Irrelevant markets: rejected by title relevance gate.
- Empty API results: `no_consensus=True`.
- Closed market: rejected by hard gate.
- Low liquidity/volume: rejected by hard gate.
- Missing end_date: not rejected, but lower proximity score.
- Stale end_date (before release_time): rejected.
- Far future end_date: penalized but not auto-rejected.
