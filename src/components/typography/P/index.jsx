import React from 'react';
import PropTypes from 'prop-types';
import styles from './index.scss';

const P = (props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const {
    style,
    children,
  } = props;

  // --------------------- ===
  //  RENDER
  // ---------------------
  const italic = style === 'italic' ? styles.italic : '';
  return (
    <P className={`
      ${styles.p}
      ${italic}
    `}
    >
      {children}
    </P>
  );
};

P.defaultProps = {
  style: 'normal',
};

P.propTypes = {
  style: PropTypes.string,
  children: PropTypes.node.isRequired,
};

export default P;
