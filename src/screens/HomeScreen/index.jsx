import React from 'react'
import styles from './index.scss'

import P from '$components/typography/P'
import A from '$components/typography/A'
import Web from '$components/layouts/Web'

// importing our thing variable from brad/sayl test in the "common" folder
// import { lizard, someFunc } from '$common/test';

// P was breaking
const HomeScreen = () => {
  // console.log(lizard, "this is a lizard")
  //  const favoriteColor = someFunc("red")
  //  console.log("someString", favoriteColor)
  return (
    <>
      <div className="col-12 text-center">
        <h1 className="h1">Who Eats Whom</h1>
        <h2 className="h2">
          Enter the name of a plant, animal or fungus to see what it eats.
        </h2>
        <A href="https://www.inaturalist.org/projects/who-eats-whom">
          See the project on iNaturalist
        </A>
      </div>
      <Web />
    </>
  )
}

export default HomeScreen
