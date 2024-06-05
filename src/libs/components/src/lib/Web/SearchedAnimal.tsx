import { AnimalName } from './AnimalName'
import { Observation, Ofv } from './types'

interface Props {
  results: Observation[]
  type: Ofv['value']
  partnerData: any
}

const square = 'square'
const partnerFieldId = 12796

const getCommonName = (result: Observation) =>
  result.taxon.preferred_common_name
const sciName = (result: Observation) => result.taxon.name

export const SearchedAnimal = (props: Props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const { results, type, partnerData } = props

  console.log('partnerData :>> ', partnerData)

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div className="w-full grid grid-cols-2 gap-3">
      {results &&
        results.map(
          (result, i) =>
            partnerData[result.id] && (
              <a
                href={result.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="basis-1/2"
                key={i}
              >
                {result.photos && (
                  <img
                    src={result.photos[0].url.replace(square, 'original')}
                    alt=""
                  />
                )}

                <span>
                  <AnimalName
                    commonName={getCommonName(result)}
                    sciName={sciName(result)}
                  />{' '}
                  {type === 'eaten' ? 'eats' : 'is eaten by'}{' '}
                  <AnimalName commonName={partnerData[result.id]} />
                </span>
              </a>
            )
        )}
    </div>
  )
}
