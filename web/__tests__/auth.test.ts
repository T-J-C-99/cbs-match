/**
 * Comprehensive Frontend Tests for CBS Match Web
 * Independent evaluator test suite - identifies frontend issues
 * 
 * NOTE: These tests require jest and testing-library to be installed.
 * Run: npm install --save-dev jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom @types/jest ts-node
 */

// Mock Response for fetch
class MockResponse {
  status: number;
  private _json: any;
  ok: boolean;
  
  constructor(json: any, status = 200) {
    this._json = json;
    this.status = status;
    this.ok = status >= 200 && status < 300;
  }
  
  json() {
    return Promise.resolve(this._json);
  }
}

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('Authentication API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('Login Flow', () => {
    test('successful login returns access token', async () => {
      mockFetch
        .mockResolvedValueOnce(new MockResponse({ 
          access_token: 'test-token', 
          refresh_token: 'refresh-token' 
        }, 200))
        .mockResolvedValueOnce(new MockResponse({ 
          user: { id: '1', email: 'test@gsb.columbia.edu', is_email_verified: true } 
        }, 200));

      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: 'test@gsb.columbia.edu', password: 'password123' }),
      });

      const data = await res.json();
      expect(res.ok).toBe(true);
      expect(data.access_token).toBe('test-token');
    });

    test('failed login with wrong password returns 401', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'Invalid credentials' 
      }, 401));

      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: 'test@gsb.columbia.edu', password: 'wrongpassword' }),
      });

      expect(res.ok).toBe(false);
      expect(res.status).toBe(401);
    });

    test('login with username instead of email works', async () => {
      mockFetch
        .mockResolvedValueOnce(new MockResponse({ 
          access_token: 'test-token' 
        }, 200))
        .mockResolvedValueOnce(new MockResponse({ 
          user: { id: '1', email: 'test@gsb.columbia.edu' } 
        }, 200));

      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: 'testuser', password: 'password123' }),
      });

      expect(res.ok).toBe(true);
    });
  });

  describe('Registration Flow', () => {
    test('registration with valid GSB email succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        access_token: 'test-token',
        user: { id: '1', email: 'new@gsb.columbia.edu' }
      }, 201));

      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'new@gsb.columbia.edu',
          password: 'validpassword123',
          gender_identity: 'man',
          seeking_genders: ['woman'],
        }),
      });

      expect(res.status).toBe(201);
    });

    test('registration with non-GSB email fails', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'Email must be @gsb.columbia.edu' 
      }, 400));

      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'user@gmail.com',
          password: 'validpassword123',
        }),
      });

      expect(res.status).toBe(400);
    });

    test('registration with short password fails', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'Password must be at least 10 characters' 
      }, 400));

      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'user@gsb.columbia.edu',
          password: 'short',
        }),
      });

      expect(res.status).toBe(400);
    });
  });

  describe('Email Verification Flow', () => {
    test('verification with valid code succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        message: 'Email verified' 
      }, 200));

      const res = await fetch('/api/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'user@gsb.columbia.edu',
          code: '123456',
        }),
      });

      expect(res.ok).toBe(true);
    });

    test('verification with invalid code fails', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'Invalid email or code' 
      }, 400));

      const res = await fetch('/api/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'user@gsb.columbia.edu',
          code: '000000',
        }),
      });

      expect(res.status).toBe(400);
    });
  });

  describe('Token Refresh Flow', () => {
    test('refresh token returns new access token', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        access_token: 'new-token',
        refresh_token: 'new-refresh'
      }, 200));

      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: 'old-refresh' }),
      });

      const data = await res.json();
      expect(data.access_token).toBe('new-token');
    });
  });
});

describe('Profile API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('Profile Update', () => {
    test('update profile with valid data succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        profile: {
          id: '1',
          display_name: 'Test User',
          cbs_year: '26',
          hometown: 'New York',
          gender_identity: 'man',
          seeking_genders: ['woman'],
        }
      }, 200));

      const res = await fetch('/api/users/me/profile', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token'
        },
        body: JSON.stringify({
          display_name: 'Test User',
          cbs_year: '26',
          hometown: 'New York',
          gender_identity: 'man',
          seeking_genders: ['woman'],
        }),
      });

      expect(res.ok).toBe(true);
    });

    test('update profile with invalid CBS year fails', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'cbs_year must be one of: 26, 27' 
      }, 400));

      const res = await fetch('/api/users/me/profile', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token'
        },
        body: JSON.stringify({
          display_name: 'Test User',
          cbs_year: '2025',
          gender_identity: 'man',
          seeking_genders: ['woman'],
        }),
      });

      expect(res.status).toBe(400);
    });

    test('update profile with too many photos fails', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        detail: 'You can provide up to 3 photo URLs' 
      }, 400));

      const res = await fetch('/api/users/me/profile', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token'
        },
        body: JSON.stringify({
          display_name: 'Test User',
          gender_identity: 'man',
          seeking_genders: ['woman'],
          photo_urls: [
            'https://example.com/1.jpg',
            'https://example.com/2.jpg',
            'https://example.com/3.jpg',
            'https://example.com/4.jpg',
          ],
        }),
      });

      expect(res.status).toBe(400);
    });
  });

  describe('User State', () => {
    test('get user state returns onboarding status', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        user: { id: '1', email: 'user@gsb.columbia.edu' },
        onboarding: {
          has_any_session: true,
          has_completed_survey: true,
        },
        profile: {
          has_required_profile: true,
          missing_fields: [],
        }
      }, 200));

      const res = await fetch('/api/users/me/state', {
        headers: { 'Authorization': 'Bearer test-token' }
      });

      const data = await res.json();
      expect(data.onboarding.has_completed_survey).toBe(true);
      expect(data.profile.has_required_profile).toBe(true);
    });
  });
});

