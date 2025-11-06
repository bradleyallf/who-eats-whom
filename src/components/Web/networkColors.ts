type NetworkCategory = 'plants' | 'vertebrates' | 'invertebrates' | 'unknown'

const CATEGORY_COLORS: Record<NetworkCategory, { label: string; color: string }> = {
  plants: {
    label: 'Plants & Fungi - Chromista, Fungi, Plantae',
    color: '#9BD6A5', // pastel teal
  },
  vertebrates: {
    label: 'Vertebrates - Actinopterygii, Amphibia, Aves, Mammalia, Reptilia',
    color: '#8FBCEA', // pastel blue
  },
  invertebrates: {
    label: 'Invertebrates - Animalia, Arachnida, Insecta, Mollusca, Protozoa',
    color: '#F5B97B', // pastel orange
  },
  unknown: {
    label: 'Other',
    color: '#C8C8C8',
  },
}

const PLANT_TAXA = new Set(['Plantae', 'Fungi', 'Chromista'])
const VERTEBRATE_TAXA = new Set([
  'Actinopterygii',
  'Amphibia',
  'Reptilia',
  'Aves',
  'Mammalia',
])
const INVERTEBRATE_TAXA = new Set([
  'Insecta',
  'Arachnida',
  'Mollusca',
  'Protozoa',
  'Animalia',
])

export const getTaxonCategory = (iconicTaxon?: string): NetworkCategory => {
  if (!iconicTaxon) return 'unknown'
  if (PLANT_TAXA.has(iconicTaxon)) return 'plants'
  if (VERTEBRATE_TAXA.has(iconicTaxon)) return 'vertebrates'
  if (INVERTEBRATE_TAXA.has(iconicTaxon)) return 'invertebrates'
  return 'unknown'
}

export const getCategoryColor = (iconicTaxon?: string) =>
  CATEGORY_COLORS[getTaxonCategory(iconicTaxon)].color

export const NETWORK_LEGEND = Object.entries(CATEGORY_COLORS).map(
  ([key, value]) => ({
    key: key as NetworkCategory,
    label: value.label,
    color: value.color,
  })
)
