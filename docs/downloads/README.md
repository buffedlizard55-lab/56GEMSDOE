# Archived research downloads — no corrections-lane TIFF cleared for submission

> **STOP for the corrections lane:** no TIFF from the active corrections review is safe to submit.
> These files are preserved for research and reproducibility, not as submission recommendations.
> The active corrections primary fails the
> registry proximity gate and the strict sample-footprint format check. No slot has been used.

## Published files and current status

| File | Lane / purpose | Strict local format result | Lane / experiment result | Submit? |
|---|---|---|---|---|
| `gems56-corr-crestgt2px-20261009T051209Z-78fc86ad-nan.tif` | Earlier corrections run; 6,504 dots | **PASS against the hash-pinned bridge sample only**: finite/NaN mask and NaN nodata match | Literal >70%-within-3-px registry trigger; negative | **NO** |
| `h56-corr-snap200cm-20261009.tif` (+ `.zip`, `.json`) | Active corrections primary; 1 dot | **FAIL**: 7,111,787 non-NaN cells outside the sample footprint; nodata tag is absent | Registry DUPLICATE/STOP: 1.0 directed near-3-px fraction (>0.70); no artifact-level holdout evidence | **NO** |
| `h56-corr-snap100cm-20261009.tif` (+ `.zip`, `.json`) | Active corrections sensitivity; 14 dots | **FAIL**: same outside-mask and nodata problems | Not cleared; historical registry gate receipt has offenders | **NO** |
| `h56-disc-multi-b25000-20261009-20261009T165646Z.tif` (+ `.zip`, `.json`) | Later discovery-lane archive; 25,000 dots | **FAIL**: same outside-mask and nodata problems | Negative holdout / registry stop; discovery is outside the active corrections lane | **NO** |

## Separate dotted-ridge lane artifact (not adjudicated by this review)

[Download the dotted-ridge TIFF added by PR #11](h56-final-dotted-ridge-d2p8-20261009T190421Z.tif).
It is a distinct, later output from outside the active corrections lane. PR #11 carries its own
run receipts and submission-status claims; this corrections review did not independently revalidate,
select, or promote it. Its status is therefore **not adjudicated here**. Do not interpret the
corrections-lane STOP below as either clearance or a rejection of that separate artifact. The
preserved parallel round-2 index is [`../discovery-index.html`](../discovery-index.html); its banner
marks it as archival, and its status/receipts are separate from this corrections review.

For the active primary, the pre-placement surface check found no rank-correlation trigger among
readable entries (max ρ=0.005135), but 36/944 priors were unreadable, so it is not a complete
clearance. The final-dot check separately triggers the >70%-within-3-px stop on 263/944 priors
(directed fraction 1.0). The sensitivity final-dot check triggers on 175/944. Neither is cleared.

The old build receipts marked the 1-dot, 14-dot, and 25,000-dot files as passing because the former
validator did not compare their full finite/NaN mask and nodata tag to the sample. The receipts now
retain the old result as `legacy_validator_ok` and include the strict independent report. Trust the
strict report, not the historical field.

## The one-click file on the project home page

The one-click link is the earlier 6,504-dot GeoTIFF because it is format-conformant to the pinned
bridge sample. It is labeled **archive / technical inspection only — NOT safe to submit** because its
literal registry proximity trigger failed. Its current file SHA-256 is
`08de79ce298c74dc5fcc006c1bde2bf117203e31b3a5ba3e943c1d05154781d7`.

## Scope and limitations

- All local format passes are against `data/sample_submission.tif`, a hash-pinned owner-bridge copy.
  Its contents are cell-for-cell equal to `existing_faults.tif`, while the official public problem
  page describes a total-fault-absence sample. The official data-tab hash/content must be checked by
  a logged-in human before relying on this footprint.
- The official rules require one-band float32, EPSG:32611, 100 m, same bounds, [0,1] values, and
  null/NaN outside the bounds. Local validation is not proof of upload acceptance.
- No corrections-lane candidate is selected or promoted. Do not edit, sanitize, repackage, or upload
  a corrections archive as a workaround for a failed scientific or registry gate.
- The dotted-ridge artifact linked above is a separate lane; its status is not adjudicated by this
  corrections log. Read PR #11's receipts and status wording separately.

Revalidation is documented in [`docs/review/2026-10-09.md`](../review/2026-10-09.md) and the
active-lane card [`evidence/run_card.json`](../../evidence/run_card.json). The user-prompt archive and
limitations are in [`README.md`](../../README.md).
