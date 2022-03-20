import React from 'react';
import PropTypes from 'prop-types';
import Title from '$components/typography/Title';
import Subtitle from '$components/typography/Subtitle';
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
          <Title>Who Eats Whom</Title>
          <Subtitle>A planetary food web</Subtitle>
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