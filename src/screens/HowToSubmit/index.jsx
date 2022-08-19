import React from 'react';
import PropTypes from 'prop-types';
import A from '$components/typography/A';

const HowToSubmit = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div>
      <header className="entry-header alignwide">
        <h1 className="entry-title">How to Submit</h1>
      </header>
      To add your own observations to Who Eats Whom, first sign up for iNaturalist, then
      <A href="https://www.inaturalist.org/projects/who-eats-whom"> join our project here. </A>
    </div>
  );
};

HowToSubmit.defaultProps = {

};

HowToSubmit.propTypes = {

};

export default HowToSubmit;
