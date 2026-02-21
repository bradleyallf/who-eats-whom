import {
  ChangeEvent,
  FormEvent,
  MouseEvent as ReactMouseEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { apiClient } from '../../utils'

import { SearchResultGrid } from './SearchedAnimal'
import { SearchResultGraph } from './SearchResultGraph'
import { SearchResultSummary } from './SearchResultSummary'
import { Observation, Ofv } from './types'
import { Dropdown, Suggestion } from './Dropdown'
import { SearchResultNetwork } from './SearchResultNetwork'
import { SearchResultMap } from './SearchResultMap'

const getLastLetter = (str: string) => str[str.length - 1]

const IconGrid = ({ active }: { active: boolean }) => (
  <svg
    aria-hidden
    viewBox="0 0 24 24"
    className={`${active ? 'text-white' : 'text-slate-500'} h-4 w-4`}
    fill="currentColor"
  >
    <rect x="3" y="3" width="6" height="6" rx="1" />
    <rect x="3" y="13" width="6" height="6" rx="1" />
    <rect x="13" y="3" width="6" height="6" rx="1" />
    <rect x="13" y="13" width="6" height="6" rx="1" />
  </svg>
)

const IconGraph = ({ active }: { active: boolean }) => (
  <svg
    aria-hidden
    viewBox="0 0 24 24"
    className={`${active ? 'text-white' : 'text-slate-500'} h-4 w-4`}
    fill="currentColor"
  >
    <rect x="4" y="12" width="3" height="7" rx="1" />
    <rect x="10.5" y="7" width="3" height="12" rx="1" />
    <rect x="17" y="4" width="3" height="15" rx="1" />
  </svg>
)

const IconNetwork = ({ active }: { active: boolean }) => (
  <svg
    aria-hidden
    viewBox="0 0 24 24"
    className={`${active ? 'text-white' : 'text-slate-500'} h-4 w-4`}
    stroke="currentColor"
    fill="none"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="5" cy="5" r="2.5" />
    <circle cx="19" cy="5" r="2.5" />
    <circle cx="12" cy="19" r="2.5" />
    <line x1="6.8" y1="6.2" x2="17.2" y2="6.2" />
    <line x1="11.2" y1="16.4" x2="6.2" y2="7.8" />
    <line x1="12.8" y1="16.4" x2="17.8" y2="7.8" />
  </svg>
)

const IconMap = ({ active }: { active: boolean }) => (
  <svg
    aria-hidden
    viewBox="0 0 24 24"
    className={`${active ? 'text-white' : 'text-slate-500'} h-4 w-4`}
    fill="currentColor"
  >
    <path d="M12 2a6 6 0 0 0-6 6c0 4.33 6 12 6 12s6-7.67 6-12a6 6 0 0 0-6-6Zm0 8.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5Z" />
  </svg>
)

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
  'geojson',
  'location',
  'positional_accuracy',
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

interface TaxonSuggestion {
  id: number
  name: string
  preferred_common_name?: string
  default_photo?: {
    url?: string
    small_url?: string
    square_url?: string
  }
}

export const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState<Observation[]>([])
  const [partnerData, setPartnerData] = useState<Record<string, Observation>>(
    {}
  )
  const [eatenByData, setEatenByData] = useState<Observation[]>()

  const [search, setSearch] = useState('')

  // Actual search/what appears in searchbox
  const [submittedSearch, setSubmittedSearch] = useState('')
  // NOT IMPLEMENTED YET -- search delay for api call after
  const debouncedSubSearch = useDebounce(submittedSearch, 500)

  // The taxonId from the API corresponding to a unique organism
  const [selectedTaxonId, setSelectedTaxonId] = useState<number | null>(null)
  const [taxonDesc, setTaxonDesc] = useState<string>('')
  const [taxonPhoto, setTaxonPhoto] = useState<string>('')

  // State representing the updated amount of results from API on each year update
  // Added to handle year adjustments to properly display 0 results
  const [updatedSearchLength, setUpdatedSearchLength] = useState(0)

  // Year filter added by user
  const [yearFilter, setYearFilter] = useState<string>('')
  const debouncedYearFilter = useDebounce(yearFilter, 500)
  const [suggestionSource, setSuggestionSource] = useState<TaxonSuggestion[]>(
    []
  )
  const [locationInput, setLocationInput] = useState('')
  const [selectedPlaceId, setSelectedPlaceId] = useState<number | null>(null)
  const [selectedPlaceLabel, setSelectedPlaceLabel] = useState<string | null>(
    null
  )
  const [placeLookupError, setPlaceLookupError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [isResolvingPlace, setIsResolvingPlace] = useState(false)
  const [isSearchLoading, setIsSearchLoading] = useState(false)
  const [isPartnerLoading, setIsPartnerLoading] = useState(false)
  const [isSuggestionLoading, setIsSuggestionLoading] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isLocationSuggestionLoading, setIsLocationSuggestionLoading] =
    useState(false)
  const [isLocationDropdownOpen, setIsLocationDropdownOpen] = useState(false)
  const [locationSuggestions, setLocationSuggestions] = useState<PlaceResult[]>(
    []
  )
  const [shouldDisplayResults, setShouldDisplayResults] = useState(false)
  const [selectedThumbnail, setSelectedThumbnail] = useState<string | null>(
    null
  )
  const [searchNonce, setSearchNonce] = useState(0)

  const [type, setType] = useState(types.eaten.key)
  const [selectedView, setSelectedView] = useState<
    'grid' | 'graph' | 'network' | 'map' | null
  >(null)

  const locationDropdownRef = useRef<HTMLDivElement | null>(null)
  const speciesInputReady = useMemo(
    () => search.trim().length >= 3 || submittedSearch.length >= 3,
    [search, submittedSearch]
  )

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const setPartnerLoadingFailed = () => {
    setIsPartnerLoading(false)
    setEatenByData([])
  }

  function useDebounce<T>(value: T, delay: number) {
    const [debounced, setDebounced] = useState(value)

    useEffect(() => {
      const timeout = setTimeout(() => setDebounced(value), delay)
      return () => clearTimeout(timeout)
    }, [value, delay])

    return debounced
  }

  const getPartnerData = async (ids: string[]) => {
    const uniqueIds = Array.from(new Set(ids))
    setIsPartnerLoading(true)
    if (!uniqueIds.length) {
      setEatenByData([])
      setIsPartnerLoading(false)
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

    try {
      const d = await apiClient.get(`/observations?${params.toString()}`)
      setEatenByData(d.data.results)
    } catch (error) {
      setPartnerLoadingFailed()
      return
    }
    setIsPartnerLoading(false)
  }

  const fetchPlaceCandidates = async (
    query: string
  ): Promise<PlaceResult[]> => {
    const params = new URLSearchParams({ q: query, per_page: '10' })

    try {
      const response = await apiClient.get(
        `/places/autocomplete?${params.toString()}`
      )
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

    const prioritized = results.slice().sort((a, b) => {
      const priorityIndex = (place?: PlaceResult) => {
        if (!place?.place_type_name) return priorities.length
        const idx = priorities.findIndex(
          (label) =>
            label.toLowerCase() === place.place_type_name?.toLowerCase()
        )
        return idx === -1 ? priorities.length : idx
      }
      return priorityIndex(a) - priorityIndex(b)
    })

    return (
      prioritized.find((place) =>
        place.display_name?.toLowerCase().includes(normalized)
      ) ||
      prioritized[0] ||
      null
    )
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------

  // Fetch suggestions when user types in the search box
  useEffect(() => {
    let canceled = false
    const query = search.trim()

    if (query.length < 3) {
      setSuggestionSource([])
      setIsSuggestionLoading(false)
      return () => {
        canceled = true
      }
    }

    setIsSuggestionLoading(true)

    const params = new URLSearchParams({
      q: query,
      per_page: '25',
    })
    if (selectedPlaceId) {
      params.append('place_id', String(selectedPlaceId))
    }

    apiClient
      .get(`/taxa/autocomplete?${params.toString()}`)
      .then((d) => {
        if (!canceled) {
          setSuggestionSource(d.data.results || [])
          setIsSuggestionLoading(false)
        }
      })
      .catch(() => {
        if (!canceled) {
          setSuggestionSource([])
          setIsSuggestionLoading(false)
        }
      })

    return () => {
      canceled = true
    }
  }, [search, selectedPlaceId])

  // Fetch location suggestions when user types in the location box,
  // but only if the species input is ready (to avoid unnecessary calls)
  useEffect(() => {
    let canceled = false
    const query = locationInput.trim()

    if (!speciesInputReady || query.length < 3) {
      setLocationSuggestions([])
      setIsLocationSuggestionLoading(false)
      setIsLocationDropdownOpen(false)
      return () => {
        canceled = true
      }
    }

    if (
      selectedPlaceLabel &&
      query.toLowerCase() === selectedPlaceLabel.toLowerCase()
    ) {
      setLocationSuggestions([])
      setIsLocationSuggestionLoading(false)
      setIsLocationDropdownOpen(false)
      return () => {
        canceled = true
      }
    }

    setIsLocationSuggestionLoading(true)

    fetchPlaceCandidates(query)
      .then((results) => {
        if (!canceled) {
          setLocationSuggestions(results)
          setIsLocationSuggestionLoading(false)
          setIsLocationDropdownOpen(true)
        }
      })
      .catch(() => {
        if (!canceled) {
          setLocationSuggestions([])
          setIsLocationSuggestionLoading(false)
          setIsLocationDropdownOpen(false)
        }
      })

    return () => {
      canceled = true
    }
  }, [locationInput, speciesInputReady])

  // When new search data comes in, filter it (by eaten or eater) and fetch partner data
  useEffect(() => {
    if (!shouldDisplayResults || isSearchLoading) {
      if (!shouldDisplayResults) {
        setIsPartnerLoading(false)
      }
      return
    }
    if (!data.length) {
      setIsPartnerLoading(false)
      return
    }

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
        if (
          ofv.field_id === partnerFieldId &&
          ofv.value.includes('/observations/')
        ) {
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

  // When search parameters change (search term, place filter, year filter), fetch new data from API
  // MAIN SEARCH EFFECT / API CALL / QUERY
  useEffect(() => {
    let canceled = false

    if (submittedSearch.length < 3) {
      setIsSearchLoading(false)
      setData([])
      if (submittedSearch.length === 0) {
        setSubmittedSearch('')
      }
      return () => {
        canceled = true
      }
    }

    if (yearFilter && !/^\d{4}$/.test(yearFilter)) {
      setIsSearchLoading(false)
      setData([])
      return () => {
        canceled = true
      }
    }

    setIsSearchLoading(true)

    const params = new URLSearchParams({
      project_id: String(projectId),
      quality_grade: 'research',
      per_page: '200',
      fields: observationFieldsParam,
    })
    if (selectedTaxonId) {
      params.append('taxon_id', String(selectedTaxonId))
    } else {
      params.append('taxon_name', submittedSearch)
    }
    if (selectedPlaceId) {
      params.append('place_id', String(selectedPlaceId))
    }
    if (yearFilter && /^\d{4}$/.test(yearFilter)) {
      params.append('d1', `${yearFilter}-01-01`)
      params.append('d2', `${yearFilter}-12-31`)
    }

    apiClient
      .get(`/observations?${params.toString()}`)
      .then((d) => {
        setUpdatedSearchLength(d.data.results?.length || 0)
        if (!canceled && d.data?.results != 0) {
          setData(d.data.results || [])
          setIsSearchLoading(false)
          setIsPartnerLoading(false)
          setShouldDisplayResults(true)
        } else {
          setIsSearchLoading(false)
          setShouldDisplayResults(true)
        }
      })
      .catch(() => {
        if (!canceled) {
          setData([])
          setIsSearchLoading(false)
          setIsPartnerLoading(false)
          setShouldDisplayResults(true)
        }
      })

    return () => {
      canceled = true
    }
  }, [submittedSearch, selectedPlaceId, searchNonce, yearFilter])

  // Separate use effect for the about organism information
  useEffect(() => {
    setIsSearchLoading(true)
    apiClient
      .get(`/taxa/${selectedTaxonId?.toString()}`)
      .then((d) => {
        setTaxonDesc(d.data.results[0].wikipedia_summary)
        setTaxonPhoto(d.data.results[0].default_photo.square_url)
      })
      .catch(() => {
        setTaxonDesc('')
        setTaxonPhoto('')
      })
    setIsSearchLoading(false)
  }, [selectedTaxonId])

  // Close dropdown when clicking outside or pressing Escape/Enter
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

  // Close location dropdown when clicking outside or pressing Escape
  useEffect(() => {
    if (!isLocationDropdownOpen) return

    const handleClick = (event: MouseEvent) => {
      if (
        locationDropdownRef.current &&
        !locationDropdownRef.current.contains(event.target as Node)
      ) {
        setIsLocationDropdownOpen(false)
      }
    }

    const handleKey = (evt: KeyboardEvent) => {
      if (evt.key === 'Escape') {
        setIsLocationDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)

    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [isLocationDropdownOpen])

  // --------------------- ===
  //  HANDLERS
  // ---------------------
  const handleInputChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const { value } = evt.target
    setSearch(value)
    setSelectedTaxonId(null)
    setTaxonDesc('')
    setTaxonPhoto('')
    setIsDropdownOpen(value.trim().length >= 1)
    setSearchError(null)
    setShouldDisplayResults(false)
    setSelectedThumbnail(null)
    if (value.trim().length < 3) {
      setSuggestionSource([])
      setIsSuggestionLoading(false)
    }
  }

  const handleYearChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const { value } = evt.target
    setShouldDisplayResults(false)
    if (/^\d*$/.test(value)) {
      setYearFilter(value)
    } else {
      setYearFilter('')
    }
  }

  const handleLocationChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const { value } = evt.target
    setLocationInput(value)
    setSelectedPlaceLabel(null)
    setSelectedPlaceId(null)
    setPlaceLookupError(null)
    setShouldDisplayResults(false)
    const trimmed = value.trim()
    if (trimmed.length < 3) {
      setLocationSuggestions([])
      setIsLocationSuggestionLoading(false)
    }
    setIsLocationDropdownOpen(speciesInputReady && trimmed.length >= 3)
  }

  const handleSubmit = async (
    evt?:
      | FormEvent<HTMLFormElement>
      | ReactMouseEvent<HTMLButtonElement>
      | undefined,
    explicitSearch?: string,
    explicitThumbnail?: string | null,
    explicitLocation?: { id: number | null; label: string | null }
  ) => {
    evt?.preventDefault()
    setIsDropdownOpen(false)
    setIsLocationDropdownOpen(false)
    setPlaceLookupError(null)
    // reset partner loading in case a previous search was mid-flight
    setIsPartnerLoading(false)

    const rawSearch = explicitSearch ?? search
    const trimmedSearch = rawSearch.trim()
    setSearch(trimmedSearch)

    const lookupKey = trimmedSearch.toLowerCase()
    const matchedSuggestion = suggestionLookup.get(lookupKey)

    if (explicitThumbnail !== undefined) {
      setSelectedThumbnail(explicitThumbnail)
    } else {
      setSelectedThumbnail(matchedSuggestion?.thumbnail ?? null)
    }

    if (explicitSearch == undefined) {
      setSelectedTaxonId(matchedSuggestion?.id ?? null)
    }

    if (trimmedSearch.length < 3) {
      setSearchError('Please enter a species name.')
      setShouldDisplayResults(false)
      setSubmittedSearch('')
      return
    }

    if (explicitSearch === undefined) {
      setSelectedTaxonId(matchedSuggestion?.id ?? null)
    }

    setSearchError(null)
    setIsSearchLoading(true)

    const trimmedLocation = (explicitLocation?.label ?? locationInput).trim()
    let resolvedId: number | null = explicitLocation?.id ?? null
    let resolvedLabel: string | null = explicitLocation?.label ?? null

    // If location input was cleared, make sure we clear any prior place filters
    if (!trimmedLocation) {
      resolvedId = null
      resolvedLabel = null
      setSelectedPlaceId(null)
      setSelectedPlaceLabel(null)
    }

    try {
      if (trimmedLocation && explicitLocation === undefined) {
        setIsResolvingPlace(true)
        const place = await resolvePlace(trimmedLocation)
        resolvedId = place?.id ?? null
        resolvedLabel = place?.display_name || place?.name || trimmedLocation
      }

      if (trimmedLocation && resolvedId === null) {
        setIsSearchLoading(false)
        setIsPartnerLoading(false)
        setSelectedPlaceId(null)
        setSelectedPlaceLabel(null)
        setData([])
        setEatenByData([])
        setPartnerData({})
        setShouldDisplayResults(true)
        setSubmittedSearch('')
        return
      }
    } catch (error) {
      setIsSearchLoading(false)
      setIsPartnerLoading(false)
      setIsResolvingPlace(false)
      setPlaceLookupError(
        'Unable to resolve that location. Please try another.'
      )
      setShouldDisplayResults(false)
      return
    } finally {
      setIsResolvingPlace(false)
    }

    setSelectedPlaceId(resolvedId)
    setSelectedPlaceLabel(resolvedLabel)
    setSubmittedSearch(trimmedSearch)
    setSearchNonce((n) => n + 1)
    setShouldDisplayResults(true)
    setData([])
    setEatenByData([])
    setPartnerData({})
  }

  const handleLocationSuggestionClick = (place: PlaceResult) => {
    const label = place.display_name || place.name
    setLocationInput(label || '')
    setSelectedPlaceId(place.id)
    setSelectedPlaceLabel(label || null)
    setPlaceLookupError(null)
    setIsLocationDropdownOpen(false)
    setShouldDisplayResults(false)
    void handleSubmit(undefined, search, selectedThumbnail, {
      id: place.id,
      label: label || null,
    })
  }

  const suggestionLookup = useMemo(() => {
    const map = new Map<string, Suggestion>()
    suggestionSource.forEach((taxon) => {
      const label = taxon.preferred_common_name || taxon.name
      if (!label) return
      const key = label.toLowerCase()
      if (map.has(key)) return
      const photo = taxon.default_photo
      const thumbnail =
        photo?.square_url || photo?.small_url || photo?.url || undefined
      map.set(key, {
        label,
        id: taxon.id,
        sciName: taxon.name,
        thumbnail,
      })
    })
    return map
  }, [suggestionSource])

  const suggestions = useMemo(
    () =>
      search.trim().length >= 3 ? Array.from(suggestionLookup.values()) : [],
    [search, suggestionLookup]
  )

  const filteredResults = shouldDisplayResults ? eatenByData || [] : []

  const hasResults = filteredResults.length > 0 && updatedSearchLength > 0
  const isResultsLoading = isSearchLoading || isPartnerLoading

  useEffect(() => {
    if (shouldDisplayResults && hasResults) {
      setSearchError(null)
    }
    setSelectedView(hasResults ? 'grid' : null)
  }, [hasResults, shouldDisplayResults])

  const getObservationLabel = (observation?: Observation) =>
    observation?.taxon.preferred_common_name || observation?.taxon.name || ''

  const getScientificName = (observation?: Observation) =>
    observation?.taxon.name || ''

  const focalName = useMemo(() => {
    const fallback = submittedSearch || search.trim()
    if (!hasResults) return fallback
    for (const result of filteredResults) {
      const partner = partnerData[result.id]
      const label = getObservationLabel(partner)
      if (label) return label
    }
    return fallback
  }, [filteredResults, partnerData, hasResults, submittedSearch, search])

  const aggregatedCounterparts = useMemo(() => {
    const map = new Map<
      string,
      { count: number; scientificName?: string; urls: Set<string> }
    >()

    filteredResults.forEach((observation) => {
      const label = getObservationLabel(observation) || 'Unknown'
      const current = map.get(label) || {
        count: 0,
        scientificName: undefined,
        urls: new Set<string>(),
      }
      current.count += 1
      const sciName = getScientificName(observation)
      if (sciName && !current.scientificName) {
        current.scientificName = sciName
      }
      if (observation.uri) {
        current.urls.add(observation.uri)
      }
      map.set(label, current)
    })

    return Array.from(map.entries())
      .map(([label, value]) => ({
        label,
        count: value.count,
        scientificName: value.scientificName || '',
        urls: Array.from(value.urls),
      }))
      .sort((a, b) => {
        if (b.count === a.count) return a.label.localeCompare(b.label)
        return b.count - a.count
      })
  }, [filteredResults])

  const totalSpecies = useMemo(() => {
    const speciesSet = new Set<string>()
    filteredResults.forEach((observation) => {
      const label = getObservationLabel(observation)
      if (label) speciesSet.add(label)
    })
    return speciesSet.size
  }, [filteredResults])

  const downloadCsv = () => {
    if (!aggregatedCounterparts.length) return
    const roleLabel = type === 'eaten' ? 'Predator' : 'Prey'

    const rows = [
      `${roleLabel} Common Name,${roleLabel} Scientific Name,Observation URLs,# of Observations`,
      ...aggregatedCounterparts.map((row) => {
        const urls = row.urls.join(' | ')
        return [
          JSON.stringify(row.label),
          JSON.stringify(row.scientificName || ''),
          JSON.stringify(urls),
          row.count,
        ].join(',')
      }),
    ]

    const csvContent = rows.join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)

    const sanitize = (value: string) =>
      value.replace(/[\\/:*?"<>|]/g, '').trim() || 'result'

    const species = sanitize(submittedSearch || search.trim())
    const location = selectedPlaceLabel ? sanitize(selectedPlaceLabel) : null
    const prefix = type === 'eaten' ? 'Who Eats' : 'Who is Eaten By'
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    const fileName = `${prefix} ${species}${
      location ? ` - ${location}` : ''
    } ${timestamp}.csv`

    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', fileName)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const speciesLabel =
    submittedSearch || search.trim() || 'the selected species'

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
            <div className="flex flex-1 items-center gap-2">
              {selectedThumbnail && (
                <img
                  src={selectedThumbnail}
                  alt=""
                  className="h-10 w-10 rounded object-cover border border-slate-200"
                />
              )}
              <div className="relative flex-1" style={{ zIndex: 2 }}>
                <input
                  className={`w-full ${
                    searchError
                      ? 'border-red-500 text-red-600 placeholder:text-red-500'
                      : ''
                  }`}
                  type="text"
                  onChange={handleInputChange}
                  value={search}
                  placeholder={searchError || 'Search...'}
                />

                <Dropdown
                  isLoading={isSuggestionLoading}
                  isOpen={isDropdownOpen}
                  suggestions={suggestions}
                  onClick={(s) => {
                    setSearch(s.label)
                    //setSearchSciName(s.sciName)
                    //setSearchCommonName(s.label)
                    const match = suggestionSource.find(
                      (t) => (t.preferred_common_name || t.name) === s.label
                    )
                    setSelectedTaxonId(match?.id ?? null)
                    setSelectedThumbnail(s.thumbnail ?? null)
                    void handleSubmit(undefined, s.label, s.thumbnail ?? null)
                  }}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1 items-start">
              {placeLookupError && (
                <p className="text-sm text-red-600 max-w-[16rem] leading-snug">
                  {placeLookupError}
                </p>
              )}
              <div className="flex items-stretch gap-2">
                <div
                  className="relative w-full max-w-xs"
                  style={{ zIndex: 1 }}
                  ref={locationDropdownRef}
                >
                  <input
                    className="w-full"
                    type="text"
                    value={locationInput}
                    onChange={handleLocationChange}
                    placeholder="Location"
                    onFocus={() => {
                      if (
                        speciesInputReady &&
                        locationInput.trim().length >= 3
                      ) {
                        setIsLocationDropdownOpen(true)
                      }
                    }}
                  />

                  {(isLocationDropdownOpen || isLocationSuggestionLoading) &&
                    speciesInputReady && (
                      <div className="absolute mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg max-h-60 overflow-y-auto text-sm">
                        {isLocationSuggestionLoading ? (
                          <p className="p-2 text-slate-500 italic">
                            Loading...
                          </p>
                        ) : locationSuggestions.length ? (
                          locationSuggestions.map((place) => (
                            <button
                              type="button"
                              key={place.id}
                              onClick={() =>
                                handleLocationSuggestionClick(place)
                              }
                              className="w-full text-left px-3 py-2 hover:bg-slate-100"
                            >
                              <span className="block font-medium">
                                {place.display_name || place.name}
                              </span>
                              {place.place_type_name && (
                                <span className="text-xs text-slate-500">
                                  {place.place_type_name}
                                </span>
                              )}
                            </button>
                          ))
                        ) : (
                          <p className="p-2 text-slate-500 italic">
                            No matching locations
                          </p>
                        )}
                      </div>
                    )}
                </div>
                <div className="flex items-stretch gap-2">
                  <input
                    className="w-full"
                    type="text"
                    value={yearFilter}
                    onChange={handleYearChange}
                    placeholder="Year"
                    onFocus={() => {
                      if (
                        speciesInputReady &&
                        locationInput.trim().length >= 3
                      ) {
                        setIsLocationDropdownOpen(true)
                      }
                    }}
                  />
                </div>

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
          <img src={taxonPhoto} />
          <h1 dangerouslySetInnerHTML={{ __html: taxonDesc }} />
          <SearchResultSummary
            heading={`Search results for ${
              type === 'eaten' ? 'Who eats' : 'Who is eaten by'
            } ${speciesLabel}${
              selectedPlaceLabel ? ` in ${selectedPlaceLabel}` : ''
            }${yearFilter ? ` in ${yearFilter}` : ''}:`}
            totalObservations={
              updatedSearchLength == 0 ? 0 : filteredResults.length
            }
            totalSpecies={updatedSearchLength == 0 ? 0 : totalSpecies}
            onDownload={downloadCsv}
            isDownloadDisabled={!aggregatedCounterparts.length}
            isLoading={isResultsLoading}
          />

          {isResultsLoading ? (
            <div className="p-4 border border-slate-200 rounded text-sm text-slate-700 flex items-center gap-3">
              <span
                className="inline-block h-5 w-5 rounded-full border-2 border-slate-300 border-t-slate-700 animate-spin"
                aria-label="Loading results"
              />
              <span>Loading results…</span>
            </div>
          ) : hasResults ? (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                {(
                  [
                    {
                      key: 'grid',
                      label: 'Grid',
                      disabled: false,
                      icon: IconGrid,
                    },
                    {
                      key: 'graph',
                      label: 'Graph',
                      disabled: false,
                      icon: IconGraph,
                    },
                    {
                      key: 'network',
                      label: 'Network',
                      disabled: false,
                      icon: IconNetwork,
                    },
                    {
                      key: 'map',
                      label: 'Map',
                      disabled: false,
                      icon: IconMap,
                    },
                  ] as const
                ).map(({ key, label, disabled, icon: Icon }) => (
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
                    <Icon active={selectedView === key && !disabled} />
                    <span>{label}</span>
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

              {selectedView === 'graph' && (
                <SearchResultGraph
                  results={filteredResults}
                  partnerData={partnerData}
                  type={type}
                  focalName={speciesLabel}
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

              {selectedView === 'map' && (
                <SearchResultMap
                  results={filteredResults}
                  partnerData={partnerData}
                  type={type}
                />
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
