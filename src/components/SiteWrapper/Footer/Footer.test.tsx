import { describe, expect, it, vi } from 'vitest'

import { getCurrentYear } from './Footer'

describe('Footer', () => {
  it('uses the current year', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2031-06-15'))

    expect(getCurrentYear()).toBe(2031)

    vi.useRealTimers()
  })
})
