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
        let i = 0
        while (!displayObservation.photos?.[i].license_code) {
          i++
        }
        const photoUrl = displayObservation.photos?.[i]?.url
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
              <div className="bg-black p-2 rounded-full cursor-pointer group">
                <h2 className="bg-black/60 absolute top-2 text-white p-1 rounded">
                  {displayObservation.photos?.[i].license_code}
                </h2>
                <div className="absolute top-2 left-10 opacity-0 group-hover:opacity-100 transition bg-black text-white text-xs px-2 py-1 rounded">
                  Small hover text
                </div>
              </div>
            </div>
            <div className="p-4">
              <span className="sr-only">{roleLabel}</span>
              <p className="text-base font-semibold text-slate-900">
                {commonName || 'Unknown species'}
              </p>
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
