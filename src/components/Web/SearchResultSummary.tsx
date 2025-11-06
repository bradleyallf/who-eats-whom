import { MouseEventHandler } from 'react'

interface Props {
  heading: string
  totalObservations: number
  totalSpecies: number
  onDownload: MouseEventHandler<HTMLButtonElement>
  isDownloadDisabled?: boolean
}

const DownloadIcon = () => (
  <svg
    aria-hidden
    viewBox="0 0 24 24"
    className="h-4 w-4"
    fill="currentColor"
  >
    <path d="M12 3a1 1 0 0 0-1 1v8.59l-2.3-2.3a1 1 0 0 0-1.4 1.42l4 4a1 1 0 0 0 1.4 0l4-4a1 1 0 1 0-1.4-1.42L13 12.59V4a1 1 0 0 0-1-1Zm-7 14a1 1 0 0 0 0 2h14a1 1 0 1 0 0-2H5Z" />
  </svg>
)

export const SearchResultSummary = (props: Props) => {
  const {
    heading,
    totalObservations,
    totalSpecies,
    onDownload,
    isDownloadDisabled,
  } = props

  return (
    <div className="sticky top-0 z-30">
      <div className="flex flex-wrap items-center gap-6 rounded-md bg-slate-800 px-6 py-4 text-white shadow-lg">
        <div className="flex min-w-0 flex-1 items-center gap-8">
          <div className="min-w-0 max-w-full">
            <p className="text-lg font-semibold leading-snug">{heading}</p>
          </div>
          <div className="flex items-end gap-6 text-right text-white">
            <div>
              <span className="block text-2xl font-bold leading-none">{totalObservations}</span>
              <span className="text-xs uppercase tracking-wide text-slate-300">
                Observations
              </span>
            </div>
            <div>
              <span className="block text-2xl font-bold leading-none">{totalSpecies}</span>
              <span className="text-xs uppercase tracking-wide text-slate-300">
                Unique species
              </span>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onDownload}
          disabled={isDownloadDisabled}
          className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition ${
            isDownloadDisabled
              ? 'bg-white/10 text-white/60 cursor-not-allowed'
              : 'bg-white/10 text-white hover:bg-white/20'
          }`}
        >
          <DownloadIcon />
          Download CSV
        </button>
      </div>
    </div>
  )
}
