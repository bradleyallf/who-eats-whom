import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { apiClient } from '$common/api'
import SearchedAnimal from './SearchedAnimal'

const types = ['Who is eaten by...', 'Who eats...']

const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState()
  const [eatenByData, setEatenByData] = useState()
  const [search, setSearch] = useState('')

  const [typeIndex, setTypeIndex] = useState(0)

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getData = async () => {
    const d = await apiClient.get(
      `/observations?project_id=41347&taxon_name=${search}`
    )
    setData(d.data.results)

    // taxon.preferred_common_name
    // field_id: 12796
  }

  const getPartnerData = async (ids) => {
    const d = await apiClient.get(`/observations?id=41347&id=${ids}`)
    setEatenByData(d.data.results)
  }

  // --------------------- ===
  //  EFFECTS
  // ---------------------
  useEffect(() => {
    if (data) {
      const observationIds = []
      data.forEach((result) => {
        result.ofvs.forEach((ofv) => {
          if (ofv.field_id === 12796) {
            const i = ofv.value.lastIndexOf('/')
            const observationId = ofv.value.substring(i + 1, ofv.value.length)
            observationIds.push(observationId)
          }
        })
      })
      getPartnerData(observationIds)
    }
  }, [data])

  // --------------------- ===
  //  RENDER
  // ---------------------
  console.log('Data', data)
  console.log('Eaten data', eatenByData)
  return (
    <>
      <div className="col-12 d-flex gap-2 justify-content-center mt-4">
        <div className="dropdown">
          <select
            className="form-select form-select-lg"
            value={typeIndex}
            onChange={(evt) => setTypeIndex(evt.target.value)}
          >
            {types.map((t, i) => (
              <option value={i} key={i}>
                {types[i]}
              </option>
            ))}
          </select>
        </div>
        <div className="d-flex gap-2">
          <input
            className="form-control form-control-lg"
            type="text"
            onChange={(evt) => setSearch(evt.target.value)}
            value={search}
            onSubmit={getData}
            placeholder="Search..."
          />
          <button
            className="btn btn-primary btn-lg"
            type="button"
            onClick={getData}
          >
            Search
          </button>
        </div>
      </div>
      {/* <div className="col-12">
        <p>Animal</p>
        <SearchedAnimal results={data || []} />
        <p>Eats</p>
        <SearchedAnimal results={eatenByData || []} />
      </div> */}
    </>
  )
}

Web.defaultProps = {}

Web.propTypes = {}

export default Web
