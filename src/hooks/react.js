import { useEffect, useRef } from 'react';

// https://stackoverflow.com/a/56767883/3550318
export const useMountEffect = (fun) => useEffect(fun, []);

// https://stackoverflow.com/a/53446665/3550318
export const usePrevious = (val, initialVal = null) => {
  const ref = useRef(initialVal);
  useEffect(() => {
    ref.current = val;
  });
  return ref.current;
};
