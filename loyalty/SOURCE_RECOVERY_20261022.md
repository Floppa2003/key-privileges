# Source error recovery — 22 October 2026

Baseline: run 39776874567 (125 routes, 22 failed/partial reports), execution
commit debde8a59d8e0154506f2b8227eecee3003261bc. Code changes are independent of
the experimental model pipeline in PR #90.

## Parser corrections

- HSE: explicit anchors reserve their own sections before heading-only matching.
  This includes named sections missing from the current catalogue. Ambiguous
  heading-only joins remain observations; unrelated cards continue. No name
  exception or past percentage determines acceptance.
- Smartavia: read the plan's own title block; a line break between the label and
  its value is not a missing plan. Unrecognized plan names remain supported.
- Mantera hotel: distinguish hotel participation from customer membership;
  multiple affirmative statements do not conflict. A negative participation
  statement cannot become affirmative evidence.
- Park&Fly: support the current single article container as well as the old
  layout, not the entire body containing unrelated promotions.

## Transport and diagnosis

- Share only successfully read robots rules within one browser run and origin,
  with a five-minute TTL and serialized concurrent fetches. Retain Disallow and
  crawl-delay; failed policy reads do not become cached permission.
- Scoped HTTP reader retries only connection errors/timeouts, at most three
  attempts within the original deadline. HTTP refusals, Retry-After, TLS and
  authentication are not bypassed.
- PrimBank publicly documents its national-CA migration at
  https://info.primbank.ru/. Reuse the existing pinned CA bundle for the exact
  public tariff URL and its robots file. Do not modify system trust, disable
  verification, or access a customer account. Continue using the existing PDF
  parser and preserve earlier standard-TLS records without claiming new trust.
- Emit bounded error codes, categories, HTTP status, selector/match count and
  response hashes where available. Arbitrary exception text is not public
  telemetry. It may contain tokens or response contents.
- Zero records with errors is failed, not partial. Health lists every selected
  route; inventory-completeness checks remain separate. The four implemented
  legacy special routes no longer have misleading mode=probe registration.

## Acceptance and limits

Run full Python and KEY suites; run original layout/ownership counterexamples;
re-run the complete registered collection without Google credentials or Sheets
writes. Preserve a code snapshot, logs and normalized source reports. A green
regression job is not a claim that every remote site works.

The remaining external failures from the baseline (403, unavailable robots,
404, authentication and transport) must be re-read. Do not substitute a cached
search snippet, enable a paid proxy, weaken TLS/robots, silently delete a source
or claim an access probe is a working catalogue extractor. Some catalogues use
separate existing import workflows; their results are not inferred from this
collector's status.
