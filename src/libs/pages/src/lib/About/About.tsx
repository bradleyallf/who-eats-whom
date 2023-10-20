import img1 from './NRG-bradley.jpg'

export const About = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div className="row">
      <div className="col-12">

        <p style={{ margin: '20px 0' }}>
          How organisms in an ecosystem are connected to one another is one of the 
          most fundamental questions in ecology. The goal of Who Eats Whom 
          is to create a central database of what organisms eat, based on 
          iNaturalist observations submitted by people from all over the world. 
          Most features are coming soon!
        </p>
      </div>
      <div className="col-8 col-md-6 mb-4">
  <img src={img1} alt="" style={{ width: '30%', display: 'block', margin: '0 auto' }} />
</div>
      <div className="col-12">
        <p>
          Who Eats Whom was started in 2019 by
          <a href="https://bradleyallf.com/" style={{ color: 'blue' }}> Bradley Allf </a>
          (above) while he was a PhD student at North Carolina State University.
        </p>
      </div>
    </div>
  )
}
