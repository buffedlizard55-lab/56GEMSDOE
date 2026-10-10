# Why 0.2778 — the metric, the mechanism, and the irregularity

PhD-level note, 2026-10-09. Every number is labelled: **ORGANIZER-CONFIRMED** (from the
submission-page receipt), **MEASURED** (this repo, official data), **HOLDOUT-DTI** (local,
simulated truth), or **USER-REPORTED** (sibling owner, unauthenticated).

## 1. The metric is a budget, and it reduces exactly

The official metric (DrivenData problem page 967) is a distance-weighted Tversky index with
α=0.2 (false-positive weight), β=0.8 (false-negative weight) and a 300 m triangular
kernel (R=3 px at 100 m). With T = TP_w (kernel-weighted true-positive mass), F = FP_w
(kernel-weighted false-positive mass) and K = |G| (hidden truth pixels):

```
DTI = T / (α·(T + F) + β·K)      (verified 1e-15 against the official formulas and the
                                   official worked example 3.00/(3.00+0.2·1.89+0.8·2.00)=0.60)
```

Two consequences (derived by the GEMSDOE32 sibling, re-derived here from the same official
text):

* **Marginal theorem.** Adding one unit of prediction mass anywhere raises the denominator by
  exactly α = 0.2 (it enters F, and T is unchanged unless the mass lands on truth). A dot
  therefore pays iff its kernel credit exceeds α·DTI — at DTI 0.26 that is 0.052, i.e. the dot
  must land within ~284 m of a hidden truth pixel (triangular kernel: credit 1−d/300 m).
* **The masking corollary.** The live scorer masks known-fault pixels pixel-exactly (organizer
  forum thread 11516, cited by the sibling knowledge docs). The published catalogue is known
  faults. Therefore a dot on the catalogue line earns nothing and costs 0.2 — it is a pure
  false positive. (The sibling group measured the same behaviour live: their quarantined
  heatfield with 14.8% of dots on the catalogue scored lower, and their IR-32-INSTR-01 probe
  showed one on-catalogue dot collapsing their drift instrument 0.14801→0.07831.)

## 2. What h33-h33-2-b2 embodies

USER-REPORTED family (GEMSDOE32, owner-reported; not independently authenticated):

| emission | predicted px | reported live DTI |
|---|---|---|
| solid surface (H19-5 field) | 121,131 | 0.1922 |
| dotted d1.5 | 60,069 | 0.2477 |
| dotted d2.8 | 44,090 | 0.2600 |
| **h33-2-b2 = dotted d2.8 minus every dot within 2 px (200 m) of the catalogue** | **37,654 (0 on-catalogue)** | **0.2778 per the brief; 0.2747 modelled projection per the owner site** |

The mechanism is the marginal theorem applied to emission: thinning a thick surface while
keeping its geometry removes mass that was already covered, raising credit per emitted pixel,
until the marginal pixel's credit equals the break-even bar α·DTI. The group measured that bar
empirically at 0.0548 credit/dot; the formula gives 0.2·0.26 = 0.0520. Two independent routes,
one answer. Deleting every dot within 200 m of the catalogue removes pure-loss mass (masked
known faults), which is why the pruned file outranks its unpruned base.

## 3. The irregularity (flagged — do not repeat it)

The brief attaches **0.2778** to `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`. Checked against
the sibling's own pages: the GEMSDOE32 site and README label that artifact **UNSCORED**, give a
**modelled projection of 0.2747**, and state that no organizer score exists for it. The
GEMSDOE51 sibling's audit (`evidence/score_attribution_audit.json`) calls the 0.2778
attribution "unsupported and contradicted". No organizer receipt maps that file to any score.

What is defensible: the *mechanism* above (which any file in that family would exhibit).
What is not: that this exact file scored 0.2778, or any causal geological story for a public
score (a public DTI value cannot reveal a method's causal contribution without the exact
scored TIFF, the hidden labels, and the weighted TP/FP terms).

Similarly: "0.3195 is the highest score right now" is **stale** — the verified 2026-10-04
snapshot (GEMSDOE32 `registry/leaderboard_snapshot_2026-10-04.json`) has #1 nchuzhoy **0.3262**,
#2 kinghorton42 0.3222, #3 DARD 0.3195; GEMSDOE51's one-time official-page check on 2026-10-08
found 0.3195 was not the page high. The brief's newer figure (0.3774, 2026-10-09) is
**user-supplied and unverifiable from this sandbox** (drivendata.org is not reachable from the
egress allowlist). Check the official leaderboard directly.

## 4. Can we beat it?

At the same emitted mass, the live leader needs ≈+25% mean credit per pixel (T 3,937→4,939 at
|G|≈7,905 implied by the family). No public catalogue can supply that — the newest public
compilation (QFaults+INGENIOUS v2) is already inside the given catalogue. The ceiling with
perfect trace knowledge is ≈0.78. The remaining levers are:

1. **A better field (detector).** Raising credit density of the top of the ranking. This
   session's corrections lane is exactly such a mechanism: the organizers confirmed that
   new-fault ground truth lies within 300 m of known traces as "corrections or modifications
   to existing fault traces" (forum 11516), and USGS-to-refined-trace discrepancies up to
   400 m are documented for north-central Nevada (Hermant, Kiersnowski & Bellanger, Stanford
   Geothermal Workshop 2025). Refined traces near known traces are in the hidden GT; the
   catalogue line itself is masked, so only the refined position scores.
2. **Genuinely novel faults.** The 2020 Mw 6.5 Monte Cristo rupture occurred on the largely
   unmapped Candelaria fault, inside the footprint (USGS field response, SRL 92(2A) 823–829).
   Novel-fault lanes (magnetic-gradient lineaments, radiometric alteration halos, basement
   edges, strain gradients) are preregistered on `docs/hypotheses.html`.
3. **Emission-side gains.** Nearly exhausted (the d1.5/d2.8/prune family brackets the optimum).

## 5. What this session built toward lever 1

The corrections lane (see `src/corrections.py`): perpendicular transects ±400 m on every
catalogue trace; strongest-crest offset of the DEM-scarp ridge (`det_elev_slope`) and of the
magnetic-gradient ridge (`tmi_hg`) per vector-catalogue record; LiDAR-calibrated crest
(1 m 3DEP: MAD 0.29 px); consistent offset > 2 px on 28/125 well-sampled records; emission on
the evidence-defined trace, off-catalogue. HOLDOUT-DTI (simulated truth, 26,813 withheld
positives): 0.31049 [0.282, 0.338] vs 0.00000 masked control and 0.01174 random.
Full derivation and tables: `docs/research.html`.
