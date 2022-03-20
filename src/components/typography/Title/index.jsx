import React from 'react';
import PropTypes from 'prop-types';
import styles from './index.scss';

const Title = (props) => {
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
    <Tag className={styles.title}>
      { children }
    </Tag>
  );
};

Title.defaultProps = {
  tag: 'h1',
};

Title.propTypes = {
  tag: PropTypes.oneOf([
    'h1',
    'h2',
    'p',
  ]),
  children: PropTypes.string.isRequired,
};

export default Title;
