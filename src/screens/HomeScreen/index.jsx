import React from 'react';
import styles from './index.scss';

import P from '$components/typography/P';
import A from '$components/typography/A';

// importing our thing variable from brad/sayl test in the "common" folder
import { lizard, someFunc } from '$common/test';

// P was breaking
const HomeScreen = () => {
  console.log(lizard, "this is a lizard")
  const favoriteColor = someFunc("red")
  console.log("someString", favoriteColor)
  return (
    <div>
{lizard}
        <A href="https://www.inaturalist.org/projects/who-eats-whom">
          Who Eats Whom
        </A>

    </div>
  );
};

export default HomeScreen;
