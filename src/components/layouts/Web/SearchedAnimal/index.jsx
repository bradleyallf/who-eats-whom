import React from 'react'
import PropTypes from 'prop-types'

const SearchedAnimal = (props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { results } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div>
      {results &&
        results.map((result, i) => (
          <div key={i}>
            <p>{result.taxon.preferred_common_name}</p>
            {result.photos &&
              result.photos.map((photo, j) => {
                const url = `${photo.url.substring(
                  0,
                  photo.url.length - 10
                )}original.jpg`
                console.log('urll', url)
                return <img src={url} key={j} alt="" />
              })}
          </div>
        ))}
    </div>
  )
}

SearchedAnimal.defaultProps = {}

SearchedAnimal.propTypes = {}

export default SearchedAnimal
