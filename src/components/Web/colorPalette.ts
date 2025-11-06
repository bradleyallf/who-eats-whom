export const COLOR_PALETTE = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
  '#bcbd22',
  '#17becf',
  '#393b79',
  '#637939',
  '#8c6d31',
  '#843c39',
  '#7b4173',
  '#3182bd',
  '#e6550d',
  '#31a354',
  '#756bb1',
  '#636363',
]

export const buildColorMap = (taxa: string[]) => {
  const sorted = [...new Set(taxa)]
    .filter((taxon) => taxon && taxon.trim().length > 0)
    .sort((a, b) => a.localeCompare(b))

  const map = new Map<string, string>()
  sorted.forEach((taxon, index) => {
    map.set(taxon, COLOR_PALETTE[index % COLOR_PALETTE.length])
  })

  return map
}
