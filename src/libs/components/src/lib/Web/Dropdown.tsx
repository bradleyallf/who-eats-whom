interface Props {
  suggestions: string[]
  setSearch: (s: string) => void
}

export const Dropdown = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { suggestions, setSearch } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    suggestions.length > 0 && (
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
        {suggestions?.map((s) => (
          <button
            key={s}
            onClick={() => {
              setSearch(s)
            }}
            type="button"
            className="text-start"
          >
            {s}
          </button>
        ))}
      </div>
    )
  )
}
