import { MouseEventHandler, ReactNode } from 'react'

interface Props {
  heading: ReactNode
  totalObservations: number
  totalSpecies: number
  taxonThumbnail?: string | null
  onDownload: MouseEventHandler<HTMLButtonElement>
  isDownloadDisabled?: boolean
  isLoading?: boolean
}

const DownloadIcon = () => (
  <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M12 3a1 1 0 0 0-1 1v8.59l-2.3-2.3a1 1 0 0 0-1.4 1.42l4 4a1 1 0 0 0 1.4 0l4-4a1 1 0 1 0-1.4-1.42L13 12.59V4a1 1 0 0 0-1-1Zm-7 14a1 1 0 0 0 0 2h14a1 1 0 1 0 0-2H5Z" />
  </svg>
)

export const SearchResultSummary = (props: Props) => {
  const {
    heading,
    totalObservations,
    totalSpecies,
    taxonThumbnail,
    onDownload,
    isDownloadDisabled,
    isLoading,
  } = props

  const StatValue = ({ value }: { value: number }) =>
    isLoading ? (
      <span
        className="inline-block h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin sm:h-5 sm:w-5"
        aria-label="Loading"
      />
    ) : (
      <span className="block text-lg font-bold leading-none sm:text-2xl">
        {value}
      </span>
    )

  return (
    <div className="sticky fixed top-0 z-[9999]">
      <div className="flex flex-col gap-2 rounded-md bg-slate-800 px-2.5 py-2.5 text-white shadow-lg sm:gap-4 sm:px-6 sm:py-4">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-6 lg:grid-cols-[minmax(20rem,30rem)_auto_auto_auto] lg:items-center lg:gap-6">
          {taxonThumbnail ? (
            <div className="flex min-w-0 items-center gap-1">
              <p className="min-w-0 flex-1 text-sm font-semibold leading-snug sm:text-lg">
                {heading}
              </p>

              <div className="flex shrink-0 items-center gap-1">
                <img
                  className="relative z-50 h-10 w-10 rounded object-cover sm:-top-1 sm:h-10 sm:w-10"
                  src={taxonThumbnail}
                  alt="nothing"
                />
              </div>
            </div>
          ) : (
            <div className="min-w-0">
              <p className="min-w-0 text-sm font-semibold leading-snug sm:text-lg">
                {heading}
              </p>
            </div>
          )}

          <div className="justify-self-center sm:justify-self-start flex w-fit flex-nowrap items-center justify-center gap-3 text-right text-white sm:justify-center sm:gap-8">
            <div className="shrink-0">
              <StatValue value={totalObservations} />
              <span className="text-[9px] uppercase tracking-wide text-slate-300 sm:text-xs md:text-xs">
                Observations
              </span>
            </div>
            <div className="shrink-0">
              <StatValue value={totalSpecies} />
              <span className="text-[9px] uppercase tracking-wide text-slate-300 sm:text-xs md:text-xs">
                Unique species
              </span>
            </div>
          </div>
          <div className="flex w-full flex-wrap justify-stretch sm:col-span-2 lg:ml-12 lg:w-auto lg:justify-end">
            <button
              type="button"
              onClick={onDownload}
              disabled={isDownloadDisabled || isLoading}
              className={`relative inline-flex w-full items-center justify-center gap-2 rounded-md px-7 py-1.5 text-xs font-semibold transition sm:-top-1 sm:px-4 sm:py-2 sm:text-sm lg:w-auto ${
                isDownloadDisabled || isLoading
                  ? 'bg-white/10 text-white/60 cursor-not-allowed'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              <DownloadIcon />
              Download CSV
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
