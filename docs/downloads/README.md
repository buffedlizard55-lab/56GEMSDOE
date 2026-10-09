# Historical correction-lane artifacts — NOT SAFE TO SUBMIT

Two TIFs are present in this directory because an earlier run built and registered them. **Safe to download: yes, for audit/research inspection only. Safe to submit: NO.** They are retained as historical artifacts, not approved outputs, and neither must be uploaded to DrivenData.

| Artifact | Contents | SHA-256 | Status |
|---|---:|---|---|
| `h56-corr-snap200cm-20261009.tif` | 1 dot; built with the null-calibrated crest-strength floor disabled | `65635a536d5195532691dbe02c04f796ea6b9e7123cd4c9cf5a8f930b351d20b` | NOT SAFE TO SUBMIT |
| `h56-corr-snap100cm-20261009.tif` | 14 dots; 1 px sensitivity threshold below the ~2 px lane rule | `e3285854e73ae4ba3fce8faea64940fdc4bee3b702eb52d2530a67fb60195196` | NOT SAFE TO SUBMIT; sub-threshold diagnostic |

The decisive calibrated receipt reports **0 of 21 qualifying corridors**, so the corrections-lane finding is negative and no evidence-supported correction should be emitted. The primary's one dot does not change that result: it came from a build path that did not apply the strength threshold measured from the random no-trace null. The 1 px sensitivity file is below the requested correction bar. Neither has been promoted or uploaded; no organizer receipt or score exists.

The previous local gate reported single-band float32, [0,1] values, and the expected grid. That local check does not prove exact portal compatibility. The official submission-format page says data outside the training bounds is null or NaN and the official sample uses NaN there. The shared `gems52` writer/grid/gate currently require every cell to be finite. Historical files fill the outside with zeros to satisfy that local policy, so they are not certified against the official exterior convention. No organizer upload has tested this. Upstream issue: [GEMSDOE52 #65](https://github.com/buffedlizard55-lab/GEMSDOE52/issues/65).

## Receipts

- [Current status and blockers](../../evidence/submission_status.json)
- [Historical build receipt](../../evidence/build_corrections_v1.json)
- [Historical HOLDOUT-DTI receipt](../../evidence/holdout_corrections_v1.json)
- [Registry screen](../../evidence/registry_screen_v1.json)
- [Official submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format)
- [Conditional upload instructions](../submit.html)

Do not use the historical submission names or notes in a future upload. Only a new artifact that passes the corrected shared writer, evidence, holdout, uniqueness, and exact format gates may be labelled upload-ready. A weekly submission slot remains a separate decision and has not been selected.
