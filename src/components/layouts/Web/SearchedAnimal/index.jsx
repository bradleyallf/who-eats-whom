import React, { Fragment } from 'react'
import PropTypes from 'prop-types'

const square = 'square'
const partnerFieldId = 12796

const SearchedAnimal = (props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { results, type, partnerData } = props

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <div className="row mb-4">
        <div className="col-12">
          <ul className="list-group">
            {results &&
              results.map((result, i) => (
                <li className="list-group-item" key={i}>
                  <a
                    href={result.uri}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {result.taxon.preferred_common_name}
                  </a>
                </li>
              ))}
          </ul>
        </div>
      </div>
      <div className="row">
        {results &&
          results.map((result, i) => (
            <Fragment key={i}>
              <div className="col-12">
                <p>
                  {type === 'eaten'
                    ? `${result.taxon.preferred_common_name} eats ${
                        partnerData[result.id]
                      }`
                    : `${result.taxon.preferred_common_name} is eaten by ${
                        partnerData[result.id]
                      }`}
                </p>
              </div>
              {result.photos &&
                result.photos.map((photo, j) => {
                  const i = photo.url.lastIndexOf('.')
                  const suffix = photo.url.substring(i, photo.url.length)
                  const url = `${photo.url.substring(
                    0,
                    photo.url.length - (square.length + suffix.length)
                  )}original${suffix}`
                  return (
                    <div className="col-6" key={j}>
                      <img src={url} alt="" />
                    </div>
                  )
                })}
            </Fragment>
          ))}
      </div>
    </>
  )
}

SearchedAnimal.defaultProps = {}

SearchedAnimal.propTypes = {}

export default SearchedAnimal
