export const HowToSubmit = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div>
      To add your own observations to Who Eats Whom, first sign up for
      iNaturalist, then
      <a href="https://www.inaturalist.org/projects/who-eats-whom" style={{ color: 'blue' }}>
        {' '}
        join our project here.{' '}
      </a>
      For an observation to be included in the database, you must submit two observations
      to the project: one observation of the "eating" organism and another observation 
      of the organism being eaten. If both these observations are identified to 
      "research-grade" by the iNaturalist community, the observation will be added to 
      the Who Eats Whom database on this website.
    </div>
  )
}
