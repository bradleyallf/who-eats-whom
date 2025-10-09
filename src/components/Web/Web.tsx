import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { apiClient } from '../../utils'

import { SearchResultGrid } from './SearchedAnimal'
import { Observation, Ofv } from './types'
import { Dropdown, Suggestion } from './Dropdown'
import { SearchResultNetwork } from './SearchResultNetwork'

const getLastLetter = (str: string) => str[str.length - 1]

const types: Record<
  Ofv['value'],
  {
    label: string
    value: string
    key: Ofv['value']
  }
> = {
  eaten: {
    label: 'Who eats...',
    value: 'thing being eaten',
    key: 'eaten',
  },
  eater: {
    label: 'Who is eaten by...',
    value: 'eater',
    key: 'eater',
  },
}

const partnerFieldId = 12796
const projectId = 41347
const eaterEatenFieldId = 12795 // in the ofvs array
const observationFieldsParam = [
  'id',
  'uri',
  'ofvs',
  'taxon',
  'photos',
  'place_country_name',
  'place_state_name',
  'place_county_name',
  'place_town_name',
].join(',')

interface PlaceResult {
  id: number
  name: string
  display_name?: string
  place_type_name?: string
}

export const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState<Observation[]>([])
  const [partnerData, setPartnerData] = useState<Record<string, Observation>>({})
  const [eatenByData, setEatenByData] = useState<Observation[]>()

  const [search, setSearch] = useState('')
  const [locationInput, setLocationInput] = useState('')
  const [selectedPlaceId, setSelectedPlaceId] = useState<number | null>(null)
  const [placeLookupError, setPlaceLookupError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [isResolvingPlace, setIsResolvingPlace] = useState(false)
  const [isSearchLoading, setIsSearchLoading] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [shouldDisplayResults, setShouldDisplayResults] = useState(false)

  const [type, setType] = useState(types.eaten.key)
  const [selectedView, setSelectedView] = useState<
    'grid' | 'graph' | 'network' | 'map' | null
  >(null)

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getPartnerData = async (ids: string[]) => {
    const uniqueIds = Array.from(new Set(ids))
    if (!uniqueIds.length) {
      setEatenByData([])
      return
    }

    const params = new URLSearchParams({
      id: uniqueIds.join(','),
      quality_grade: 'research',
      per_page: '200',
      fields: observationFieldsParam,
    })
    if (selectedPlaceId) {
      params.append('place_id', String(selectedPlaceId))
    }

    const d = await apiClient.get(`/observations?${params.toString()}`)
    setEatenByData(d.data.results)
  }

  const fetchPlaceCandidates = async (query: string): Promise<PlaceResult[]> => {
    const params = new URLSearchParams({ q: query, per_page: '10' })

    try {
      const response = await apiClient.get(`/places/autocomplete?${params.toString()}`)
      if (response.data?.results?.length) {
        return response.data.results
      }
    } catch (error) {
      console.error('Place autocomplete failed, falling back to /places', error)
    }

    try {
      const response = await apiClient.get(`/places?${params.toString()}`)
      return response.data?.results || []
    } catch (error) {
      console.error('Fallback place lookup failed', error)
      throw error
    }
  }

  const resolvePlace = async (query: string): Promise<PlaceResult | null> => {
    const results = await fetchPlaceCandidates(query)
    if (!results.length) return null

    const normalized = query.trim().toLowerCase()
    const exact = results.find(
      (place) =>
        place.display_name?.toLowerCase() === normalized ||
        place.name?.toLowerCase() === normalized
    )
    if (exact) return exact

    const priorities = [
      'Country',
      'State',
      'Province',
      'County',
      'Region',
      'Local Administrative Area',
    ]

    const prioritized = results
      .slice()
      .sort((a, b) => {
        const priorityIndex = (place?: PlaceResult) => {
          if (!place?.place_type_name) return priorities.length
          const idx = priorities.findIndex(
            (label) => label.toLowerCase() === place.place_type_name?.toLowerCase()
          )
          return idx === -1 ? priorities.length : idx
        }
        return priorityIndex(a) - priorityIndex(b)
      })

    return (
      prioritized.find((place) =>
        place.display_name?.toLowerCase().includes(normalized)
      ) || prioritized[0] || null
    )
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------
  useEffect(() => {
    if (!shouldDisplayResults || !data.length || isSearchLoading) return

    // FILTER DATA
    const filteredData: Observation[] = []
    data.forEach((d) => {
      const typeObj = d.ofvs.find((o) => o.field_id === eaterEatenFieldId)
      // "eater" or "organism being eaten" (previously "thing being eaten")
      if (!typeObj) return
      //console.log('id:',d.id, 'typeObj:', typeObj.value, 'type:', type, 'typeValue:', types[type].value)

      if (getLastLetter(typeObj.value) === getLastLetter(types[type].value)) {
        filteredData.push(d)
      }
    })

    const observationIds: string[] = []
    const partnerD: Record<string, Observation> = {}
    filteredData.forEach((result) => {
      result.ofvs.forEach((ofv) => {
        
        if (ofv.field_id === partnerFieldId && ofv.value.includes('/observations/')) {
          /*
          console.log("...--->" + ofv.value)
          const i = ofv.value.lastIndexOf('/')
          const observationId = ofv.value.substring(i + 1, ofv.value.length)
          partnerD[observationId] = result
          console.log(observationId)
          observationIds.push(observationId)
          */
        
         const matches = ofv.value.match(/\/observations\/(\d+)/g)
          if (matches) {
            matches.forEach((match) => {
              const observationId = match.split('/').pop()!
              partnerD[observationId] = result
              observationIds.push(observationId)
            })
          }
          
        }
      })
    })
    setPartnerData(partnerD)
    getPartnerData(observationIds)
  }, [data, type, shouldDisplayResults, selectedPlaceId, isSearchLoading])

  useEffect(() => {
    let canceled = false

    if (search.length < 3) {
      setIsSearchLoading(false)
      setIsDropdownOpen(false)
      setData([])
      return () => {
        canceled = true
      }
    }

    setIsSearchLoading(true)

    const params = new URLSearchParams({
      project_id: String(projectId),
      taxon_name: search,
      quality_grade: 'research',
      per_page: '200',
      fields: observationFieldsParam,
    })
    if (selectedPlaceId) {
      params.append('place_id', String(selectedPlaceId))
    }

    apiClient
      .get(`/observations?${params.toString()}`)
      .then((d) => {
        if (!canceled) {
          setData(d.data.results)
          setIsSearchLoading(false)
        }
      })
      .catch(() => {
        if (!canceled) {
          setData([])
          setIsSearchLoading(false)
        }
      })

    return () => {
      canceled = true
    }
  }, [search, selectedPlaceId])

  useEffect(() => {
    if (isDropdownOpen) {
      const close = () => setIsDropdownOpen(false)
      document.addEventListener('click', close)
      document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' || evt.key === 'Enter') close()
      })
      return () => {
        document.removeEventListener('click', close)
      }
    }
  }, [isDropdownOpen])

  // --------------------- ===
  //  HANDLERS
  // ---------------------
  const handleInputChange = (evt: ChangeEvent<HTMLInputElement>) => {
    setSearch(evt.target.value)
    setIsDropdownOpen(true)
    setSearchError(null)
    setShouldDisplayResults(false)
  }

  const handleLocationChange = (evt: ChangeEvent<HTMLInputElement>) => {
    setLocationInput(evt.target.value)
    setPlaceLookupError(null)
    setShouldDisplayResults(false)
  }

  const handleSubmit = async (evt: FormEvent<HTMLFormElement>) => {
    evt.preventDefault()
    setIsDropdownOpen(false)
    setPlaceLookupError(null)

    if (search.trim().length < 3) {
      setSearchError('Please enter a species name.')
      setShouldDisplayResults(false)
      return
    }

    const trimmedLocation = locationInput.trim()
    let resolvedId: number | null = null

    if (trimmedLocation) {
      setIsResolvingPlace(true)
      try {
        const place = await resolvePlace(trimmedLocation)
        resolvedId = place?.id ?? null
      } catch (error) {
        setIsResolvingPlace(false)
        setShouldDisplayResults(false)
        return
      } finally {
        setIsResolvingPlace(false)
      }
    }

    if (trimmedLocation && resolvedId === null) {
      setSelectedPlaceId(null)
      setData([])
      setEatenByData([])
      setPartnerData({})
      setShouldDisplayResults(true)
      return
    }

    setSelectedPlaceId(resolvedId)
    setShouldDisplayResults(true)
  }

  const suggestions: Suggestion[] = Array.from(
    data.reduce((map, d) => {
      const name = d.taxon.preferred_common_name
      if (!name) return map
      if (!map.has(name)) {
        map.set(name, {
          label: name,
          sciName: d.taxon.name,
          thumbnail:
            d.taxon.default_photo?.square_url ||
            d.taxon.default_photo?.url ||
            undefined,
        })
      }
      return map
    }, new Map<string, Suggestion>())
  ).map(([, v]) => v)

  const filteredResults = shouldDisplayResults ? eatenByData || [] : []

  const hasResults = filteredResults.length > 0

  useEffect(() => {
    if (shouldDisplayResults && hasResults) {
      setSearchError(null)
    }
    setSelectedView(hasResults ? 'grid' : null)
  }, [hasResults, shouldDisplayResults])

  const getObservationLabel = (observation?: Observation) =>
    observation?.taxon.preferred_common_name || observation?.taxon.name || ''

  const focalName = useMemo(() => {
    if (!hasResults) return search.trim()
    for (const result of filteredResults) {
      const partner = partnerData[result.id]
      const label = getObservationLabel(partner)
      if (label) return label
    }
    return search.trim()
  }, [filteredResults, partnerData, hasResults, search])

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <div className="mt-12">
        <div className="flex justify-center gap-2 w-full">
          {/* type selector */}
          <select
            className="form-select form-select-lg w-full max-w-[12rem]"
            value={type}
            onChange={(evt) => {
              const { value } = evt.target
              if (value === 'eaten' || value === 'eater') setType(value)
            }}
          >
            {(Object.keys(types) as Array<Ofv['value']>).map((key) => (
              <option value={key} key={key}>
                {types[key].label}
              </option>
            ))}
          </select>

          {/* search box + dropdown */}
          <form
            className="w-full max-w-3xl flex items-stretch gap-2"
            onSubmit={handleSubmit}
          >
            <div className="relative flex-1" style={{ zIndex: 2 }}>
              <input
                className={`w-full ${searchError ? 'border-red-500 text-red-600 placeholder:text-red-500' : ''}`}
                type="text"
                onChange={handleInputChange}
                value={search}
                placeholder={searchError || 'Search...'}
              />

              <Dropdown
                isLoading={isSearchLoading}
                isOpen={isDropdownOpen}
                suggestions={suggestions}
                onClick={(s) => {
                  setSearch(s.label)
                  setIsDropdownOpen(false)
                  setShouldDisplayResults(false)
                }}
              />
            </div>
            <div className="flex flex-col gap-1 items-start">
              {placeLookupError && (
                <p className="text-sm text-red-600 max-w-[16rem] leading-snug">
                  {placeLookupError}
                </p>
              )}
              <div className="flex items-stretch gap-2">
                <input
                  className="w-full max-w-xs"
                  type="text"
                  value={locationInput}
                  onChange={handleLocationChange}
                  placeholder="Location"
                />
                <button
                  type="submit"
                  disabled={isResolvingPlace}
                  className={`px-4 bg-orange-500 text-white font-semibold rounded ${
                    isResolvingPlace ? 'opacity-70 cursor-not-allowed' : ''
                  }`}
                >
                  {isResolvingPlace ? 'Loading...' : 'Go'}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>


      {shouldDisplayResults && (
        <div className="col-12 mt-20 space-y-6">
          {hasResults ? (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                {(
                  [
                    { key: 'grid', label: 'Grid', disabled: false },
                    { key: 'graph', label: 'Graph', disabled: true },
                    { key: 'network', label: 'Network', disabled: false },
                    { key: 'map', label: 'Map', disabled: true },
                  ] as const
                ).map(({ key, label, disabled }) => (
                  <button
                    key={key}
                    type="button"
                    disabled={disabled}
                    title={disabled ? 'Coming soon' : undefined}
                    onClick={() => {
                      if (!disabled) setSelectedView(key)
                    }}
                    className={`flex items-center gap-2 rounded-md border px-4 py-2 transition-colors ${
                      selectedView === key
                        ? 'bg-slate-900 text-white border-slate-900'
                        : 'bg-white text-slate-700 border-slate-200'
                    } ${disabled ? 'cursor-not-allowed opacity-70' : ''}`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {selectedView === 'grid' && (
                <SearchResultGrid
                  results={filteredResults}
                  partnerData={partnerData}
                  type={type}
                />
              )}

              {selectedView === 'network' && (
                <SearchResultNetwork
                  results={filteredResults}
                  partnerData={partnerData}
                  type={type}
                  focalName={focalName}
                />
              )}

              {selectedView && selectedView !== 'grid' && selectedView !== 'network' && (
                <div className="p-4 border border-dashed border-slate-200 rounded text-sm text-slate-600">
                  {selectedView.charAt(0).toUpperCase() +
                    selectedView.slice(1)}{' '}
                  view coming soon.
                </div>
              )}
            </>
          ) : (
            <div className="p-4 border border-slate-200 rounded text-sm text-slate-600">
              No results were found for this search.
            </div>
          )}
        </div>
      )}
    </>
  )
}
