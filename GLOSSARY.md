# SGW Storm Preparation

The language of the Emergency Operations Center (EOC) of a fictional utility preparing for a
hurricane, as used by the prototype. All names and data are fictional.

## Forecast and time

**Advisory**:
One issued hurricane forecast (track, intensity, cone, surge) at a given number of hours before landfall. The prototype replays five, one at a time.
_Avoid_: Forecast update, bulletin

**Scenario time**:
The clock of the replayed storm, counted as hours to landfall at the current advisory. Every playbook deadline runs on scenario time, not on wall-clock time.
_Avoid_: Real time, current time

**Activation level**:
The EOC's readiness stage: Monitor (Level 3), Prepare (Level 2) or Full (Level 1). It is the last level a person declared, never computed; the scenario starts at Monitor. The **proposed level** is the one the playbook's thresholds propose at the current scenario time (Monitor from T-120, Prepare from T-72, Full from T-48); when it differs from the declared level, the decision package carries an activation proposal (P-2.5).
_Avoid_: Phase, alert level, computed level

**Declaration**:
A person's decision to put the EOC at an activation level, taken on the activation proposal: the Director declares Level 3 and Level 2, the Incident Commander Level 1 (P-2.5). It records who declared, when (in scenario time) and why; the Full declaration starts the regulator notification clock (P-7.2).
_Avoid_: Activation, escalation (as a verb for what the system does)

**Operational period**:
The time between two advisories, during which one set of decisions and one situation report hold. The planning products are drafted for the next one.
_Avoid_: Shift, cycle

**Advisory context**:
What holds at the current advisory: which advisory is current (none before advisory 1), its scenario time, its activation level, whether the EOC is at Full activation, and who commands (Incident Commander or Director). A new advisory starts a new operational period, which resets the per-advisory flags (risk list reviewed, situation report approved).
_Avoid_: Current state, session state

## Playbook

**Clause**:
One numbered paragraph of the playbook (for example P-4.2), cited by its ID.
_Avoid_: Section, rule text

**Rule**:
The machine-checkable trigger for a clause: when it applies, to which entity, and what state satisfies it.
_Avoid_: Check, condition

**Rule inputs**:
The values the rules read at one advisory: the event fields (scenario time, declared and proposed activation level, hours since Full was declared, counts such as pumping stations in the top 25 that serve the treatment plant, the per-advisory flags) and, per asset and staging area, its data, exposure and operational state. Built by the playbook module only.
_Avoid_: Evaluation context, facts

**Prohibition**:
A rule that forbids field work at an entity (P-4.7) instead of requiring an action. It never becomes a finding on its own; it blocks actions.

## Findings and decisions

**Finding**:
The result of evaluating one rule against one entity at one advisory: satisfied, open, or in conflict.
_Avoid_: Alert, issue

**Re-evaluation**:
Evaluating one stored finding again after a state change at the same advisory (P-7.1 once the situation report is approved), and updating it with the new outcome. A playbook operation, called by the one step that writes decided operational state.
_Avoid_: Refresh, patch

**Gap**:
An open finding: the playbook requires something the current state does not show.
_Avoid_: Shortfall, violation, missing action

**Action**:
The remedy proposed for a gap, which a person approves or overrides.
_Avoid_: Task, recommendation

**Conflict**:
A finding where a required action needs field work that a prohibition forbids at the same entity. Only the Incident Commander decides it, and personnel safety prevails (P-8.2).
_Avoid_: Clash, exception

**Decision package**:
Everything put before the EOC for one advisory: what changed, the gaps with their proposed actions, the conflicts, and the draft situation report.
It is **open** from the moment its advisory is issued until the next advisory expires it; only an open package takes decisions, and items still undecided then close as not decided.
_Avoid_: Report, briefing pack

**Approval**:
A person accepting a proposed action. In the prototype the action then counts as done from that moment on.
_Avoid_: Sign-off, confirmation

**Override**:
A person declining a proposed action, with a recorded reason. The gap stays open and normally reappears at the next advisory.
_Avoid_: Rejection, dismissal

**Situation report**:
The written status issued once per operational period. It stays marked DRAFT until the Incident Commander approves it.
_Avoid_: Sitrep (in UI text), summary

## Planning products

**ICS-215**:
The operational planning worksheet drafted for the next operational period from approved field work only: per work assignment, its location, the resource kind it needs, how many are required, how many the operational state and staging data show available ("have"), the shortfall ("need" = required minus have), the staging area to report to and the requested arrival time. It stays DRAFT until released.
_Avoid_: Work plan, resource sheet

**IAP**:
The Incident Action Plan. The prototype drafts its objectives section: three to six incident objectives derived from the open findings, each citing its clause IDs. Code writes them from a template; a model may only reword them, and never their citations. It stays DRAFT until released.
_Avoid_: Action plan (alone), plan objectives

**Release**:
Taking the ICS-215 and IAP objectives out of DRAFT: two approvals in order, the Planning Section Chief and then the role that commands (the Incident Commander at Full activation), both recorded in the audit log. Any other order, or one approval alone, does not release.
_Avoid_: Publish, sign-off

## Risk model

**Model version**:
A set of fragility curves risk scoring can use. Version 1 is the published curves; a calibration proposes a new one, and only an approved version is ever used. Each score records the version that produced it.
_Avoid_: Model, curve set

**Calibration**:
Fitting the fragility curves to the failures of a past storm (Storm Delta) and back-testing the fit against the version in use: reliability table, Brier score and top-decile capture, before and after.
_Avoid_: Training, tuning

## Roles

**Owner role**:
The EOC section a playbook rule assigns its action to: Planning, Operations, Logistics, or Regulatory Liaison.
_Avoid_: Owner, responsible team

**Incident Commander**:
The person with authority over all playbook decisions once the EOC is at Full activation.
_Avoid_: IC (in UI text), commander

**Planning Section Chief**:
The head of the Planning section, who approves the ICS-215 and IAP objectives first in their release.
_Avoid_: Planner, planning lead

**Director**:
The EOC Director, who holds the decisions the Incident Commander would hold while the EOC is below Full activation.
_Avoid_: Manager, duty officer
