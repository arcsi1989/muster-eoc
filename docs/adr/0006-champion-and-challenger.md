# Champion and challenger: shadow models, human-approved promotion

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

Status: accepted, 2026-10-30 (CR-01 C6 calibration, tickets 09–10; CR-03 C2 challenger, tickets
32–34).

## Context

The rule-based risk score (lognormal fragility curves) is transparent but its published curves are
illustrative. Two ways to improve it exist in the prototype: calibrating the curves on a past storm
(Storm Delta) and a gradient-boosted challenger trained on 20 synthetic past storms. Either could
make the ranking better or worse, and the ranking drives the playbook check and the decision
package. A model that silently replaces the ranking would break "humans approve" and every demo
fact.

## Decision

- **Risk model interface** (`backend/muster/risk/model.py`): `RuleBasedModel` (`risk/score.py`) and
  `ChallengerModel` (`challenger/model.py`) both turn an asset's exposure into a failure
  probability. Consequence and confidence stay outside the model.
- **Model versions** (`calibration/versions.py`): every model is a version with a status. Version 1,
  the published curves, is approved at load. A calibration run stores a `proposed` version. The
  challenger is registered at startup in `shadow`.
- **Champion**: the latest approved version of either kind ranks the assets; each score records
  its version. Approval never rescores an advisory already issued.
- **Shadow**: while the challenger is not champion it scores every advisory in shadow
  (`shadowscore` table); shadow scores never drive the ranking, the playbook check or the package.
  The champion-and-challenger page shows the disagreements.
- **Promotion rule** (`challenger/promotion.py`, `config/models.yaml`): on Storm Delta, held out of
  training and tuning, the challenger must beat the published curves' Brier score and top-decile
  capture by set margins with calibration error under a limit. Passing only lets it be **proposed**;
  the Planning Section Chief, the Director or the Incident Commander approves it through the same
  model-version path as calibrated curves. Never automatic; proposal and approval are audited.

## Consequences

- The rules stay champion in the demo because nobody approves the challenger; promoting it is a
  deliberate, logged act, and the latest approval of either kind wins and names what it replaced.
- Explanations, copilot tools and demo seeds are unchanged while the rules are champion; a promoted
  challenger changes p_fail, risk and rank only.
- The challenger's accuracy is measured on synthetic data with one planted effect; it shows the
  discipline (leave-storms-out folds, a held-out storm, the same metrics for both), not skill on
  real assets.
- The committed model (`data/models/challenger.pkl`) is a pickle tied to the locked scikit-learn
  version; without it the backend runs with no shadow scoring.

## Alternatives rejected

- **Automatic promotion when the rule passes.** Breaks "humans approve"; a metric margin on one
  storm is evidence, not a decision.
- **A/B ranking (some advisories by each model).** The EOC needs one ranking per advisory.
- **Replacing the curves with the challenger outright.** Loses the transparent factor breakdown the
  explain panel shows, and needs trust the prototype has not earned.
- **Checking promotion on the leave-storms-out folds.** Those storms are the training history;
  Storm Delta is the only storm never used to fit or tune anything.

## Links

- `docs/decisions.md`: 2026-10-29 calibration and model versions (tickets 09–10); 2026-10-30
  synthetic history and challenger training (ticket 32), challenger in shadow and its review (ticket
  33), champion and challenger view (ticket 34).
- Code: `risk/model.py`, `risk/score.py`, `calibration/`, `challenger/`, `replay/service.py`
  (`advance`); results `docs/eval/challenger_results.json`.
