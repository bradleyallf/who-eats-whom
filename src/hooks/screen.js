import { useState } from 'react';
import { useMountEffect } from '$hooks/react';

export const useScreenSize = () => {
  const [screenSize, setScreenSize] = useState({
    width: 100,
    height: 100,
  });

  // --------------------- ===
  //  SCREEN SIZE LISTENER
  // ---------------------
  useMountEffect(() => {
    const handleResize = () => {
      const {
        innerWidth,
        innerHeight,
      } = window;

      setScreenSize({ width: innerWidth, height: innerHeight });
    };

    // run on mount
    handleResize();

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  });

  return screenSize;
};
