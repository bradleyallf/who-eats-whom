import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { apiClient } from '$common/api'
import SearchedAnimal from './SearchedAnimal'

const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState()
  const [eatenByData, setEatenByData] = useState()
  const [search, setSearch] = useState('')

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
    <div>
      <input
        type="text"
        onChange={(evt) => setSearch(evt.target.value)}
        value={search}
        onSubmit={getData}
      />
      <button type="button" onClick={getData}>
        Search
      </button>
      <p>Animal</p>
      <SearchedAnimal results={data || []} />
      <p>Eats</p>
      <SearchedAnimal results={eatenByData || []} />
    </div>
  )
}

Web.defaultProps = {}

Web.propTypes = {}

export default Web
