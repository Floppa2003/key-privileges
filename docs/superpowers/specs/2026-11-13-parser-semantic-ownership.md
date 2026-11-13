# Parser semantic ownership repair

## Goal and authority

The user asked to fix the seven reproduced deterministic-parser defect groups and continue through verification and independent review. Prior session authorization includes updating the working GitHub/Sheets pipeline. This specification defines the finite acceptance surface; it does not claim understanding of arbitrary prose or all future upstream layouts.

Base: `23c5e7da30c1f96c6a9d700c948836587e8f28df`; normalizer before repair: `1.0.5`.

## Required outcomes

1. A denied benefit stays denied with ordinary modifiers: `Скидка 10% больше не действует`, `Скидка 10% временно не предоставляется`. Supported source-specific fields must also preserve denial, including Utair's `двойные мили больше не начисляются` and Bootwood's `Не начисляется 1 миля за каждые потраченные 70 руб.`. An inactive-only public record must not reappear as a usable catalogue offer merely because its original text contains a benefit word.
2. Source-owned mileage formulas preserve complete bounds: `До 2 миль за каждые потраченные 70 руб.` creates an upper bound, not an additional exact rate. `От 1 до 2 миль за каждые потраченные 70 руб.` creates the range without an exact upper endpoint. Full source evidence remains available.
3. `Промокод OLD10 больше не действует. Примените промокод NEW10.` exposes only NEW10 as a code to use. Explicit cancellation and `Не используйте` have the same effect. Source text is retained. A product exclusion (`Промокод NEW10 не действует на алкоголь`) preserves the code and exclusion.
4. `Скидка 20% на первый заказ от 5000 ₽, скидка 10% на повторный заказ от 2000 ₽.` links each minimum only to its own benefit. Comma, ordinary sentence boundary, semicolon and line break variants agree; decimals and `руб.` remain intact.
5. `Скидка 10% при сумме заказа не более 5000 рублей.` does not produce a reward cap. The amount belongs to the purchase. Preserve it as `maximum_amount_reference` unless a justified existing schema type is more precise. Real reward caps continue working.
6. `Скидка 10% на меню. Акция не действует на алкоголь.` remains visible, including when both sentences occupy the benefit field. Complete closure remains excluded. Moving an exclusion between benefit and conditions must not change the offer's eligibility meaning.
7. `Введите промокод NEW10 НА САЙТЕ.` produces NEW10; uppercase instructions `ПРИ ЗАКАЗЕ` and `ДЛЯ ЗАКАЗА` cannot extend an unquoted code. Existing real multiword codes (`MOSKVICH MAG`) and explicitly quoted literals (`«NEW10 НА САЙТЕ»`) remain valid.

## Global constraints

- Change deterministic parsing, normalization and catalogue projection only; do not change LLM behavior, providers, schedules, authentication, access controls or dependencies.
- Do not hardcode business amounts, coupon literals, record IDs or partner exceptions for these fixes. Existing source-template identity checks remain valid.
- Preserve source text, evidence, raw record identity, observation timestamps, stable IDs and private/manual data. No private workbook exports or identifiers, credentials or browser data in public git/artifacts.
- Resolve each numeric/coupon occurrence in its own clause/component; an unrelated denial or sibling offer must not erase a live benefit.
- Preserve actual product exclusions, real reward caps, payment amounts, valid multiword/quoted codes, existing source-specific scopes and supported number formats.
- Re-normalization of retained source rows must not resurrect a contradicted stale structured field or cancelled/malformed code when the complete original evidence is present. Do not guess missing source facts.
- Use regression tests observed failing before code edits, real source/publication/common/catalogue entrypoints, and literal independently derived expectations.
- Ship with normalizer `1.0.6`; public record schema stays compatible.
- Final acceptance requires green Python and Node suites, reviewed replay differences on an immutable public corpus, independent scoped and whole-branch review, CI on the final revision, and readback of the last production publication.

## Architecture and verification

Keep source ownership in source adapters; share existing clause/polarity machinery rather than inventing branded numeric exceptions. Source-specific structured extraction and common lexical extraction must agree on whether an occurrence is positive and whether its amount is exact or bounded. Prefer small changes in existing ownership helpers over a broad parser rewrite.

Use the latest immutable public collector artifact for baseline/treatment normalization at the same assessment date. Serialize source rows once using the baseline, preserve those exact inputs for both revisions, and compare semantic projections and reader rows with version/hash noise separated. Review every changed semantic record and every removed reader row. A replay does not constitute fresh upstream collection.

After integration, refresh the supported source templates affected by source-owned extraction, then re-normalize all retained workbook inputs using the existing workflow. Verify run SHA, artifacts/source coverage, source-text preservation and native audit/catalogue manifests. Access failures remain visible and are not relabelled parser success.
