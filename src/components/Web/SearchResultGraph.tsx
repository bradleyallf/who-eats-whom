import { useMemo } from 'react'
import { Observation, Ofv } from './types'
import { buildColorMap } from './colorPalette'

interface Props {
  results: Observation[]
  partnerData: Record<string, Observation>
  type: Ofv['value']
  focalName: string
}

interface AggregatedStats {
  taxon: string
  observations: number
  uniqueSpecies: number
  color: string
}

const pickObservation = (
  _type: Ofv['value'],
  result: Observation,
  partner: Observation | undefined
) => {
  if (result?.taxon) return result
  return partner ?? result
}

const formatPercent = (value: number) => `${Math.round(value * 100)}%`

export const SearchResultGraph = (props: Props) => {
  const { results, partnerData, type, focalName } = props

  const stats = useMemo(() => {
    const speciesByTaxon = new Map<string, Set<string>>()
    const observationCounts = new Map<string, number>()

    results.forEach((result) => {
      const partner = partnerData[result.id]
      const observation = pickObservation(type, result, partner)
      const taxon =
        observation?.taxon?.iconic_taxon_name || 'Unidentified Taxon'
      const speciesName = observation?.taxon?.name

      observationCounts.set(taxon, (observationCounts.get(taxon) || 0) + 1)

      if (!speciesByTaxon.has(taxon)) {
        speciesByTaxon.set(taxon, new Set())
      }
      if (speciesName) {
        speciesByTaxon.get(taxon)?.add(speciesName)
      }
    })

    const colorMap = buildColorMap(Array.from(observationCounts.keys()))

    const aggregated: AggregatedStats[] = Array.from(observationCounts).map(
      ([taxon, observations]) => ({
        taxon,
        observations,
        uniqueSpecies: speciesByTaxon.get(taxon)?.size || 0,
        color: colorMap.get(taxon) || '#94a3b8',
      })
    )

    aggregated.sort((a, b) => b.observations - a.observations)
    return aggregated
  }, [partnerData, results, type])

  if (!stats.length) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No graph is available for this search yet.
      </div>
    )
  }

  const totalObservations = stats.reduce((sum, item) => sum + item.observations, 0)

  const observationSegments = stats.map((item) => ({
    ...item,
    value: item.observations,
    proportion: totalObservations ? item.observations / totalObservations : 0,
  }))

  const maxObservations = totalObservations || 1

  const yTicks = [maxObservations, Math.round(maxObservations / 2), 0]

  const summaryText = useMemo(() => {
    if (!totalObservations || !stats.length) return null
    const subject = focalName || 'This species'
    const action = type === 'eaten' ? 'is eaten by' : 'eats'
    const fragments = stats.map(
      (item) =>
        `${item.taxon} (${formatPercent(item.observations / totalObservations)})`
    )
    return `${subject} ${action} ${fragments.join(', ')}.`
  }, [focalName, stats, totalObservations, type])

  return (
    <div className="space-y-8 pb-10">
      <section className="space-y-3">
        <header>
          <h3 className="text-lg font-semibold text-slate-900">
            Observations by taxon
          </h3>
          <p className="text-sm text-slate-600">
            Showing {totalObservations} observations grouped by iconic taxon.
          </p>
        </header>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm flex-1 overflow-hidden">
            <div className="flex items-center justify-center">
              <div className="relative h-80 w-64">
                <div className="absolute bottom-0 left-0 h-full w-px bg-slate-200" />
                <div className="absolute bottom-0 left-0 w-full translate-x-12 border-b border-slate-200" />

                <div className="absolute left-[-4.2rem] top-1/2 -translate-y-1/2 rotate-[-90deg] text-sm font-medium text-slate-600">
                  Observations
                </div>

                <div className="absolute bottom-0 left-12 flex h-full w-40 flex-col-reverse">
                  {observationSegments.map((segment) => (
                    <div
                      key={`stacked-${segment.taxon}`}
                      className="relative w-full"
                      style={{
                        height: `${segment.proportion * 100}%`,
                        minHeight: segment.value ? '1.5rem' : 0,
                        backgroundColor: segment.color,
                      }}
                    >
                      <div className="absolute inset-0 flex items-center justify-center px-1 text-[10px] font-semibold text-white">
                        <span className="whitespace-nowrap">
                          {segment.value} ({formatPercent(segment.proportion)})
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="absolute bottom-0 left-0 flex h-full -translate-x-3 flex-col justify-between text-sm text-slate-500">
                  {yTicks.map((tick) => (
                    <span key={`tick-${tick}`}>{tick}</span>
                  ))}
                </div>

                <div className="absolute bottom-[-2.75rem] left-12 flex w-40 justify-center text-sm font-medium text-slate-600">
                  Taxa
                </div>
              </div>
            </div>
          </div>

          <aside className="w-full lg:w-auto flex flex-col lg:flex-row gap-4">
            <div className="rounded border border-slate-200 bg-white p-4 shadow-sm lg:min-w-[14rem]">
              <h4 className="text-sm font-semibold text-slate-900 mb-3">Legend</h4>
              <div className="flex flex-col gap-3">
                {stats.map((item) => (
                  <div
                    key={`legend-${item.taxon}`}
                    className="flex items-center gap-3 text-sm text-slate-700"
                  >
                    <span
                      className="inline-block h-3 w-3 rounded"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="font-medium">{item.taxon}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800 shadow-sm  lg:min-w-[16rem] max-w-2xl">
              <h4 className="text-sm font-semibold text-slate-900 mb-2">Summary</h4>
              {summaryText ? (
                <p className="leading-snug">{summaryText}</p>
              ) : (
                <p className="text-slate-500">Not enough data for a summary.</p>
              )}
              <p className="mt-2 text-xs text-slate-500">
                {stats.length} iconic taxa detected across {totalObservations}{' '}
                observations.
              </p>
            </div>
          </aside>
        </div>
      </section>
    </div>
  )
}
