import { useEffect, useMemo } from 'react'
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  type MapContainerProps,
  type TileLayerProps,
} from 'react-leaflet'
import L, { type LatLngExpression } from 'leaflet'

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

import { Observation, Ofv } from './types'

type MarkerPoint = {
  id: number
  lat: number
  lng: number
  label: string
  roleLabel: string
  url: string
  locationText?: string
  positionalAccuracy?: number | null
}

const DEFAULT_CENTER: LatLngExpression = [20, 0]
const DEFAULT_ZOOM = 2

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const getObservationLabel = (observation?: Observation) =>
  observation?.taxon.preferred_common_name || observation?.taxon.name || 'Unknown species'

const getLocationLabel = (observation?: Observation) => {
  if (!observation) return undefined
  const parts = [
    observation.place_town_name,
    observation.place_county_name,
    observation.place_state_name,
    observation.place_country_name,
  ]
    .filter(Boolean)
    .map((part) => part?.trim())

  return parts.length ? parts.join(', ') : undefined
}

const extractCoordinates = (observation?: Observation) => {
  if (!observation) return null

  const { geojson, latitude, longitude, location } = observation

  if (geojson?.coordinates?.length === 2) {
    const [lng, lat] = geojson.coordinates
    if (typeof lat === 'number' && typeof lng === 'number') {
      return { lat, lng }
    }
  }

  if (typeof latitude === 'number' && typeof longitude === 'number') {
    return { lat: latitude, lng: longitude }
  }

  if (location && typeof location === 'string') {
    const [latStr, lngStr] = location.split(',')
    const lat = Number(latStr)
    const lng = Number(lngStr)
    if (!Number.isNaN(lat) && !Number.isNaN(lng)) {
      return { lat, lng }
    }
  }

  return null
}

const MapBoundsHandler = ({ points }: { points: MarkerPoint[] }) => {
  const map = useMap()

  useEffect(() => {
    if (!points.length) {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM)
      return
    }

    if (points.length === 1) {
      const { lat, lng } = points[0]
      map.setView([lat, lng], Math.max(DEFAULT_ZOOM + 3, 6))
      return
    }

    const bounds = L.latLngBounds(points.map(({ lat, lng }) => [lat, lng] as [number, number]))
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 })
  }, [map, points])

  return null
}

interface Props {
  results: Observation[]
  partnerData: Record<string, Observation>
  type: Ofv['value']
}

export const SearchResultMap = ({ results, partnerData, type }: Props) => {
  const markerPoints = useMemo<MarkerPoint[]>(() => {
    const roleLabel = type === 'eaten' ? 'Predator' : 'Prey'

    return results.flatMap((result) => {
      const partner = partnerData[result.id]
      const coords = extractCoordinates(result) ?? extractCoordinates(partner)
      if (!coords) return []

      const label = getObservationLabel(result) || getObservationLabel(partner)

      return [
        {
          id: result.id,
          lat: coords.lat,
          lng: coords.lng,
          label,
          roleLabel,
          url: result.uri,
          locationText: getLocationLabel(result) ?? getLocationLabel(partner),
          positionalAccuracy: result.positional_accuracy ?? partner?.positional_accuracy,
        },
      ]
    })
  }, [partnerData, results, type])

  const mapProps: MapContainerProps = useMemo(
    () => ({
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      scrollWheelZoom: true,
      className: 'h-full w-full',
    }),
    []
  )

  const tileLayerProps: TileLayerProps = useMemo(
    () => ({
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    }),
    []
  )

  if (!results.length) {
    return (
      <div className="p-4 border border-slate-200 rounded text-sm text-slate-600">
        No map data available for this search yet.
      </div>
    )
  }

  if (!markerPoints.length) {
    return (
      <div className="p-4 border border-slate-200 rounded text-sm text-slate-600">
        None of the observations include map-ready coordinates. Try a different search or
        remove location filters.
      </div>
    )
  }

  return (
    <div className="w-full h-[32rem] border border-slate-200 rounded-lg overflow-hidden shadow-sm">
      <MapContainer {...mapProps}>
        <TileLayer {...tileLayerProps} />
        <MapBoundsHandler points={markerPoints} />
        {markerPoints.map((marker) => (
          <Marker key={marker.id} position={[marker.lat, marker.lng]}>
            <Popup>
              <div className="space-y-1">
                <p className="font-semibold text-sm">{marker.label}</p>
                <p className="text-xs text-slate-600">{marker.roleLabel}</p>
                {marker.locationText && (
                  <p className="text-xs text-slate-600">{marker.locationText}</p>
                )}
                {marker.positionalAccuracy != null && (
                  <p className="text-[10px] text-slate-500">
                    Positional accuracy: ~{marker.positionalAccuracy} m
                  </p>
                )}
                <a
                  href={marker.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-xs text-cyan-700 underline"
                >
                  View observation
                </a>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
