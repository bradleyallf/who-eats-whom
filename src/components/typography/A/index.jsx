import React from 'react';
import PropTypes from 'prop-types';

// External link
const A = (props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const {
    href,
    children,
  } = props;

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <a href={href}>
      {children}
    </a>
  );
};

A.defaultProps = {

};

A.propTypes = {
  href: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
};

export default A;
