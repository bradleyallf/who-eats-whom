import React from 'react'

export interface Suggestion {
  label: string
  sciName?: string
  thumbnail?: string
}

interface Props {
  isLoading: boolean
  isOpen: boolean
  suggestions: Suggestion[]
  onClick: (s: Suggestion) => void
}

export const Dropdown = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { isLoading, isOpen, suggestions, onClick } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    (isOpen || isLoading) && (
      <div
        className="absolute p-4 flex flex-col gap-2 bg-white"
        style={{
          top: '100%',
          left: 0,
          right: 0,
          border: '1px solid #ced4da',
          textAlign: 'left',
        }}
      >
        {isLoading ? (
          <p className="text-sm text-gray-500 italic">Loading...</p>
        ) : (
          <>
            {!suggestions.length && (
              <p className="text-sm text-gray-500 italic">No suggestions</p>
            )}

            {suggestions.map((s) => (
              <button
                key={s.label}
                onClick={() => onClick(s)}
                type="button"
                className="flex items-center gap-2 text-start hover:bg-slate-100 rounded p-1"
              >
                {s.thumbnail && (
                  <img
                    src={s.thumbnail}
                    alt={s.label}
                    className="w-6 h-6 object-cover rounded"
                  />
                )}
                <span>
                  {s.label}
                  {s.sciName && (
                    <span className="text-gray-600 italic">
                      {' '}
                      ({s.sciName})
                    </span>
                  )}
                </span>
              </button>
            ))}
          </>
        )}
      </div>
    )
  )
}
