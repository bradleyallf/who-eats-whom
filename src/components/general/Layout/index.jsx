import React from 'react';
import PropTypes from 'prop-types';
import {
  Outlet,
  Link,
} from 'react-router-dom';

import { routePaths } from '$route/routePaths';

const Layout = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div>
      <nav className="navbar">
        <ul className="navbar-nav me-auto mb-2 mb-lg-0">
          <li className="nav-item">
            <Link className="nav-link" to={routePaths.home}>HOMEE</Link>
          </li>
        </ul>
      </nav>
      <Outlet />
    </div>
  );
};

Layout.defaultProps = {

};

Layout.propTypes = {

};

export default Layout;
