# Demo script (8 minutes)

> **Fictional prototype.** Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are synthetic.

## The story in one paragraph

A hurricane is 72 hours from the coast of Bayport County. Five forecasts (advisories) arrive, 12 hours apart, and each one moves the expected landfall: first into Bayport West, the city, then about 40 km east into Bayport East, where the Seawall Pumping Station (PS-14) and the coastal staging yard (STG-02) sit. The video follows one thread: at advisory 3 the Incident Commander postpones the PS-14 inspection because crews are short; at advisory 5 that choice collides with the stop-work rule, and the tool hands the conflict back to a person. Everything else on screen is there because the storm forced a decision. The message: **Muster prepares decisions; people make them, and every step is on the record.**

## Before you record

- `make demo-reset` before every take. `LLM_PROVIDER=template` makes every take identical and needs no network; switch to Claude (`backend/.env`) only for the copilot scene if you want live answers.
- Window 1440 × 900 or larger, browser zoom about 110 %, a cursor highlighter. Start on the **Storm map** page.
- Say the role aloud whenever you change **Deciding as**: the roles are the human-in-the-loop story.
- Paste, don't type:
  - PS-14 override reason: `crew shortage, re-plan at next advisory`
  - PS-14 defer reason: `stop-work in force; inspect after landfall`
  - Copilot: `Why is PS-14 ranked where it is?` and `Will PS-14 fail?`
- Record scene by scene and cut them together; record the voice-over separately (about 130 words a minute) and fit the clips to it.

## Scenes

### 1. The problem (0:00–0:40) · before advisory 1

**On screen:** the Storm map, still: the synthetic coastline, the four districts, the assets coloured by risk band, hospitals, shelters and staging areas.

**Voice-over:** "This is Bayport County, a fictional coast, and SGW, the utility that keeps its power and water running. A hurricane is three days out. The emergency operations centre has two hundred critical assets, a playbook of rules, and a forecast that changes every twelve hours. Each forecast is called an advisory: where the storm will go, how strong it will be, and how uncertain that is. Muster turns each advisory into decisions for people to make. It never makes them itself."

### 2. The first forecast (0:40–1:30) · advisory 1, T-72

**Do:** **Issue advisory 1.** Point at the forecast track, the dots coloured by hurricane category, the time labels and the cone; landfall is in Bayport West. Open **Operations**: the ranked risk list, then **Decision package**. As **Director**, declare **Level 2** (prepare), the level the package proposes.

**Voice-over:** "The cone is the track uncertainty. Behind it, fifty possible versions of the storm give every asset a wind and a flood estimate. Risk is the chance of failure times who depends on the asset, so a pumping station feeding the water plant outranks a quiet substation. The playbook engine has already found gaps: six fuelled generators for more at-risk pumping stations than that. The tool proposes an activation level; the Director declares it."

### 3. Time pressure (1:30–2:00) · advisory 2, T-60

**Do:** **Issue advisory 2.** Show *What changed* and the rank arrows; open the audit and point at the items that closed as *not decided*.

**Voice-over:** "Twelve hours later, a new advisory. Whatever nobody decided is closed as not decided. The storm does not wait, and the record shows who decided what, and what nobody decided."

### 4. The storm shifts east (2:00–4:00) · advisory 3, T-48

**Do:**
1. **Issue advisory 3.** The cone narrows and the landfall moves about 40 km east, towards Bayport East; the previous track stays dotted. As **Incident Commander**, declare **Level 1** (full activation).
2. Click **PS-09** on the map: the explanation drawer (wind, flood, condition, who depends on it). It climbed from rank 40 to 20.
3. **Decision package**, by role: as **Logistics**, approve *Assign a portable generator to PS-09 (feeds WTP-01)* (P-4.5). As **Regulatory Liaison**, approve the hospital backup check for SUB-07 (P-6.2) and the regulator notification (P-7.2).
4. As **Incident Commander**, **override** the PS-14 inspection (P-4.2) with the reason `crew shortage, re-plan at next advisory`.
5. Show the situation report draft: its clause and asset chips; click one; edit a line; **approve** it.

