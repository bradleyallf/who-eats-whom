import React, { useEffect, useState } from 'react'
import { apiClient } from '../../utils'
import { Dropdown, Suggestion } from './Dropdown'

interface SpeciesSearchResult {
  id?: number
  taxon_id?: number
  name?: string
  scientific_name?: string
  preferred_common_name?: string
  common_name?: string
  default_photo?: {
    square_url?: string
    small_url?: string
    url?: string
  }
}

interface Props {
  value: string
  onChange: (value: string) => void
  onSelect: (suggestion: Suggestion) => void
  placeholder?: string
  ariaLabel?: string
  className?: string
}

// Text input with the same species autocomplete dropdown as the main search.
export const TaxonSearchInput = (props: Props) => {
  const { value, onChange, onSelect, placeholder, ariaLabel, className } = props

  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    let canceled = false
    const query = value.trim()

    if (query.length < 3) {
      setSuggestions([])
      setIsLoading(false)
      return () => {
        canceled = true
      }
    }

    setIsLoading(true)

    const params = new URLSearchParams({ q: query, limit: '25' })

    apiClient
      .get(`/v1/species/search?${params.toString()}`)
      .then((d) => {
        if (canceled) return
        const seen = new Set<string>()
        const mapped: Suggestion[] = []
        ;(d.data.results as SpeciesSearchResult[] | undefined)?.forEach((r) => {
          const sciName = r.scientific_name ?? r.name
          const label = r.common_name ?? r.preferred_common_name ?? sciName
          const id = r.taxon_id ?? r.id
          if (!label || id === undefined || seen.has(label.toLowerCase()))
            return
          seen.add(label.toLowerCase())
          const photo = r.default_photo
          mapped.push({
            label,
            id,
            sciName,
            thumbnail:
              photo?.square_url || photo?.small_url || photo?.url || undefined,
          })
        })
        setSuggestions(mapped)
        setIsLoading(false)
      })
      .catch(() => {
        if (canceled) return
        setSuggestions([])
        setIsLoading(false)
      })

    return () => {
      canceled = true
    }
  }, [value])

  // Close when clicking outside or pressing Escape/Enter
  useEffect(() => {
    if (!isOpen) return
    const close = () => setIsOpen(false)
    const onKey = (evt: KeyboardEvent) => {
      if (evt.key === 'Escape' || evt.key === 'Enter') close()
    }
    document.addEventListener('click', close)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', close)
      document.removeEventListener('keydown', onKey)
    }
  }, [isOpen])

  return (
    <div
      className="relative w-full min-w-0 sm:min-w-[10rem] sm:flex-1"
      style={{ zIndex: 1 }}
    >
      <input
        className={className}
        type="text"
        aria-label={ariaLabel}
        value={value}
        placeholder={placeholder}
        onChange={(evt) => {
          onChange(evt.target.value)
          setIsOpen(evt.target.value.trim().length >= 1)
        }}
      />
      <Dropdown
        isLoading={isLoading}
        isOpen={isOpen}
        suggestions={value.trim().length >= 3 ? suggestions : []}
        onClick={(s) => {
          onSelect(s)
          setIsOpen(false)
        }}
      />
    </div>
  )
}
