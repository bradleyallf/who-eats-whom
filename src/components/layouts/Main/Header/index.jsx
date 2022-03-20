import React from 'react';
import PropTypes from 'prop-types';
import H1 from '$components/typography/H1';
import H2 from '$components/typography/H2';
import Nav from './Nav';

import styles from './index.scss';

const Header = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <header>
      <section className={styles.section}>
        <div>
          <H1>Who Eats Who</H1>
          <H2>A planetary food web</H2>
        </div>
        <Nav />
      </section>
    </header>
  );
};

Header.defaultProps = {

};

Header.propTypes = {

};

export default Header;