import React from 'react'
import PropTypes from 'prop-types'

const square = 'square'

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
                const i = photo.url.lastIndexOf('.')
                const suffix = photo.url.substring(i, photo.url.length)
                const url = `${photo.url.substring(
                  0,
                  photo.url.length - (square.length + suffix.length)
                )}original${suffix}`
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
