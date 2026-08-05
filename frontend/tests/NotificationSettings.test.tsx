import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NotificationSettings } from '../src/components/NotificationSettings'
import React from 'react'

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}))

// Mock authService
vi.mock('../src/api', () => ({
  authService: {
    isAuthenticated: () => true,
    getMe: vi.fn().mockResolvedValue({ id: 1, email: 'test@example.com' }),
  },
}))

describe('NotificationSettings Screen', () => {
  beforeEach(() => {
    // Mock the Notification global object
    vi.stubGlobal('Notification', {
      permission: 'granted',
    })

    // Mock matchMedia for jsdom
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    
    // Mock navigator.serviceWorker
    vi.stubGlobal('navigator', {
      ...navigator,
      serviceWorker: {
        ready: Promise.resolve({
          pushManager: {
            getSubscription: vi.fn().mockResolvedValue(null),
          },
        }),
      },
    })
  })

  it('renders four notification type items with luteal phase first', async () => {
    render(<NotificationSettings />)
    
    // Wait for the status loading to resolve
    const heading = await screen.findByText('📬 Reminders you will receive:')
    expect(heading).toBeDefined()

    // Find all list items inside the notif-features-list class
    const listItems = document.querySelectorAll('.notif-features-list li')
    expect(listItems).toHaveLength(4)

    // The first item should be the Luteal Phase reminder
    const firstItem = listItems[0]
    expect(firstItem.textContent).toContain('8 days before your period — luteal phase heads-up')
    
    // Check that descriptions are in the correct order
    expect(listItems[1].textContent).toContain('3 days before your period')
    expect(listItems[2].textContent).toContain('1 day before your period')
    expect(listItems[3].textContent).toContain('1 day before your fertile window')
  })

  it('displays the plain language luteal phase description text', async () => {
    render(<NotificationSettings />)
    
    // Wait for loading to finish
    await screen.findByText('📬 Reminders you will receive:')

    // Verify luteal phase description is present
    const descText = screen.getByText(/The week before your period can bring mood changes, fatigue, and physical symptoms/)
    expect(descText).toBeDefined()
  })
})
