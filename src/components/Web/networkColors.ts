type NetworkCategory = 'plants' | 'vertebrates' | 'invertebrates' | 'unknown'

const PLANT_TAXA = ['Plantae', 'Fungi']
const VERTEBRATE_TAXA = ['Actinopterygii', 'Amphibia', 'Reptilia', 'Aves', 'Mammalia']
const INVERTEBRATE_TAXA = ['Insecta', 'Arachnida', 'Mollusca', 'Protozoa', 'Animalia', 'Chromista']

const CATEGORY_COLORS: Record<
  NetworkCategory,
  { label: string; color: string; taxa: string[] }
> = {
  plants: {
    label: 'Plants & Fungi',
    color: '#9BD6A5', // pastel teal
    taxa: PLANT_TAXA,
  },
  vertebrates: {
    label: 'Vertebrates',
    color: '#8FBCEA', // pastel blue
    taxa: VERTEBRATE_TAXA,
  },
  invertebrates: {
    label: 'Invertebrates',
    color: '#F5B97B', // pastel orange
    taxa: INVERTEBRATE_TAXA,
  },
  unknown: {
    label: 'Other',
    color: '#C8C8C8',
    taxa: [],
  },
}

const PLANT_TAXA_SET = new Set(PLANT_TAXA)
const VERTEBRATE_TAXA_SET = new Set(VERTEBRATE_TAXA)
const INVERTEBRATE_TAXA_SET = new Set(INVERTEBRATE_TAXA)

export const getTaxonCategory = (iconicTaxon?: string): NetworkCategory => {
  if (!iconicTaxon) return 'unknown'
  if (PLANT_TAXA_SET.has(iconicTaxon)) return 'plants'
  if (VERTEBRATE_TAXA_SET.has(iconicTaxon)) return 'vertebrates'
  if (INVERTEBRATE_TAXA_SET.has(iconicTaxon)) return 'invertebrates'
  return 'unknown'
}

export const getCategoryColor = (iconicTaxon?: string) =>
  CATEGORY_COLORS[getTaxonCategory(iconicTaxon)].color

export const NETWORK_LEGEND = Object.entries(CATEGORY_COLORS).map(
  ([key, value]) => ({
    key: key as NetworkCategory,
    label: value.label,
    color: value.color,
    taxa: value.taxa,
  })
)
