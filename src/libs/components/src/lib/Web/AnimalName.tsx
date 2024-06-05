interface Props {
  commonName: string
  sciName?: string
}

export const AnimalName = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { commonName, sciName } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <span>
      {commonName}
      {sciName && (
        <span className="text-gray-600 italic">
          &nbsp;{commonName ? `(${sciName})` : sciName}
        </span>
      )}
    </span>
  )
}
