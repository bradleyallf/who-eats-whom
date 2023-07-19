import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { apiClient } from '$common/api'
import SearchedAnimal from './SearchedAnimal'

const types = {
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

const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState()
  const [partnerData, setPartnerData] = useState({})
  const [eatenByData, setEatenByData] = useState()
  const [search, setSearch] = useState('')

  const [type, setType] = useState(types.eaten.key)

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getData = async (canceled) => {
    const d = await apiClient.get(
      `/observations?project_id=41347&taxon_name=${search}&quality_grade=research`
    )
    setData(d.data.results)

    // taxon.preferred_common_name
    // field_id: 12796
  }

  const getPartnerData = async (ids) => {
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
    const filteredData = []
    data.forEach((d) => {
      const typeObj = d.ofvs.find((o) => o.field_id === eaterEatenFieldId)
      if (typeObj?.value === types[type].value) {
        filteredData.push(d)
      }
    })

    console.log('FILTER', filteredData)

    const observationIds = []
    const partnerD = {}
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
  }, [data])

  useEffect(() => {
    let canceled = false
    if (search.length < 3) return
    apiClient
      .get(
        `/observations?project_id=41347&taxon_name=${search}&quality_grade=research`
      )
      .then((d) => {
        if (!canceled) setData(d.data.results)
      })
    return () => {
      canceled = true
    }
  }, [search])

  // --------------------- ===
  //  RENDER
  // ---------------------
  console.log('Data', data)
  console.log('Eaten data', eatenByData)

  const suggestions = [
    ...new Set(data?.map((d) => d.taxon.preferred_common_name)),
  ]
  console.log('suggestions :>> ', suggestions)

  return (
    <>
      <div className="col-12 d-flex gap-2 justify-content-center mt-4">
        <div className="dropdown">
          <select
            className="form-select form-select-lg"
            value={type}
            onChange={(evt) => setType(evt.target.value)}
          >
            {Object.keys(types).map((key) => (
              <option value={key} key={key}>
                {types[key].label}
              </option>
            ))}
          </select>
        </div>
        <form className="d-flex gap-2 mb-4" onSubmit={getData}>
          <div className="position-relative" style={{ zIndex: 2 }}>
            <input
              className="form-control form-control-lg"
              type="text"
              onChange={(evt) => setSearch(evt.target.value)}
              value={search}
              onSubmit={getData}
              placeholder="Search..."
            />
            {suggestions.length > 0 && (
              <div
                className="position-absolute p-4 d-flex flex-column gap-2 bg-white"
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
            )}
          </div>
          <button
            className="btn btn-primary btn-lg"
            type="button"
            onClick={getData}
          >
            Search
          </button>
        </form>
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

Web.defaultProps = {}

Web.propTypes = {}

export default Web
