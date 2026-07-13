import { describe, expect, it } from 'vitest'

import { titleCase } from './Dropdown'

describe('titleCase', () => {
  it('formats species names while preserving minor words', () => {
    expect(titleCase('red fox and osprey')).toBe('Red Fox and Osprey')
  })
})
