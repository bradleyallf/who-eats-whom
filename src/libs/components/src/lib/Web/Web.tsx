import { ChangeEvent, useEffect, useState } from 'react'
import { apiClient } from '@utils'

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

export const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState<Observation[]>([])
  const [partnerData, setPartnerData] = useState<Record<string, Observation>>({})
  const [eatenByData, setEatenByData] = useState<Observation[]>()

  const [search, setSearch] = useState('')
  const [isSearchLoading, setIsSearchLoading] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

  const [type, setType] = useState(types.eaten.key)

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getPartnerData = async (ids: string[]) => {
    const d = await apiClient.get(
      `/observations?id=${ids}&quality_grade=research&per_page=200`
    )
    setEatenByData(d.data.results)
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------
  useEffect(() => {
    if (!data.length) return

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
  }, [data, type])

  useEffect(() => {
    let canceled = false
    if (search.length < 3) {
      setIsDropdownOpen(false)
      
    }
    setIsSearchLoading(true)
    apiClient
      //#&per_page=200
      .get(
        `/observations?project_id=${projectId}&taxon_name=${search}&quality_grade=research&per_page=200`
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
  }

  const suggestions: Suggestion[] = Array.from(
    data.reduce((map, d) => {
      const name = d.taxon.preferred_common_name
      if (!name) return map
      if (!map.has(name)) {
        map.set(name, {
          label: name,
          thumbnail:
            d.taxon.default_photo?.square_url ||
            d.taxon.default_photo?.url ||
            undefined,
        })
      }
      return map
    }, new Map<string, Suggestion>())
  ).map(([, v]) => v)

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
            className="w-full max-w-md"
            onSubmit={(e) => {
              e.preventDefault()
            }}
          >
            <div className="relative w-full" style={{ zIndex: 2 }}>
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
                }}
              />
            </div>
          </form>
        </div>
      </div>
      

      <div className="col-12 mt-20">
        <SearchedAnimal
          results={eatenByData || []}
          partnerData={partnerData}
          type={type}
        />
      </div>
    </>
  )
}
