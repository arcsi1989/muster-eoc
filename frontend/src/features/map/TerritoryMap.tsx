import { CRS, type LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, Polygon, Polyline, Tooltip } from 'react-leaflet'
import { FULL_RED_AT, pFailColor } from '../../lib/pFailColor'
import type { Advisory, Asset, Coastline, Exposure, Facility, Point, StagingArea } from '../../types/scenario'

// Planar km grid with Leaflet's simple CRS: lat = y_km, lng = x_km. No tiles, no real geography.
const toLatLng = (p: Point): LatLngExpression => [p.y_km, p.x_km]
const BOUNDS: [[number, number], [number, number]] = [
  [-20, 0],
  [180, 240],
]

interface Props {
  coastline: Coastline
  assets: Asset[]
  facilities: Facility[]
  stagingAreas: StagingArea[]
  /** failure probability per asset at the current advisory */
  pFail: Map<string, number>
  exposure: Map<string, Exposure>
  advisory: Advisory | undefined
  previous: Advisory | undefined
  onSelect: (assetId: string) => void
}

function exposureText(e: Exposure | undefined): string {
  if (!e) return ''
  const arrival = e.tsforce_arrival_h === null ? 'no TS-force wind' : `TS-force wind in ${e.tsforce_arrival_h} h`
  const imputed = e.elevation_imputed ? ' (elevation imputed)' : ''
  return ` · wind ${e.wind_p50_mph}/${e.wind_p90_mph} mph · flood ${e.flood_depth_p50_m}/${e.flood_depth_p90_m} m${imputed} (P50/P90) · ${arrival}`
}

export function TerritoryMap({
  coastline,
  assets,
  facilities,
  stagingAreas,
  pFail,
  exposure,
  advisory,
  previous,
  onSelect,
}: Props) {
  return (
    <div className="map-wrap">
      <MapContainer crs={CRS.Simple} bounds={BOUNDS} minZoom={-2} className="territory-map">
        <Polygon positions={coastline.land.map(toLatLng)} pathOptions={{ className: 'land' }} />
        <Polyline positions={coastline.coastline.map(toLatLng)} pathOptions={{ className: 'coast' }} />
        {previous && (
          <Polyline positions={previous.track.map(toLatLng)} pathOptions={{ className: 'track-previous' }}>
            <Tooltip sticky>Previous forecast track (advisory {previous.advisory_no})</Tooltip>
          </Polyline>
        )}
        {advisory && (
          <>
            <Polygon positions={advisory.cone.map(toLatLng)} pathOptions={{ className: 'cone' }}>
              <Tooltip sticky>Forecast cone, advisory {advisory.advisory_no}</Tooltip>
            </Polygon>
            <Polyline positions={advisory.track.map(toLatLng)} pathOptions={{ className: 'track' }}>
              <Tooltip sticky>Forecast track, advisory {advisory.advisory_no}</Tooltip>
            </Polyline>
            <CircleMarker center={toLatLng(advisory.landfall)} radius={7} pathOptions={{ className: 'landfall' }}>
              <Tooltip direction="bottom" permanent className="landfall-label">
                Forecast landfall
              </Tooltip>
            </CircleMarker>
          </>
        )}
        {facilities.map((facility) => (
          <CircleMarker
            key={facility.id}
            center={toLatLng(facility)}
            radius={facility.type === 'hospital' ? 6 : 4}
            pathOptions={{ className: `facility facility-${facility.type}` }}
          >
            <Tooltip>
              {facility.id} {facility.name}
            </Tooltip>
          </CircleMarker>
        ))}
        {stagingAreas.map((area) => (
          <CircleMarker key={area.id} center={toLatLng(area)} radius={7} pathOptions={{ className: 'staging' }}>
            <Tooltip>
              {area.id} {area.name} (staging area)
              {exposureText(exposure.get(area.id))}
            </Tooltip>
          </CircleMarker>
        ))}
        {assets.map((asset) => {
          const score = pFail.get(asset.id)
          return (
            <CircleMarker
              key={asset.id}
              center={toLatLng(asset)}
              radius={asset.type === 'treatment_plant' ? 8 : asset.type === 'pump_station' ? 3.5 : 4.5}
              pathOptions={{
                color: '#222',
                weight: 1,
                fillColor: score === undefined ? '#9aa0a6' : pFailColor(score),
                fillOpacity: 0.95,
              }}
              eventHandlers={{ click: () => onSelect(asset.id) }}
            >
              <Tooltip>
                {asset.id} {asset.name}
                {score !== undefined && ` · failure probability ${Math.round(score * 100)}%`}
                {exposureText(exposure.get(asset.id))}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
      <div className="map-legend">
        <p>
          <span className="legend-line track" aria-hidden /> Current forecast track and cone
        </p>
        {previous && (
          <p>
            <span className="legend-line track-previous" aria-hidden /> Previous forecast
          </p>
        )}
        <p>
          <span className="legend-dot facility-hospital-swatch" aria-hidden /> hospital
          <span className="legend-dot facility-shelter-swatch" aria-hidden /> shelter
          <span className="legend-dot staging-swatch" aria-hidden /> staging area
        </p>
        <p className="legend-scale">
          <span className="legend-dot" style={{ background: pFailColor(0) }} aria-hidden /> 0%
          <span className="legend-dot" style={{ background: pFailColor(FULL_RED_AT / 2) }} aria-hidden />{' '}
          {Math.round((FULL_RED_AT / 2) * 100)}%
          <span className="legend-dot" style={{ background: pFailColor(FULL_RED_AT) }} aria-hidden /> ≥
          {Math.round(FULL_RED_AT * 100)}%
          <span className="legend-dot" style={{ background: '#9aa0a6' }} aria-hidden /> not scored
        </p>
        <p className="hint">Asset colour = failure probability at this advisory. Click an asset to see why.</p>
      </div>
    </div>
  )
}
