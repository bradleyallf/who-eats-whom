import { useEffect, useMemo } from 'react'
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
  type MapContainerProps,
  type TileLayerProps,
} from 'react-leaflet'
import L, { type LatLngExpression } from 'leaflet'

import { Observation, Ofv } from './types'
import { getCategoryColor } from './networkColors'

type MarkerPoint = {
  id: number
  lat: number
  lng: number
  label: string
  scientificName?: string
  url: string
  color: string
}

const DEFAULT_CENTER: LatLngExpression = [20, 0]
const DEFAULT_ZOOM = 2

const getObservationLabel = (observation?: Observation) =>
  observation?.taxon.preferred_common_name ||
  observation?.taxon.name ||
  'Unknown species'

const getScientificName = (observation?: Observation) => observation?.taxon.name

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

    const bounds = L.latLngBounds(
      points.map(({ lat, lng }) => [lat, lng] as [number, number])
    )
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 })
  }, [map, points])

  return null
}

interface Props {
  results: Observation[]
  partnerData: Record<string, Observation>
  type: Ofv['value']
}

export const SearchResultMap = ({ results, partnerData }: Props) => {
  const markerPoints = useMemo<MarkerPoint[]>(() => {
    return results.flatMap((result) => {
      const partner = partnerData[result.id]
      const coords = extractCoordinates(result) ?? extractCoordinates(partner)
      if (!coords) return []

      const label = getObservationLabel(result) || getObservationLabel(partner)
      const scientificName =
        getScientificName(result) || getScientificName(partner)
      const colorSource = result?.taxon?.iconic_taxon_name ? result : partner
      const color = getCategoryColor(colorSource?.taxon?.iconic_taxon_name)

      return [
        {
          id: result.id,
          lat: coords.lat,
          lng: coords.lng,
          label,
          scientificName,
          url: result.uri,
          color,
        },
      ]
    })
  }, [partnerData, results])

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
        None of the observations include map-ready coordinates. Try a different
        search or remove location filters.
      </div>
    )
  }

  return (
    <div className="sticky top-40 w-full h-[32rem] border border-slate-200 rounded-lg overflow-hidden shadow-sm z-0">
      <MapContainer {...mapProps}>
        <TileLayer {...tileLayerProps} />
        <MapBoundsHandler points={markerPoints} />
        {markerPoints.map((marker) => (
          <CircleMarker
            key={marker.id}
            center={[marker.lat, marker.lng]}
            radius={8}
            pathOptions={{
              color: '#0f172a',
              weight: 1,
              fillColor: marker.color,
              fillOpacity: 0.95,
            }}
          >
            <Popup>
              <div className="space-y-1">
                <p className="font-semibold text-sm">{marker.label}</p>
                {marker.scientificName && (
                  <p className="text-xs italic text-slate-600">
                    {marker.scientificName}
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
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
