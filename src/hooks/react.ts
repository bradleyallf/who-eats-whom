import { EffectCallback, useEffect, useRef } from 'react'

// https://stackoverflow.com/a/56767883/3550318
export const useMountEffect = (callback: EffectCallback) => {
  useEffect(callback, [])
}

// https://stackoverflow.com/a/53446665/3550318
export const usePrevious = <T>(val: T, isValInit = false): T | null => {
  const ref = useRef<T | null>(isValInit ? val : null)
  useEffect(() => {
    ref.current = val
  })
  return ref.current
}
