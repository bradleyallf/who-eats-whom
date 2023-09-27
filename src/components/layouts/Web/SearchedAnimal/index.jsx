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
            <a
              href={result.uri}
              target="_blank"
              rel="noopener noreferrer"
              className="col-6 mb-3"
              key={i}
            >
              {result.photos && (
                <img
                  src={result.photos[0].url.replace(square, 'original')}
                  alt=""
                />
              )}
              <p>
                {type === 'eaten'
                  ? `${result.taxon.preferred_common_name} eats ${
                      partnerData[result.id]
                    }`
                  : `${result.taxon.preferred_common_name} is eaten by ${
                      partnerData[result.id]
                    }`}
              </p>
            </a>
          ))}
      </div>
    </>
  )
}

SearchedAnimal.defaultProps = {}

SearchedAnimal.propTypes = {}

export default SearchedAnimal
