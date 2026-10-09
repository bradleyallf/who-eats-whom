import { useMemo, useState } from 'react'
import { Observation, Ofv } from './types'
import {
  SearchResultGrid,
  placeholderSrc,
  getCommonName,
  getScientificName,
} from './SearchedAnimal'

interface Props {
  results: Observation[]
  type: Ofv['value']
  partnerData: Record<string, Observation>
}

interface SpeciesGroup {
  key: string
  taxonId: number | null
  label: string
  scientificName?: string
  count: number
  photoUrl?: string
}

const getGroupKey = (result: Observation) => {
  if (result.taxon?.id) return `id:${result.taxon.id}`
  return `name:${getCommonName(result) || getScientificName(result) || 'Unknown species'}`
}

export const SearchResultSpeciesGrid = (props: Props) => {
  const { results, type, partnerData } = props
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  const linkedResults = useMemo(
    () => results.filter((result) => partnerData[result.id]),
    [results, partnerData]
  )

  const speciesGroups = useMemo(() => {
    const map = new Map<string, SpeciesGroup>()
    linkedResults.forEach((result) => {
      const key = getGroupKey(result)
      const licensedPhoto = result.photos?.find((photo) => photo.license_code)
      const existing = map.get(key)
      if (existing) {
        existing.count += 1
        if (!existing.photoUrl && licensedPhoto?.url) {
          existing.photoUrl = licensedPhoto.url
        }
      } else {
        map.set(key, {
          key,
          taxonId: result.taxon?.id ?? null,
          label: getCommonName(result) || 'Unknown species',
          scientificName: getScientificName(result),
          count: 1,
          photoUrl: licensedPhoto?.url,
        })
      }
    })
    return Array.from(map.values()).sort((a, b) => {
      if (b.count === a.count) return a.label.localeCompare(b.label)
      return b.count - a.count
    })
  }, [linkedResults])

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

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {speciesGroups.map((group) => (
        <button
          key={group.key}
          type="button"
          onClick={() => setSelectedKey(group.key)}
          className="block text-left rounded-lg overflow-hidden bg-white border border-slate-200 shadow-sm transition hover:border-slate-300 hover:shadow"
        >
          <div className="h-48 w-full overflow-hidden bg-slate-100 relative">
            <img
              src={
                group.photoUrl
                  ? group.photoUrl.replace('square', 'medium')
                  : placeholderSrc
              }
              alt={`Representative image of: ${group.label}`}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </div>
          <div className="p-4">
            <p className="text-base font-semibold text-slate-900">
              {group.label}
            </p>
            {group.scientificName && (
              <p className="text-sm italic text-slate-600">
                {group.scientificName}
              </p>
            )}
            <p className="mt-1 text-xs font-medium text-slate-500">
              {group.count} observation{group.count === 1 ? '' : 's'}
            </p>
          </div>
        </button>
      ))}
    </div>
  )
}
