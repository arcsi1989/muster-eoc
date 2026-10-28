import { CRS, type LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, Polygon, Polyline, Tooltip } from 'react-leaflet'
import { riskColor } from '../../lib/riskColor'
import type { Advisory, Asset, Coastline, Facility, Point, StagingArea } from '../../types/scenario'

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
  scores: Map<string, number>
  advisory: Advisory | undefined
  previous: Advisory | undefined
}

export function TerritoryMap({ coastline, assets, facilities, stagingAreas, scores, advisory, previous }: Props) {
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
            </Tooltip>
          </CircleMarker>
        ))}
        {assets.map((asset) => {
          const score = scores.get(asset.id)
          return (
            <CircleMarker
              key={asset.id}
              center={toLatLng(asset)}
              radius={asset.type === 'treatment_plant' ? 8 : asset.type === 'pump_station' ? 3.5 : 4.5}
              pathOptions={{
                color: '#222',
                weight: 1,
                fillColor: score === undefined ? '#9aa0a6' : riskColor(score),
                fillOpacity: 0.95,
              }}
            >
              <Tooltip>
                {asset.id} {asset.name}
                {score !== undefined && ` · score ${score.toFixed(2)}`}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
      <div className="map-legend">
        <p>
          <span className="legend-line track" aria-hidden /> Current forecast track
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
          <span className="legend-dot" style={{ background: riskColor(0) }} aria-hidden /> low
          <span className="legend-dot" style={{ background: riskColor(0.5) }} aria-hidden /> medium
          <span className="legend-dot" style={{ background: riskColor(1) }} aria-hidden /> high
          <span className="legend-dot" style={{ background: '#9aa0a6' }} aria-hidden /> not scored
        </p>
        <p className="hint">Score for now = closeness to the forecast landfall. The real risk score comes next.</p>
      </div>
    </div>
  )
}