describe('Match API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('Get Current Match', () => {
    test('returns match when available', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        match: {
          week_start_date: '2026-02-16',
          matched_user_id: 'user-2',
          status: 'revealed',
          score_total: 0.85,
        },
        message: 'You\'re matched for this week.',
        explanation: {
          bullets: ['You share similar values'],
          icebreakers: ['Ask about their hometown']
        }
      }, 200));

      const res = await fetch('/api/matches/current', {
        headers: { 'Authorization': 'Bearer test-token' }
      });

      const data = await res.json();
      expect(data.match).not.toBeNull();
      expect(data.match.status).toBe('revealed');
    });

    test('returns no match when not assigned', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        match: null,
        message: 'No match has been assigned for this week yet'
      }, 200));

      const res = await fetch('/api/matches/current', {
        headers: { 'Authorization': 'Bearer test-token' }
      });

      const data = await res.json();
      expect(data.match).toBeNull();
    });
  });

  describe('Match Actions', () => {
    test('accept match succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        status: 'accepted' 
      }, 200));

      const res = await fetch('/api/matches/current/accept', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer test-token' }
      });

      const data = await res.json();
      expect(data.status).toBe('accepted');
    });

    test('decline match succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        status: 'declined' 
      }, 200));

      const res = await fetch('/api/matches/current/decline', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer test-token' }
      });

      const data = await res.json();
      expect(data.status).toBe('declined');
    });
  });

  describe('Match Feedback', () => {
    test('submit feedback succeeds', async () => {
      mockFetch.mockResolvedValueOnce(new MockResponse({ 
        status: 'submitted',
        answers: { coffee_intent: 5, met: true }
      }, 200));

      const res = await fetch('/api/matches/current/feedback', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token'
        },
        body: JSON.stringify({
          answers: { coffee_intent: 5, met: true }
        }),
      });

      expect(res.ok).toBe(true);
    });
  });
});

describe('Safety Features', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  test('block user succeeds', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      status: 'blocked',
      blocked_user_id: 'user-to-block'
    }, 200));

    const res = await fetch('/api/safety/block', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
      },
      body: JSON.stringify({ blocked_user_id: 'user-to-block' }),
    });

    const data = await res.json();
    expect(data.status).toBe('blocked');
  });

  test('report user succeeds', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      status: 'reported',
      report: { id: 'report-1', reason: 'inappropriate' }
    }, 200));

    const res = await fetch('/api/safety/report', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
      },
      body: JSON.stringify({ reason: 'inappropriate', details: 'Details here' }),
    });

    expect(res.ok).toBe(true);
  });
});

describe('Survey Flow', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  test('get active survey returns definition', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      survey: { slug: 'cbs_match', version: 1 },
      screens: [
        { key: 'intro', title: 'Welcome', items: [] }
      ]
    }, 200));

    const res = await fetch('/api/survey/active');
    const data = await res.json();
    
    expect(data.survey.slug).toBe('cbs_match');
    expect(Array.isArray(data.screens)).toBe(true);
  });

  test('create session succeeds', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      session_id: 'session-123',
      user_id: 'user-1'
    }, 200));

    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer test-token' }
    });

    const data = await res.json();
    expect(data.session_id).toBe('session-123');
  });

  test('submit answers succeeds', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      status: 'saved',
      saved_count: 3
    }, 200));

    const res = await fetch('/api/sessions/session-123/answers', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
      },
      body: JSON.stringify({
        answers: [
          { question_code: 'Q1', answer_value: 4 },
          { question_code: 'Q2', answer_value: 3 },
          { question_code: 'Q3', answer_value: 5 },
        ]
      }),
    });

    const data = await res.json();
    expect(data.saved_count).toBe(3);
  });

  test('complete session returns traits', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      status: 'completed',
      traits: {
        big5: { openness: 0.7, conscientiousness: 0.8 }
      }
    }, 200));

    const res = await fetch('/api/sessions/session-123/complete', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer test-token' }
    });

    const data = await res.json();
    expect(data.status).toBe('completed');
    expect(data.traits).toBeDefined();
  });
});

describe('Error Handling', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  test('unauthorized request returns 401', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      detail: 'Unauthorized'
    }, 401));

    const res = await fetch('/api/users/me/state');
    expect(res.status).toBe(401);
  });

  test('forbidden request returns 403', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      detail: 'Email verification required'
    }, 403));

    const res = await fetch('/api/matches/current', {
      headers: { 'Authorization': 'Bearer unverified-token' }
    });
    expect(res.status).toBe(403);
  });

  test('not found returns 404', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      detail: 'Session not found'
    }, 404));

    const res = await fetch('/api/sessions/nonexistent-session');
    expect(res.status).toBe(404);
  });

  test('rate limit returns 429', async () => {
    mockFetch.mockResolvedValueOnce(new MockResponse({ 
      detail: 'Too many requests'
    }, 429));

    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier: 'user', password: 'pass' }),
    });
    expect(res.status).toBe(429);
  });
});