import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { apiClient } from '$common/api'
import SearchedAnimal from './SearchedAnimal'

const Web = () => {
  // --------------------- ===
  //  STATE
  // ---------------------
  const [data, setData] = useState()
  const [search, setSearch] = useState('')

  // --------------------- ===
  //  FUNCS
  // ---------------------
  const getData = async () => {
    const d = await apiClient.get(
      `/observations?project_id=41347&taxon_name=${search}`
    )
    setData(d)

    // taxon.preferred_common_name
    // field_id: 12796
  }

  // --------------------- ===
  //  RENDER
  // ---------------------
  console.log('Data', data)
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
      <SearchedAnimal results={data ? data.data.results : []} />
    </div>
  )
}

Web.defaultProps = {}

Web.propTypes = {}

export default Web
