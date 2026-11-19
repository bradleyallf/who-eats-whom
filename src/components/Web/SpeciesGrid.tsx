import {
  Dispatch,
  KeyboardEvent,
  MouseEvent,
  SetStateAction,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { apiClient } from '../../utils'
import { Observation, Ofv } from './types'
import {
  SearchResultGrid,
  placeholderSrc,
  getCommonName,
  getScientificName,
} from './SearchedAnimal'

export interface TaxonImage {
  imageUrl?: string
  attribution?: string
}

interface Props {
  results: Observation[]
  type: Ofv['value']
  partnerData: Record<string, Observation>
  taxonImages: Record<number, TaxonImage>
  setTaxonImages: Dispatch<SetStateAction<Record<number, TaxonImage>>>
}

interface SpeciesGroup {
  key: string
  taxonId: number | null
  label: string
  scientificName?: string
  count: number
}

const getGroupKey = (result: Observation) => {
  if (result.taxon?.id) return `id:${result.taxon.id}`
  return `name:${getCommonName(result) || getScientificName(result) || 'Unknown species'}`
}

export const SearchResultSpeciesGrid = (props: Props) => {
  const { results, type, partnerData, taxonImages, setTaxonImages } = props
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [openAttributionByKey, setOpenAttributionByKey] = useState<
    Record<string, boolean>
  >({})

  const toggleAttribution =
    (key: string) => (evt: MouseEvent<HTMLButtonElement>) => {
      evt.preventDefault()
      evt.stopPropagation()
      setOpenAttributionByKey((prev) => ({ ...prev, [key]: !prev[key] }))
    }

  const linkedResults = useMemo(
    () => results.filter((result) => partnerData[result.id]),
    [results, partnerData]
  )

  const speciesGroups = useMemo(() => {
    const map = new Map<string, SpeciesGroup>()
    linkedResults.forEach((result) => {
      const key = getGroupKey(result)
      const existing = map.get(key)
      if (existing) {
        existing.count += 1
      } else {
        map.set(key, {
          key,
          taxonId: result.taxon?.id ?? null,
          label: getCommonName(result) || 'Unknown species',
          scientificName: getScientificName(result),
          count: 1,
        })
      }
    })
    return Array.from(map.values()).sort((a, b) => {
      if (b.count === a.count) return a.label.localeCompare(b.label)
      return b.count - a.count
    })
  }, [linkedResults])

  // Fetch a generic representative image for each species (taxon), rather
  // than reusing a photo from one specific observation.
  useEffect(() => {
    let canceled = false
    const taxonIds = Array.from(
      new Set(
        speciesGroups
          .map((group) => group.taxonId)
          .filter((id): id is number => id != null && !(id in taxonImages))
      )
    )

    if (!taxonIds.length) return

    Promise.all(
      taxonIds.map((taxonId) =>
        apiClient
          .get(`/v1/species/${taxonId}`)
          .then(
            (response) =>
              [taxonId, response.data?.results?.[0]] as const
          )
          .catch(() => [taxonId, null] as const)
      )
    ).then((entries) => {
      if (canceled) return
      setTaxonImages((prev) => {
        const next = { ...prev }
        entries.forEach(([taxonId, record]) => {
          next[taxonId] = {
            imageUrl: record?.image_url ?? undefined,
            attribution: record?.attribution ?? undefined,
          }
        })
        return next
      })
    })

    return () => {
      canceled = true
    }
  }, [speciesGroups, taxonImages, setTaxonImages])

  if (!linkedResults.length) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No observations to display.
      </div>
    )
  }

  const selectedGroup = selectedKey
    ? speciesGroups.find((group) => group.key === selectedKey)
    : undefined

  if (selectedGroup) {
    const drilldownResults = linkedResults.filter(
      (result) => getGroupKey(result) === selectedGroup.key
    )
    const roleLabel = type === 'eater' ? 'Prey' : 'Predator'

    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <button
            type="button"
            onClick={() => setSelectedKey(null)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            ← All species
          </button>
          <h3 className="text-base font-semibold text-slate-900">
            {selectedGroup.label}
            {selectedGroup.scientificName && (
              <span className="ml-2 text-sm italic font-normal text-slate-600">
                {selectedGroup.scientificName}
              </span>
            )}
          </h3>
          <span className="text-sm text-slate-500">
            {selectedGroup.count} observation
            {selectedGroup.count === 1 ? '' : 's'} as{' '}
            {roleLabel.toLowerCase()}
          </span>
        </div>
        <SearchResultGrid
          results={drilldownResults}
          partnerData={partnerData}
          type={type}
        />
      </div>
    )
  }

  // Cached per taxon in taxonImages, so once a species' image has been
  // fetched for this search it won't be requested again.
  const isLoadingTaxonImages = speciesGroups.some(
    (group) => group.taxonId != null && !(group.taxonId in taxonImages)
  )

  if (isLoadingTaxonImages) {
    return (
      <div className="p-4 border border-slate-200 rounded text-sm text-slate-700 flex items-center gap-3">
        <span
          className="inline-block h-5 w-5 rounded-full border-2 border-slate-300 border-t-slate-700 animate-spin"
          aria-label="Loading species images"
        />
        <span>Loading species images…</span>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {speciesGroups.map((group) => {
        const taxonImageUrl =
          group.taxonId != null
            ? taxonImages[group.taxonId]?.imageUrl
            : undefined
        const taxonAttribution =
          group.taxonId != null
            ? taxonImages[group.taxonId]?.attribution
            : undefined

        return (
          <div
            key={group.key}
            role="button"
            tabIndex={0}
            onClick={() => setSelectedKey(group.key)}
            onKeyDown={(evt: KeyboardEvent<HTMLDivElement>) => {
              if (evt.key === 'Enter' || evt.key === ' ') {
                evt.preventDefault()
                setSelectedKey(group.key)
              }
            }}
            className="block text-left rounded-lg overflow-hidden bg-white border border-slate-200 shadow-sm transition hover:border-slate-300 hover:shadow cursor-pointer"
          >
            <div className="h-48 w-full overflow-hidden bg-slate-100 relative">
              <img
                src={
                  taxonImageUrl
                    ? taxonImageUrl.replace('square', 'medium')
                    : placeholderSrc
                }
                alt={`Representative image of: ${group.label}`}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            </div>
            <div className="p-4">
              <div className="flex items-center justify-start gap-2">
                <p className="text-base font-semibold text-slate-900">
                  {group.label}
                </p>

                <div className="ml-auto inline-flex items-center gap-1 text-xs text-slate-600 shrink-0">
                  <div className="relative">
                    {openAttributionByKey[group.key] && (
                      <div className="pointer-events-none absolute bottom-full right-0 mb-1 z-10 w-48 rounded border border-slate-300 bg-white px-2 py-1 text-[10px] leading-tight text-slate-700 shadow-md">
                        {taxonAttribution ||
                          'No attribution available for this image.'}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={toggleAttribution(group.key)}
                      aria-expanded={!!openAttributionByKey[group.key]}
                      aria-label="Toggle image attribution"
                      className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-white text-slate-900 font-semibold border border-black hover:bg-slate-100"
                    >
                      CC
                    </button>
                  </div>
                </div>
              </div>
              {group.scientificName && (
                <p className="text-sm italic text-slate-600">
                  {group.scientificName}
                </p>
              )}
              <p className="mt-1 text-xs font-medium text-slate-500">
                {group.count} observation{group.count === 1 ? '' : 's'}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
