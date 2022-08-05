import React from 'react';
import PropTypes from 'prop-types';

const HowToSubmit = () => {
  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <div className="row">
      <div className="col-12">
        <p>
          this is a paragraph. I'm writing in html
        </p>
      </div>
      normal text. good to line up the tags i.e. greater than less than symbols. Turned on line-wrap. 
      tab and shift-tab 

    </div>
  );
};

HowToSubmit.defaultProps = {

};

HowToSubmit.propTypes = {

};

export default HowToSubmit;