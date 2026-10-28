# Florida landfall analogues for the synthetic advisory scenario

> **Note.** These values only parameterise a **fictional** scenario. The app's storm is unnamed and
> crosses the fictional "Bayport County"; no real place, track or date from the storms below
> appears in the app. Researched 2026-10-28.

Each number is marked **sourced** (with a link) or **estimated** (with the reasoning). Unit
conversions (1 kt = 1.15 mph, 1 n mi = 1.852 km, 1 ft = 0.3048 m) are applied to sourced values and
do not change their status. Wind speeds in mph follow the NHC 5-mph rounding convention.

## Sources

| Key | Primary source |
|---|---|
| TCR-Ian | NHC Tropical Cyclone Report, Hurricane Ian (AL092022): <https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf> |
| TCR-Michael | NHC TCR, Hurricane Michael (AL142018): <https://www.nhc.noaa.gov/data/tcr/AL142018_Michael.pdf> |
| TCR-Idalia | NHC TCR, Hurricane Idalia (AL102023): <https://www.nhc.noaa.gov/data/tcr/AL102023_Idalia.pdf> |
| HURDAT2 | NHC Atlantic best track, 1851-2025 release: <https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt>. The last column is the radius of maximum wind (RMW, n mi), best-tracked from 2021 on ([format doc](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-atl-1851-2021.pdf), note 7) |
| EBTRK | RAMMB/CIRA Extended Best Track, Atlantic 1851-2021: <https://rammb2.cira.colostate.edu/wp-content/uploads/2020/11/EBTRK_AL_final_1851-2021_new_format_02-Sep-2022-1.txt> (6-hourly; covers storms up to 2021 only, so not Ian or Idalia) |
| CONE | NHC "Definition of the NHC Track Forecast Cone": <https://www.nhc.noaa.gov/aboutcone.shtml> (the `.shtm` URL now returns 404). Earlier seasons come from Internet Archive snapshots of the same NHC page: [2018](https://web.archive.org/web/20180914121611/https://www.nhc.noaa.gov/aboutcone.shtml), [2022](https://web.archive.org/web/20220921164722/https://www.nhc.noaa.gov/aboutcone.shtml), [2023](https://web.archive.org/web/20230818134148/https://www.nhc.noaa.gov/aboutcone.shtml) |

## Per-storm landfall parameters (Florida landfall)

