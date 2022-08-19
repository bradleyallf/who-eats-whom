import React from 'react'
import img1 from '$images/NRG-bradley.jpg'
import A from '$components/typography/A'

const About = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div>
      <header className="entry-header alignwide">
        <h1 className="entry-title">About</h1>
      </header>
      <p>
        One of the most important questions in ecology is this: what do the
        different species in an ecosystem eat? By better understanding the food
        web we can better understand how all the species in an ecosystem
        contribute to its function. It can also allow us to make better-informed
        conservation decisions. For instance, if we know that a particular mouse
        species in an alpine forest is eaten by nearly every predator in the
        landscape, then focusing on protecting that mouse might be the best use
        of park resources, as the survival of that species is linked to so many
        other species.
      </p>
      <p>
        Traditionally, observations of what an animal eats are reported in small
        scientific journals with limited readership. “Who Eats Whom?” is looking
        to change that by creating the first-ever central hub of animal feeding
        ecology, so that anyone can search for a species and find out what it
        eats.
      </p>
      <p>
        You can contribute to Who Eats Whom by sending us your observations of
        an animal eating a plant, fungus, or another animal on iNaturalist! This
        website is under construction but it will eventually allow anyone to
        search for a species and find out how it’s connected to other species in
        its ecosystem– who eats that species and who that species eats.
      </p>
      <p>
        <img src={img1} alt="" />
      </p>
      <p>
        Who Eats Whom was started in 2019 by
        <A href="https://bradleyallf.com/"> Bradley Allf </A>
        (above) while he was a PhD student at North Carolina State University
        studying citizen science.
      </p>
    </div>
  )
}

About.defaultProps = {}

About.propTypes = {}

export default About
