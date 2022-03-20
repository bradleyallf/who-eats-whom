import React from 'react';
import PropTypes from 'prop-types';
import { Outlet } from 'react-router-dom';

import Header from '$components/layouts/Main/Header';
import Footer from '$components/layouts/Main/Footer';

const Main = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <Header />
      <Outlet />
      <Footer />
    </>
  );
};

Main.defaultProps = {

};

Main.propTypes = {

};

export default Main;
