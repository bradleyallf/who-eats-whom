import React from 'react';
import PropTypes from 'prop-types';
import styles from './index.scss';

const Subtitle = (props) => {
  // --------------------- ===
  //  PROPS
  // ---------------------
  const {
    tag: Tag,
    children,
  } = props;

  // --------------------- ===
  //  RENDER
  // ---------------------
  return (
    <Tag className={styles.subtitle}>
      {children}
    </Tag>
  );
};

Subtitle.defaultProps = {
  tag: 'h2',
};

Subtitle.propTypes = {
  tag: PropTypes.oneOf([
    'h2',
    'h3',
    'p',
  ]),
  children: PropTypes.string.isRequired,
};

export default Subtitle;