**Voice-over:** "The forecast moved east and got stronger. PS-09 jumped twenty places, and the tool shows why: flood depth and wind at that site, and the water plant it feeds. Each action belongs to a role. Logistics sends a generator to PS-09. The regulatory liaison confirms the hospital's own backup power and notifies the regulator. Now remember PS-14, the Seawall Pumping Station. Its inspection is due, but crews are short, so the Incident Commander overrides it, with a reason. Only the Incident Commander can deviate from the playbook. The situation report is drafted for us, and every sentence cites the clause and asset it comes from. If the draft invents one, it is replaced. A person edits and approves it."

### 5. Into the field (4:00–4:30) · advisory 3

**Do:** **Field tasks**, district **Bayport West**: the PS-09 generator task with its clause and who approved it. Then **Run trace**, advisory 3, for a few seconds.

**Voice-over:** "Approved work lands with the field supervisor of that district, with the reason and the clause. They can mark it done or blocked, nothing more. And here is what the agent did for this advisory: every step, how long it took, and what it cost. Offline, the cost is zero."

### 6. Planning the next shift (4:30–5:15) · advisory 4, T-36

**Do:** **Issue advisory 4.** The landfall is now in Bayport East. Point at STG-02: the staging yard floods (P-4.6). As **Logistics**, approve two flood barriers (P-5.1). Open **ICS-215 and IAP**, **Redraft from the current decisions**, then **Approve as Planning Section Chief** and **Release as Incident Commander**.

**Voice-over:** "The storm shifted east again. Our coastal staging yard will now flood, and substations need flood barriers. From the approved items only, the tool drafts the planning worksheet for the next operational period: who goes where, with what, what we have and what we still need. Nothing is released until the planning chief approves it and the commander releases it."

### 7. The consequence (5:15–6:15) · advisory 5, T-24

**Do:** **Issue advisory 5.** In **Conflicts**: PS-14, citing P-4.2, P-4.7 and P-8.2. As **Operations**, try **Defer…**: refused. As **Incident Commander**, **Defer…** with `stop-work in force; inspect after landfall`. Then **Copilot**: `Why is PS-14 ranked where it is?` (click the PS-14 chip) and `Will PS-14 fail?`.

**Voice-over:** "Here is the inspection we postponed. Tropical-storm wind reaches PS-14 within twelve hours, and the playbook says crews withdraw. Inspect, or keep people safe? The tool does not choose. It shows the clash, cites both rules, and routes it to the Incident Commander. Operations cannot decide it; the commander can, and personnel safety prevails. The copilot answers follow-up questions from read-only tools. Asked whether PS-14 will fail, it says nobody can know, gives the modelled probability, and cites where that comes from."

### 8. Why trust it (6:15–7:30)

**Do:** **Calibration**, as **Planning**: **Run the back-test**; point at the two reliability curves and the Brier score before and after. **Champion and challenger**: the held-out Storm Delta comparison, the promotion rule, the disagreements. **Audit**: filter **People**, then **Agent**. **Data quality**: the two rejected rows.

**Voice-over:** "Why trust the numbers? We back-test the failure curves on a past storm and propose a calibrated version, which a person must approve before it scores anything. A machine-learning challenger, trained on twenty synthetic storms, beats the rules on a storm it never saw, yet it runs in shadow. It changes nothing until real outcomes justify it and a person promotes it. Every decision, every model call and every rejected data row is recorded."

### 9. Proof and close (7:30–8:00)

**Do:** `docs/eval/report.md`: the five categories and the gate; `./scripts/check.sh` running the evaluation. End on the Storm map at advisory 5.

**Voice-over:** "The AI itself is tested: thirty scenarios checked by rules, not by another model, for grounding, refusals, data leaks, prompt injection and drafting. With Claude, every category passes, and removing the citation instruction fails the build. Muster prepares the decisions. People make them."

## Alternative path (also tested)

At advisory 3, as **Operations**, *approve* the PS-14 inspection instead of overriding it (optionally mark it **Done** in **Field tasks**, district Bayport East). At advisory 5 there is no PS-14 conflict.
