import React from 'react';
import styles from './index.scss';

import P from '$components/typography/P';
import A from '$components/typography/A';


// P was breaking
const HomeScreen = () => {
  return (
    <div>

        <A href="https://www.inaturalist.org/projects/who-eats-whom">
          Who Eats Whom
        </A>

    </div>
  );
};

export default HomeScreen;
