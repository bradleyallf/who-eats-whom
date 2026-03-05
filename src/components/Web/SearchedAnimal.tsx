import { Observation, Ofv } from './types'

interface Props {
  results: Observation[]
  type: Ofv['value']
  partnerData: Record<string, Observation>
}

const placeholderSrc = 'https://via.placeholder.com/400x300.png?text=No+Image'

const getCommonName = (observation?: Observation) =>
  observation?.taxon.preferred_common_name || observation?.taxon.name

const getScientificName = (observation?: Observation) => observation?.taxon.name

export const SearchResultGrid = (props: Props) => {
  const { results, type, partnerData } = props

  if (!results.length) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No observations to display.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {results.map((result) => {
        const partner = partnerData[result.id]
        if (!partner) return null

        const displayObservation = result
        const commonName = getCommonName(displayObservation)
        const scientificName = getScientificName(displayObservation)
        const licensedPhoto = displayObservation.photos?.find(
          (photo) => photo.license_code
        )
        const photoUrl = licensedPhoto?.url
        const licenseCode = licensedPhoto?.license_code
        const attribution = licensedPhoto?.attribution
        const roleLabel = type === 'eater' ? 'Prey' : 'Predator'

        return (
          <a
            key={result.id}
            href={displayObservation.uri}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-lg overflow-hidden bg-white border border-slate-200 shadow-sm transition hover:border-slate-300 hover:shadow"
          >
            <div className="h-48 w-full overflow-hidden bg-slate-100 relative">
              <img
                src={
                  photoUrl
                    ? photoUrl.replace('square', 'medium')
                    : placeholderSrc
                }
                alt={commonName || scientificName || 'Observation'}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            </div>
            <div className="p-4">
              <span className="sr-only">{roleLabel}</span>
              <div className="flex items-center justify-start gap-2">
                <p className="text-base font-semibold text-slate-900">
                  {commonName || 'Unknown species'}
                </p>

                <div
                  className="ml-auto inline-flex items-center gap-1 text-xs text-slate-600 shrink-0"
                  title={attribution}
                >
                  <span
                    className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-white-100 text-slate-900 font-semibold border border-black"
                    aria-hidden="true"
                  >
                    CC
                  </span>
                </div>
              </div>
              {scientificName && (
                <p className="text-sm italic text-slate-600">
                  {scientificName}
                </p>
              )}
            </div>
          </a>
        )
      })}
    </div>
  )
}
