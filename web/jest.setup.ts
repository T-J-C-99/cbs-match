import '@testing-library/jest-dom'
import { TextDecoder, TextEncoder } from 'util'

if (!(global as any).TextEncoder) {
  ;(global as any).TextEncoder = TextEncoder
}
if (!(global as any).TextDecoder) {
  ;(global as any).TextDecoder = TextDecoder
}

// Mock fetch for API calls
global.fetch = jest.fn()

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
Object.defineProperty(global, 'localStorage', { value: localStorageMock })

// Reset mocks between tests
beforeEach(() => {
  jest.clearAllMocks()
  ;(global.fetch as jest.Mock).mockReset()
})