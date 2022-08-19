import React from 'react';
import PropTypes from 'prop-types';
import {
  Outlet,
  Link,
} from 'react-router-dom';
import styles from './index.scss';

import { routePaths } from '$route/routePaths';

const Nav = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <nav className={styles.nav}>
      <Link className={styles.link} to={routePaths.home}>Home</Link>
      <Link className={styles.link} to={routePaths.about}>About</Link>
      <Link className={styles.link} to={routePaths.howToSubmit}>How to Submit</Link>
      <Link className={styles.link} to={routePaths.higherLevelChart}>Higher Level Chart</Link>
      <Link className={styles.link} to={routePaths.whoSearch}>Who Search</Link>
    </nav>
  );
};

Nav.defaultProps = {

};

Nav.propTypes = {

};

export default Nav;