| Parameter | Ian (2022), Cayo Costa | Michael (2018), Tyndall AFB / Mexico Beach | Idalia (2023), Keaton Beach |
|---|---|---|---|
| Max sustained wind, category | 130 kt = **150 mph, Cat 4**; mainland Punta Gorda landfall 90 min later at 125 kt = 145 mph. Sourced: [TCR-Ian](https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf) p. 4 | 140 kt = **160 mph, Cat 5**. Sourced: [TCR-Michael](https://www.nhc.noaa.gov/data/tcr/AL142018_Michael.pdf) p. 3 | 100 kt = **115 mph, Cat 3**. Sourced: [TCR-Idalia](https://www.nhc.noaa.gov/data/tcr/AL102023_Idalia.pdf) p. 4 |
| RMW at landfall | 20 n mi = **37 km**. Sourced: TCR (p. 8, "20 n mi RMW at landfall") and the HURDAT2 landfall record. Not in EBTRK (ends 2021) | 10 n mi = **18.5 km** in the HURDAT2 landfall record (10/1730 UTC). EBTRK: 10 n mi at 1200 UTC and 15 n mi (28 km) at 1800 UTC. The TCR gives no RMW value. Sourced: [HURDAT2](https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt), [EBTRK](https://rammb2.cira.colostate.edu/wp-content/uploads/2020/11/EBTRK_AL_final_1851-2021_new_format_02-Sep-2022-1.txt) | 10 n mi = **18.5 km**. Sourced: TCR p. 7 ("10-n mi radius of maximum wind at landfall") and HURDAT2 |
| Forward speed at landfall | **~12-16 km/h (8-10 mph)**: slow. Derived from HURDAT2 positions 28/1200-29/0000 UTC | **~27 km/h (16 mph)**. Derived from HURDAT2 positions 10/1200-1800 UTC | **~35-39 km/h (22-24 mph)**: fast. Derived from HURDAT2 positions 30/0600-1200 UTC |
| Peak storm surge | 10-15 ft = **3.0-4.6 m** above ground level on a barrier-island coast and its back bays. The highest sensor reading was 12.70 ft = 3.87 m above MHHW. Sourced: TCR-Ian p. 8 | 9-14 ft = **2.7-4.3 m** above ground level on a barrier-beach coast, with the maximum in a small beach town. Sourced: TCR-Michael p. 8 | 8-12 ft = **2.4-3.7 m** above ground level on a marshy, sparsely populated coast. Sourced: TCR-Idalia p. 7 |
| Official track error, T-72 / T-48 / T-24 | Storm-mean OFCL error: **205 / 126 / 59 km** (110.5 / 67.8 / 32.0 n mi, from TCR Table 5a, p. 27). Landfall-specific error: *qualitative only*. Cross-track error dominated with a **consistent westward (left-of-track) bias**, and successive forecasts shifted south and east toward the actual landfall. The cone contained the landfall point in every cycle. Sourced: TCR pp. 15-16 | Storm-mean OFCL error: **119 / 85 / 64 km** (64.4 / 45.9 / 34.5 n mi, from TCR Table 5a, p. 66). *Qualitative*: forecasts "correctly and consistently" called for a Panhandle landfall, but intensity had a large low bias (p. 12) | Storm-mean OFCL error: **85 / 105 / 72 km** (46.1 / 56.9 / 38.7 n mi, from TCR Table 6a, p. 23). *Qualitative*: forecasts were "accurate and consistent" and "well captured the landfall location" (p. 10) |

The forward speeds are **derived**: they are great-circle distances between consecutive
[HURDAT2](https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt) fixes divided by the
time between them. The positions are sourced, the arithmetic is ours, and none of the three TCRs
states a landfall forward speed. The track-error values are means over all of the storm's forecasts
at that lead time, not the miss distance at landfall. None of the TCRs tabulates the error relative
to the landfall point for individual advisories, so **landfall-specific T-72/T-48/T-24 errors are
unavailable**.

Irma (2017) and Helene (2024) were not tabulated because they add nothing the three storms above do
not already cover. For reference, EBTRK gives Irma's RMW in the Keys at 10 n mi (18.5 km).

## NHC cone circle radii (Atlantic, 2/3-probability circle)

Each radius is set so that two-thirds of the previous five years' official track errors fall inside
the circle ([CONE](https://www.nhc.noaa.gov/aboutcone.shtml)). Values in n mi are sourced, and km is
a conversion.

| Lead (h) | 2018 season (Michael) | 2022 season (Ian) | 2023 season (Idalia) | 2026 season (current) |
|---|---|---|---|---|
| 12 | 26 n mi = 48 km | 26 = 48 km | 26 = 48 km | 25 = 46 km |
| 24 | 43 = 80 km | 39 = 72 km | 39 = 72 km | 39 = 72 km |
| 36 | 56 = 104 km | 52 = 96 km | 53 = 98 km | 49 = 91 km |
| 48 | 74 = 137 km | 67 = 124 km | 67 = 124 km | 62 = 115 km |
| 60 | not published (*estimated* ~88 n mi = 164 km by linear interpolation) | 84 = 156 km | 81 = 150 km | 77 = 143 km |
| 72 | 103 = 191 km | 100 = 185 km | 99 = 183 km | 95 = 176 km |
| 96 | 151 = 280 km | 142 = 263 km | 145 = 269 km | 134 = 248 km |

Sources: [2018](https://web.archive.org/web/20180914121611/https://www.nhc.noaa.gov/aboutcone.shtml),
[2022](https://web.archive.org/web/20220921164722/https://www.nhc.noaa.gov/aboutcone.shtml),
[2023](https://web.archive.org/web/20230818134148/https://www.nhc.noaa.gov/aboutcone.shtml), and
[2026](https://www.nhc.noaa.gov/aboutcone.shtml). The 96 h row is included because advisory 1's
track runs to 24 h after landfall, which is t = 96 h.

## Recommendation: base the scenario on Ian (2022)

**Why Ian.** Ian is the only candidate whose forecast history matches the scenario's story. Its
official forecasts had a westward bias and moved south and east toward the eventual landfall over
successive advisories. Ian also strengthened as the forecasts converged. Fort Myers Beach shows both
effects: the peak surge forecast there rose from 4-7 ft to 8-12 ft "as the forecast track of Ian
shifted southward", then to 12-18 ft after the storm intensified
([TCR-Ian](https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf) p. 16). Ian's large RMW and
barrier-island surge also produce a wide, visible hazard footprint. Michael and Idalia had
consistent track forecasts, so they offer no real-world analogue for an eastward shift.

Ian's sharp intensity peak (Cat 5 offshore, then 150 mph at landfall) does not fit "strengthens
slightly", so the intensities below are a softened version of it.

| Advisory | hours_to_landfall | vmax_mph (forecast at landfall) | peak_surge_m | Track change vs previous |
|---|---|---|---|---|
| 1 | 72 | 130 | 2.5 | baseline (west of final) |
| 2 | 60 | 130 | 2.5 | none |
| 3 | 48 | 135 | 3.0 | landfall moves ~40 km east |
| 4 | 36 | 140 | 3.5 | landfall moves a further ~40 km east |
| 5 | 24 | 145 | 4.0 | none (converged) |

- **vmax_mph: estimated.** The values rise from Cat 4 (130 mph) to just below Ian's sourced landfall
  intensity of 150 mph
  ([TCR-Ian](https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf) p. 4). A total rise of 15 mph keeps
  the change "slight", and every value stays inside Cat 4 (130-156 mph).
- **rmax_km = 37: sourced** (20 n mi, [TCR-Ian](https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf)
  p. 8, and [HURDAT2](https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt)). Keep it
  constant across advisories. In the surge formula this gives an alongshore e-folding scale of
  2·Rmax = 74 km. For a compact-storm variant, use 18.5 km (Michael or Idalia, sourced above).
- **peak_surge_m: estimated.** The final value of 4.0 m sits inside Ian's sourced 3.0-4.6 m
  inundation range ([TCR-Ian](https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf) p. 8). The ramp
  from 2.5 m follows the way Ian's surge forecast rose as the track shifted and the storm
  intensified (p. 16). The early 2.5 m is roughly the upper end of the 4-7 ft (1.2-2.1 m) first
  forecast plus a margin.
- **Eastward shift of ~80 km in total between advisories 2 and 4: estimated.** This is smaller than
  Ian's sourced storm-mean OFCL errors at 48-72 h (126-205 km) and about one 48 h cone radius
  (124 km), so the shift is realistic but does not exaggerate. Tune it until the asset ranking
  visibly reorders.
- **cone_radius_km: sourced**, using the 2022 Atlantic radii (Ian's season): 12 h 48, 24 h 72,
  36 h 96, 48 h 124, 60 h 156, 72 h 185, 96 h 263 km. Use the 2026 column instead if "current NHC
  practice" matters more than consistency with Ian. Caution: the app's ensemble draws with
  σ = cone_radius_km/2. For a 1-D normal, two-thirds of draws fall within about ±0.97σ, so σ = r/2
  gives a spread about half as wide as the NHC cone. Use σ ≈ r if the ensemble should match the
  cone's 2/3 coverage. This is a design note, not a sourced fact.

### Values that could not be sourced

- The error relative to the landfall point for individual advisories at T-72/T-48/T-24, for any of
  the three storms. The TCRs give only storm-mean errors and qualitative descriptions; the
  per-advisory tracks appear only in the figures (Ian Fig. 26-27).
- Landfall forward speed stated directly by NHC. The values above are derived from HURDAT2 fixes.
- The 2018 60 h cone radius, which NHC did not publish (interpolated above).
- RMW for Ian and Idalia from EBTRK, which ends in 2021. HURDAT2 and the TCRs supply these instead.
