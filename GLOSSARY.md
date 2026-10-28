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
The EOC's readiness stage, derived from hours to landfall: Monitor (T-120 to T-72), Prepare (T-72 to T-48), Full (T-48 to landfall). A boundary hour belongs to the later, higher level.
_Avoid_: Phase, alert level

## Playbook

**Clause**:
One numbered paragraph of the playbook (for example P-4.2), cited by its ID.
_Avoid_: Section, rule text

**Rule**:
The machine-checkable trigger for a clause: when it applies, to which entity, and what state satisfies it.
_Avoid_: Check, condition

**Prohibition**:
A rule that forbids field work at an entity (P-4.7) instead of requiring an action. It never becomes a finding on its own; it blocks actions.

## Findings and decisions

**Finding**:
The result of evaluating one rule against one entity at one advisory: satisfied, open, or in conflict.
_Avoid_: Alert, issue

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

## Roles

**Owner role**:
The EOC section a playbook rule assigns its action to: Planning, Operations, Logistics, or Regulatory Liaison.
_Avoid_: Owner, responsible team

**Incident Commander**:
The person with authority over all playbook decisions once the EOC is at Full activation.
_Avoid_: IC (in UI text), commander

**Director**:
The EOC Director, who holds the decisions the Incident Commander would hold while the EOC is below Full activation.
_Avoid_: Manager, duty officer
