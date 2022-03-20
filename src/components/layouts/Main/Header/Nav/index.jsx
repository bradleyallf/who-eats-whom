import React from 'react';
import PropTypes from 'prop-types';
import {
  Outlet,
  Link,
} from 'react-router-dom';

import { routePaths } from '$route/routePaths';

const Nav = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <nav className="navbar">
      <ul className="navbar-nav me-auto mb-2 mb-lg-0">
        <li className="nav-item">
          <Link className="nav-link" to={routePaths.home}>HOMEE</Link>
        </li>
      </ul>
    </nav>
  );
};

Nav.defaultProps = {

};

Nav.propTypes = {

};

export default Nav;
