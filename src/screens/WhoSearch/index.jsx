import React from 'react';
import PropTypes from 'prop-types';

const WhoSearch = () => {
  return (
    <>
      <div>Type the common or scientific name of any species on earth.</div>
      <input type="text" />
      <button>Search</button>
    </>
  );
};

WhoSearch.defaultProps = {

};

WhoSearch.propTypes = {

};

export default WhoSearch;
