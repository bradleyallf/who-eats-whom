import React from 'react'

const IMAGES = [
  'CommonNames.JPG',
  'Countries.JPG',
  'IconicTaxonName.JPG',
  'ObservationsOverTime.JPG',
  'Predator-Prey.JPG',
  'Predator.JPG',
  'Prey.JPG',
  'Seasons.JPG',
  'TaxonPredator-Prey.JPG',
  'Username.JPG',
  'USGone.JPG'
]

export const SummaryStatistics = () => {
  return (
    <div className="gallery-page px-4 md:px-8 mt-12">
      <h1 className="text-3xl font-bold mb-6 text-center">DataSet Statistics</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
        {IMAGES.map((filename) => (
          <div key={filename} className="border rounded shadow p-2">
            {}
            <img
              src={`/Pictures/${filename}`}
              alt={filename}
              className="w-full h-auto"
            />
            
          </div>
        ))}
      </div>
    </div>
  )
}