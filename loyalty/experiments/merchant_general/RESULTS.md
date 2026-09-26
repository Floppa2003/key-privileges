# General merchant researcher — 25 September 2026

## Decision: prototype retained; production acceptance blocked

The new runtime has no merchant-specific CSS, selectors, URL paths or extraction branches. Input is a known official homepage, merchant identity and target programme/aliases. Search and bounded navigation find source-owned pages; one extraction prompt and one quote checker are used for all v3 targets. This is progress beyond individually configured adapters, NOT a reliable universal discount extractor.

Nothing is connected to the production source registry, publisher, request.json or Google Sheets. Every candidate and semantic-review result has publication_allowed=false. No existing parser or recurring schedule was replaced. This work belongs on a draft branch/PR, not a production merge.

## Live v3 evaluation

Eight unconfigured domains were listed from earlier leads; four were actually read with the final common v3 prompt. This selection is biased, not model-unseen or representative of all merchant sites. London/Grand Karat were development probes. ARTSTUDIO and Алые паруса were not read with v3. Unrun targets and pending pages are not counted as absent offers or successes.

| Target | Actual v3 reads | Source/evidence result | Semantic conclusion |
|---|---:|---|---|
| ACADEMIA | News index + linked full article | Generic navigation found the actual article without a configured offer URL. Both model outputs failed literal scope checks. | Useful public conditions found; structured output not accepted. The article's programme name was quoted from outside the model-selected paragraph. |
| ЭЛКОМ | Homepage | Relevant EKP paragraph obtained; code-delivery quotation lay outside the model-selected scope. | Review required. Do not silently merge sections or invent the unpublished code. |
| МИСП | Source-discovered news page | Model output passed quote checks and retained payment with accumulated points. | Manual context review found a useful proposition, not unconditional free admission. Full redemption rules/required points remain unread; second model review not run. |
| Теплоход СПб | Source-discovered article | Quote checks passed on genuine words about event gifts. | False positive: a completed school event is not a reusable cardholder benefit. Separate same-provider reviewer also incorrectly returned supported. |

Totals: four domains, five acquisition pages, two quote-checked candidates and three scope-check failures. One additional live semantic-review request reread the Teplohod page. No automatic publication. Do not report two validated offers: one of the two quote-checked candidates is semantically wrong.

### Verified navigation example

ACADEMIA homepage input -> generated domain-restricted search -> /about-news -> real programme article link in multiline Markdown -> /about-news/programma-loyalnosti-ekp. The model omitted followup_links; the generic source-link scanner still found the article. It obtained the public paragraph with 15%, three named hotels, specified base tariffs, website/telephone booking and an app-supplied code. The code itself is not published. Scope verification rejected the model output rather than rewriting its quote to pass.

## Blocking semantic counterexample

See semantic-counterexample.json. The extractor misclassified gifts for schoolchildren at an already completed event as an EKP offer. All quoted words were real. A second task using the same provider and an explicit instruction to reject past-event gifts still returned supported. Its reason merely repeated programme partnership and ticket distribution.

The intended evaluation verdict is reject. Recorded provider verdict is supported. This evaluation FAILS. A second request is not an independent model and model agreement is not validation. The offline semantic-quality job deliberately reports this disagreement as failure; it does not make a new inference call. Functional Python tests remain a separate signal.

Do not fix this by adding a Teplohod domain exception, changing the expected label, or counting the always-false publication flag as successful semantic extraction. Correctness currently depends on manual context review. Automatic publication must remain disabled.

## Transport and version history

v2.1 commit014442eac83c224298232c480c2e92f54a017570 was checked by run36064201372/job107849997495: 1401 Python +7 KEY tests passed. Its actual keyless Firecrawl REST probe failed with provider_http_403 before source acquisition. Green test execution did not mean successful collection. Artifact10834853462, ZIP SHA25609bf242638c044f26fb70556cf3ddf032c83c5f19ffd1782395f621cdc96f461, was downloaded, CRC checked and code matched.

Earlier JSON-format requests returned source HTTP200 and Markdown, but json=null with a provider schema error; explicit schema submission was rejected by the connector argument schema. The cause inside the provider is not established. v3 switched all targets to the same freeform question mode and strict local JSON decoding, preserving invalid outputs as failures. No per-merchant prompt repairs.

The current v3 core plus reviewer passed 58 local functional tests. A new CI run must separately verify the exact committed files. Do not apply v2.1's test count to v3. Network probe is removed from the updated branch-only test workflow; unchanged keyless403 will not be replayed.

## Evidence and cost limits

Local receipt files preserve exact relevant source excerpts, model answers, request identity and selected provider metadata. They are explicitly marked source_excerpt_not_full_page. Their hashes are hashes of transcribed excerpt records, not original HTTP bytes or complete provider responses. The conversation contains full responses; file capture was not a fully automatic raw-response export. A mistaken truncated search-description transcription affecting museum ranking was corrected from the actual tool response and the erroneous local record retained separately. No model answer was edited to turn failure into success.

The four retained target searches report2 credits each, five v3 acquisition calls5 each, and the semantic call5:38 reported credits for this retained path, including a reused ACADEMIA search. This is NOT the entire iteration's consumption or a reconciled account debit: earlier development, errors and other requests are additional. No paid upgrade/subscription was requested. A working connected MCP is not proof that a keyless or API-key REST runner works unattended.

## Remaining implementation limits

Known homepage required; no bare-name domain resolution. Three pages/depth2 is bounded discovery, not exhaustive coverage. Same-host links only; linked external rules, image-only/PDF terms and authenticated codes are not generally solved. Source-only heading windows use the next heading rather than semantic section hierarchy; nested redemption sections can split. Source-scope checking is conservative and sometimes rejects useful outputs. The query model/provider is not pinned or calibrated. Page policy, actual redirect handling and DNS protections partly belong to the provider; lexical URL checks are not a complete network-security audit.

## Next acceptance gates

1. Use a tested authorized acquisition path with automatic full response receipts and a measurable budget, without treating the connected MCP session as scheduled REST access.
2. Improve the shared document/field contract: source-defined structural blocks and explicit relationships for programme, audience and redemption instead of model-invented section text. Preserve a failure when the relationship is not proved.
3. Evaluate an independently chosen semantic verifier/stronger model or review process against a frozen set of new positive and negative domains. Require explicit programme/audience/action evidence; a blacklist of event words is insufficient.
4. Only after measured precision, omissions, abstention, costs and independent destination-readback gates should a publication adapter be considered. Existing deterministic adapters stay as useful baselines.

Do not repeat the known provider403 or completed source reads just to recover context. This prototype's negative semantic result is a real next-work boundary, not proof that a general solution is impossible.
