import { ChangeEvent, useEffect, useState } from 'react'
import { apiClient } from '@utils'

import { SearchedAnimal } from './SearchedAnimal'
import { Observation, Ofv } from './types'
import { Dropdown } from './Dropdown'

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
  const [partnerData, setPartnerData] = useState({})
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
      `/observations?id=${ids}&quality_grade=research`
    )
    setEatenByData(d.data.results)
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------
  useEffect(() => {
    if (!data) return

    // FILTER DATA
    const filteredData: Observation[] = []
    data.forEach((d) => {
      const typeObj = d.ofvs.find((o) => o.field_id === eaterEatenFieldId)
      // "eater" or "organism being eaten" (previously "thing being eaten")
      if (!typeObj) return
      if (getLastLetter(typeObj.value) === getLastLetter(types[type].value)) {
        filteredData.push(d)
      }
    })

    const observationIds: string[] = []
    const partnerD: Record<string, string> = {}
    filteredData.forEach((result) => {
      result.ofvs.forEach((ofv) => {
        if (ofv.field_id === partnerFieldId) {
          const i = ofv.value.lastIndexOf('/')
          const observationId = ofv.value.substring(i + 1, ofv.value.length)
          partnerD[observationId] = result.taxon.preferred_common_name
          observationIds.push(observationId)
        }
      })
    })
    setPartnerData(partnerD)
    getPartnerData(observationIds)
  }, [data, type])

  useEffect(() => {
    let canceled = false
    if (search.length < 3) return
    setIsSearchLoading(true)
    apiClient
      .get(
        `/observations?project_id=${projectId}&taxon_name=${search}&quality_grade=research`
      )
      .then((d) => {
        if (!canceled) setData(d.data.results)
      })
      .finally(() => {
        setIsSearchLoading(false)
      })
    return () => {
      canceled = true
    }
  }, [search])

  useEffect(() => {
    if (isDropdownOpen) {
      document.addEventListener('click', () => {
        setIsDropdownOpen(false)
      })
      document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' || evt.key === 'Enter') {
          setIsDropdownOpen(false)
        }
      })
    }
    return () => {
      document.removeEventListener('click', () => {
        setIsDropdownOpen(false)
      })
    }
  }, [isDropdownOpen])

  // --------------------- ===
  //  HANDLERS
  // ---------------------
  const handleInputChange = (evt: ChangeEvent<HTMLInputElement>) => {
    setSearch(evt.target.value)
    setIsDropdownOpen(true)
  }

  // --------------------- ===
  //  RENDER
  // ---------------------
  const suggestions = [
    ...new Set(data?.map((d) => d.taxon.preferred_common_name)),
  ]

  return (
    <>
      <div className="mt-12">
        <div className="flex justify-center gap-2 w-full">
          <select
            className="form-select form-select-lg w-full max-w-[12rem]"
            value={type}
            onChange={(evt) => {
              const { value } = evt.target
              // extra ts protection
              if (value === 'eaten' || value === 'eater') {
                setType(value)
              }
            }}
          >
            {(Object.keys(types) as Array<Ofv['value']>).map((key) => (
              <option value={key} key={key}>
                {types[key].label}
              </option>
            ))}
          </select>
          <form className="w-full max-w-md">
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
                onClick={(s: string) => {
                  setSearch(s)
                }}
              />
            </div>
          </form>
        </div>
      </div>
      <div className="col-12">
        <SearchedAnimal
          results={eatenByData || []}
          partnerData={partnerData}
          type={type}
        />
      </div>
    </>
  )
}
