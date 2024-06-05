interface Props {
  isLoading: boolean
  isOpen: boolean
  suggestions: string[]
  onClick: (s: string) => void
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
            {!suggestions?.length && (
              <p className="text-sm text-gray-500 italic">No suggestions</p>
            )}
            {suggestions?.map((s) => (
              <button
                key={s}
                onClick={() => {
                  onClick(s)
                }}
                type="button"
                className="text-start"
              >
                {s}
              </button>
            ))}
          </>
        )}
      </div>
    )
  )
}
