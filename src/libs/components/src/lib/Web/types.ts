// Note: many of these are not a complete list of fields
export interface User {
  created_at: string
  id: number
  login: string
  spam: boolean
  suspended: boolean
  uuid: string
}

export interface Photo {
  attribution: string
  flags: string[]
  hidden: boolean
  id: number
  license_code: string
  original_dimensions: { width: number; height: number }
  url: string
}

export interface Ofv {
  datatype: string
  field_id: number
  id: number
  name: string
  name_ci: string
  user: User
  user_id: number
  uuid: string
  value: 'eaten' | 'eater'
  value_ci: string
}

export interface Taxon {
  ancestry: string
  created_at: string
  id: number
  name: string
  preferred_common_name: string
}

export interface Observation {
  community_taxon_id: number
  created_at: string
  description?: string
  ofvs: Ofv[]
  taxon: Taxon
  id: number
  uri: string
  photos: Photo[]
  uuid: string
}
