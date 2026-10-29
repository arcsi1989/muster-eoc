"""Replays all five advisories against the gold data and checks every demo seed fact (plan
section 2.2). `make data` fails loudly if one does not hold."""

import tempfile
from pathlib import Path

from sqlmodel import Session, select

from app.calibration import service as calibration
from app.db import create_fresh_engine
from app.errors import DataNotLoaded
from app.ingest.loader import load_gold
from app.models import Asset, Exposure, OpState, Score, StormOutcome
from app.network import load_network
from app.replay import service
from app.scoring_config import ScoringConfig


def check_seeds(data_dir: Path, config: ScoringConfig) -> list[str]:
    """The demo seed facts that do not hold; empty when the data is demo-ready."""
    with (
        tempfile.TemporaryDirectory() as tmp,
        Session(create_fresh_engine(Path(tmp) / "seed.sqlite")) as session,
    ):
        load_gold(session, data_dir)
        for _ in range(service.total_advisories(session)):
            service.advance(session, config)
            session.commit()
        return _failures(session, config)


def _failures(session: Session, config: ScoringConfig) -> list[str]:
    network = load_network(session)
    assets = network.assets

    def exposure(site: str, advisory: int) -> Exposure:
        found = session.get(Exposure, (site, advisory))
        if found is None:
            raise DataNotLoaded(f"no exposure for {site} at advisory {advisory}")
        return found

    def scores(advisory: int) -> dict[str, Score]:
        return {
            s.asset_id: s for s in session.exec(select(Score).where(Score.advisory_no == advisory))
        }

    def top(advisory: int, n: int) -> set[str]:
        return {a for a, s in scores(advisory).items() if s.rank <= n}

    def state(entity: str, key: str) -> object:
        row = session.get(OpState, (entity, key))
        return None if row is None else row.value

    wtp_pump_stations_top25 = [a for a in top(1, 25) if network.serves_treatment_plant(a)]
    first_issued = service.all_advisories(session)[0].issued_at.date()
    stale_days = config.risk.stale_inspection_years * 365
    stale = [
        a
        for a in session.exec(select(Asset))
        if (first_issued - a.last_inspection_date).days > stale_days
    ]

    outcomes = list(
        session.exec(select(StormOutcome).where(StormOutcome.storm == config.calibration.storm))
    )
    failure_rate = sum(o.failed for o in outcomes) / max(1, len(outcomes))
    calibrated = calibration.run(session, config)

    ps14 = assets["PS-14"]
    ps14_arrival = {n: exposure("PS-14", n).tsforce_arrival_h for n in (3, 4, 5)}
    stg02_floods = [exposure("STG-02", n).flood_depth_p90_m > 0 for n in range(1, 6)]
    checks = {
        "SUB-07 feeds HOSP-01": "HOSP-01" in {f.id for f in network.direct_facilities("SUB-07")},
        "SUB-07 in the top 25 at advisory 3": "SUB-07" in top(3, 25),
        "Bayport General not yet contacted": state("SUB-07", "critical_customer_contacted") is False
        and state("SUB-07", "hospital_backup_confirmed") is False,
        "PS-09 serves WTP-01": network.serves_treatment_plant("PS-09")
        and "WTP-01" in network.treatment_plants_reached("PS-09"),
        "PS-09 has no generator": state("PS-09", "generator_assigned") is False,
        "PS-09 p_fail >= 0.20 at advisory 3": scores(3)["PS-09"].p_fail >= 0.20,
        "PS-14 is a pumping station within 5 km of the coast": (
            ps14.type == "pump_station" and ps14.distance_to_coast_km <= 5
        ),
        "PS-14 flood P90 > 0.5 m from advisory 3": all(
            exposure("PS-14", n).flood_depth_p90_m > 0.5 for n in (3, 4, 5)
        ),
        "PS-14 stop-work wind within 12 h only at advisory 5": (
            all((ps14_arrival[n] or 99) > 12 for n in (3, 4)) and (ps14_arrival[5] or 99) <= 12
        ),
        "STG-02 floods from advisory 4 only": stg02_floods == [False, False, False, True, True],
        "6 fuelled generators, 8+ pumping stations serving WTP-01 in the top 25 at advisory 1": (
            state("event", "generators_fuelled") == 6 and len(wtp_pump_stations_top25) >= 8
        ),
        "a poor-condition substation in the top 10 at advisory 2": any(
            assets[a].type == "substation" and assets[a].condition_score >= 4 for a in top(2, 10)
        ),
        "the top 10 changes between advisories 2 and 4": top(2, 10) != top(4, 10),
        "a substation with flood P90 > 0.3 m at advisory 4": any(
            assets[a].type == "substation" and exposure(a, 4).flood_depth_p90_m > 0.3
            for a in assets
        ),
        "3 null elevations": sum(a.elevation_m is None for a in assets.values()) == 3,
        "5 inspections over 3 years old": len(stale) == 5,
        "Storm Delta has an outcome for every asset": {o.asset_id for o in outcomes} == set(assets),
        "10-50 % of assets failed in Storm Delta": 0.10 <= failure_rate <= 0.50,
        "calibration on Storm Delta lowers the Brier score": (
            calibrated.after.brier < calibrated.before.brier
        ),
    }
    return [name for name, holds in checks.items() if not holds]
