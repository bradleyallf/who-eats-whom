import React from 'react';
import PropTypes from 'prop-types';
import { Outlet } from 'react-router-dom';
import styles from './index.scss';

import Header from '$components/layouts/Main/Header';
import Footer from '$components/layouts/Main/Footer';

const Main = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <>
      <Header />
      <main className="container">
        <Outlet />
      </main>
      <Footer />
    </>
  );
};

Main.defaultProps = {

};

Main.propTypes = {

};

export default Main;
