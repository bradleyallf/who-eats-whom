import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { apiClient } from '../../utils'

import { SearchedAnimal } from './SearchedAnimal'
import { Observation, Ofv } from './types'
import { Dropdown, Suggestion } from './Dropdown'

const getLastLetter = (str: string) => str[str.length - 1]

const types: Record<
  Ofv['value'],
  {
    label: string
    value: string
    key: Ofv['value']
  }
> = {
  eaten: {
    label: 'Who eats...',
    value: 'thing being eaten',
    key: 'eaten',
  },
  eater: {
    label: 'Who is eaten by...',
    value: 'eater',
    key: 'eater',
  },
}

const partnerFieldId = 12796
const projectId = 41347
const eaterEatenFieldId = 12795 // in the ofvs array
const observationFieldsParam = [
  'id',
  'uri',
  'ofvs',
  'taxon',
  'photos',
  'place_country_name',
  'place_state_name',
  'place_county_name',
  'place_town_name',
].join(',')

export const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState<Observation[]>([])
  const [partnerData, setPartnerData] = useState<Record<string, Observation>>({})
  const [eatenByData, setEatenByData] = useState<Observation[]>()

  const [search, setSearch] = useState('')
  const [locationInput, setLocationInput] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [isSearchLoading, setIsSearchLoading] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [shouldDisplayResults, setShouldDisplayResults] = useState(false)

  const [type, setType] = useState(types.eaten.key)

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getCountry = (observation: Observation | undefined) =>
    observation?.place_country_name?.trim().toLowerCase()

  const getPartnerData = async (ids: string[]) => {
    const d = await apiClient.get(
      `/observations?id=${ids}&quality_grade=research&per_page=200&fields=${observationFieldsParam}`
    )
    setEatenByData(d.data.results)
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------
  useEffect(() => {
    if (!shouldDisplayResults || !data.length) return

    // FILTER DATA
    const filteredData: Observation[] = []
    data.forEach((d) => {
      const typeObj = d.ofvs.find((o) => o.field_id === eaterEatenFieldId)
      // "eater" or "organism being eaten" (previously "thing being eaten")
      if (!typeObj) return
      //console.log('id:',d.id, 'typeObj:', typeObj.value, 'type:', type, 'typeValue:', types[type].value)

      if (getLastLetter(typeObj.value) === getLastLetter(types[type].value)) {
        filteredData.push(d)
      }
    })

    const observationIds: string[] = []
    const partnerD: Record<string, Observation> = {}
    filteredData.forEach((result) => {
      result.ofvs.forEach((ofv) => {
        
        if (ofv.field_id === partnerFieldId && ofv.value.includes('/observations/')) {
          /*
          console.log("...--->" + ofv.value)
          const i = ofv.value.lastIndexOf('/')
          const observationId = ofv.value.substring(i + 1, ofv.value.length)
          partnerD[observationId] = result
          console.log(observationId)
          observationIds.push(observationId)
          */
        
         const matches = ofv.value.match(/\/observations\/(\d+)/g)
          if (matches) {
            matches.forEach((match) => {
              const observationId = match.split('/').pop()!
              partnerD[observationId] = result
              observationIds.push(observationId)
            })
          }
          
        }
      })
    })
    setPartnerData(partnerD)
    getPartnerData(observationIds)
  }, [data, type, shouldDisplayResults])

  useEffect(() => {
    let canceled = false
    if (search.length < 3) {
      setIsDropdownOpen(false)
      
    }
    setIsSearchLoading(true)
    apiClient
      //#&per_page=200
      .get(
        `/observations?project_id=${projectId}&taxon_name=${search}&quality_grade=research&per_page=200&fields=${observationFieldsParam}`
      )
      .then((d) => {
        if (!canceled) {
          setData(d.data.results)
          setIsSearchLoading(false)
        }
      })
    return () => {
      canceled = true
    }
  }, [search])

  useEffect(() => {
    if (isDropdownOpen) {
      const close = () => setIsDropdownOpen(false)
      document.addEventListener('click', close)
      document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' || evt.key === 'Enter') close()
      })
      return () => {
        document.removeEventListener('click', close)
      }
    }
  }, [isDropdownOpen])

  // --------------------- ===
  //  HANDLERS
  // ---------------------
  const handleInputChange = (evt: ChangeEvent<HTMLInputElement>) => {
    setSearch(evt.target.value)
    setIsDropdownOpen(true)
    setShouldDisplayResults(false)
  }

  const handleLocationChange = (evt: ChangeEvent<HTMLInputElement>) => {
    setLocationInput(evt.target.value)
    setShouldDisplayResults(false)
  }

  const handleSubmit = (evt: FormEvent<HTMLFormElement>) => {
    evt.preventDefault()
    setLocationFilter(locationInput.trim().toLowerCase())
    setIsDropdownOpen(false)
    setShouldDisplayResults(true)
  }

  const suggestions: Suggestion[] = Array.from(
    data.reduce((map, d) => {
      const name = d.taxon.preferred_common_name
      if (!name) return map
      if (!map.has(name)) {
        map.set(name, {
          label: name,
          sciName: d.taxon.name,
          thumbnail:
            d.taxon.default_photo?.square_url ||
            d.taxon.default_photo?.url ||
            undefined,
        })
      }
      return map
    }, new Map<string, Suggestion>())
  ).map(([, v]) => v)

  const filteredResults = shouldDisplayResults
    ? (eatenByData || []).filter((result) => {
        if (!locationFilter) return true

        const primaryObservation =
          type === 'eater' ? result : partnerData[result.id]

        const primaryCountry = getCountry(primaryObservation)
        if (primaryCountry) {
          return primaryCountry.includes(locationFilter)
        }

        const secondaryObservation =
          type === 'eater' ? partnerData[result.id] : result
        const secondaryCountry = getCountry(secondaryObservation)
        return secondaryCountry ? secondaryCountry.includes(locationFilter) : false
      })
    : []

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <div className="mt-12">
        <div className="flex justify-center gap-2 w-full">
          {/* type selector */}
          <select
            className="form-select form-select-lg w-full max-w-[12rem]"
            value={type}
            onChange={(evt) => {
              const { value } = evt.target
              if (value === 'eaten' || value === 'eater') setType(value)
            }}
          >
            {(Object.keys(types) as Array<Ofv['value']>).map((key) => (
              <option value={key} key={key}>
                {types[key].label}
              </option>
            ))}
          </select>

          {/* search box + dropdown */}
          <form
            className="w-full max-w-3xl flex items-stretch gap-2"
            onSubmit={handleSubmit}
          >
            <div className="relative flex-1" style={{ zIndex: 2 }}>
              <input
                className="w-full"
                type="text"
                onChange={handleInputChange}
                value={search}
                placeholder="Search..."
              />

              <Dropdown
                isLoading={isSearchLoading}
                isOpen={isDropdownOpen}
                suggestions={suggestions}
                onClick={(s) => {
                  setSearch(s.label)
                  setIsDropdownOpen(false)
                  setShouldDisplayResults(false)
                }}
              />
            </div>
            <input
              className="w-full max-w-xs"
              type="text"
              value={locationInput}
              onChange={handleLocationChange}
              placeholder="Location"
            />
            <button
              type="submit"
              className="px-4 bg-orange-500 text-white font-semibold rounded"
            >
              Go
            </button>
          </form>
        </div>
      </div>


      {shouldDisplayResults && (
        <div className="col-12 mt-20">
          <SearchedAnimal
            results={filteredResults}
            partnerData={partnerData}
            type={type}
          />
        </div>
      )}
    </>
  )
}
