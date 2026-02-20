# CBS Match - Comprehensive Documentation

## Executive Summary

**CBS Match** is a weekly matching application designed for Columbia Business School (CBS) MBA students. It uses personality science and preference compatibility to create meaningful one-to-one pairings each week. Think of it as "Hinge meets behavioral science" for a closed community of business school students.

---

## Table of Contents

1. [What is CBS Match?](#what-is-cbs-match)
2. [Architecture Overview](#architecture-overview)
3. [How It Works - User Journey](#how-it-works---user-journey)
4. [The Matching Algorithm](#the-matching-algorithm)
5. [Feature Deep Dive](#feature-deep-dive)
6. [Database Schema](#database-schema)
7. [API Reference](#api-reference)
8. [Key Decisions & Rationale](#key-decisions--rationale)
9. [Known Issues & Considerations](#known-issues--considerations)
10. [Configuration](#configuration)
11. [Development & Deployment](#development--deployment)

---

## What is CBS Match?

CBS Match is a **weekly matching platform** that pairs CBS MBA students based on:
- **Big Five personality traits** (openness, conscientiousness, extraversion, agreeableness, neuroticism)
- **Conflict resolution styles** (repair willingness, escalation, cooldown needs, grudge tendency)
- **Life architecture preferences** (marriage, kids, career intensity, NYC commitment, faith, social lifestyle)
- **Gender preferences** (who you're seeking)

### The "Dean of Dating" Brand

The application uses a playful persona called the **"Dean of Dating"** who:
- Explains match compatibility in personalized, human-readable language
- Provides "pros" and "cons" for each match
- Offers icebreakers and conversation starters
- Generates profile insights for users

### Target Audience
- CBS MBA students (Class of 2026, 2027)
- J-Term and EMBA students
- Must have a `@gsb.columbia.edu` email address

---

## Architecture Overview

CBS Match is a **three-tier application**:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                  │
├─────────────────────┬───────────────────────────────────────────┤
│   Web (Next.js)     │         Mobile (React Native/Expo)        │
│   Port 3000         │         iOS Simulator / Android Emulator  │
└─────────┬───────────┴───────────────────┬───────────────────────┘
          │                               │
          │         HTTP/REST             │
          ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API (FastAPI + Python)                        │
│                         Port 8000                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Auth       │  │   Survey     │  │   Matching Engine    │  │
│  │   Module     │  │   Module     │  │   (Algorithm)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │
          │   SQLAlchemy + psycopg2
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│                       Port 5432                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Web Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS |
| **Mobile App** | React Native, Expo, TypeScript, React Query |
| **Backend API** | FastAPI, Python 3.11+, SQLAlchemy |
| **Database** | PostgreSQL (SQLite for local dev) |
| **Auth** | JWT (access + refresh tokens), bcrypt password hashing |
| **File Storage** | Local filesystem (`/uploads` directory) |
| **Deployment** | Docker Compose |

### Project Structure

```
cbs-match/
├── api/                          # Python FastAPI backend
│   ├── app/
│   │   ├── main.py               # All API endpoints (single file)
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   ├── repo.py               # Database operations (auth, users, blocks)
│   │   ├── traits.py             # Personality trait computation
│   │   ├── config.py             # Environment configuration
│   │   ├── database.py           # DB connection setup
│   │   ├── schemas.py            # Pydantic models
│   │   ├── survey_loader.py      # Survey JSON loading
│   │   ├── survey_admin_repo.py  # Survey versioning admin
│   │   ├── auth/
│   │   │   ├── deps.py           # Auth dependencies (get_current_user)
│   │   │   └── security.py       # Password hashing, JWT creation
│   │   └── services/
│   │       ├── matching.py       # Core matching algorithm
│   │       ├── explanations.py   # Match explanation generation
│   │       ├── copy_templates.py # "Dean of Dating" copy machine
│   │       ├── calibration.py    # Weekly calibration reports
│   │       ├── state_machine.py  # Match status transitions
│   │       ├── events.py         # Event logging
│   │       ├── rules.py          # Business rules
│   │       ├── rate_limit.py     # Rate limiting
│   │       ├── seeding.py        # Dummy data generation
│   │       └── survey_validation.py
│   ├── migrations/               # SQL migration files (001-016)
│   ├── tests/                    # pytest test files
│   └── uploads/                  # User photo uploads
│
├── web/                          # Next.js web frontend
│   ├── app/                      # App Router pages
│   │   ├── page.tsx              # Landing page
│   │   ├── login/                # Login page
│   │   ├── register/             # Registration page
│   │   ├── survey/               # Questionnaire flow
│   │   ├── match/                # Weekly match display
│   │   ├── past/                 # Match history
│   │   ├── profile/              # User profile editing
│   │   ├── settings/             # Account settings
│   │   ├── admin/                # Admin dashboard
│   │   └── ...
│   ├── components/               # Shared React components
│   └── lib/                      # Server-side utilities
│
├── mobile/                       # React Native mobile app
│   ├── src/
│   │   ├── screens/              # Screen components
│   │   │   ├── MatchScreen.tsx   # Match display
│   │   │   ├── ProfileScreen.tsx # Profile editing
│   │   │   ├── LoginScreen.tsx   # Login
│   │   │   └── ...
│   │   ├── api/                  # API client
│   │   ├── hooks/                # Custom hooks
│   │   └── utils/                # Utilities
│   └── App.tsx                   # Entry point
│
├── packages/shared/              # Shared TypeScript logic (questionnaire)
├── scripts/                      # Dev scripts
├── questions.json                # Survey definition
├── docker-compose.yml            # Docker orchestration
├── Makefile                      # Common commands
└── README.md                     # Quick start guide
```

---

## How It Works - User Journey

### 1. Registration & Verification

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Register   │───▶│   Verify     │───▶│    Login     │
│   (email +   │    │   Email      │    │   (email +   │
│   password)  │    │   (6-digit   │    │   password)  │
└──────────────┘    │    code)     │    └──────────────┘
                    └──────────────┘
```

**Registration Requirements:**
- Must use `@gsb.columbia.edu` email
- Password minimum 10 characters
- Optional: username (3-24 chars, lowercase alphanumeric + underscore)
- Optional: profile photo upload (up to 3 photos, max 8MB each)

**Email Verification:**
- 6-digit code sent to email
- 24-hour expiration
- 8 attempt limit before code invalidation
- **DEV_MODE bypass:** Code defaults to "123456"

**Current Behavior (Temporary):**
> Email verification is **bypassed** for all users. New accounts are automatically marked as verified. This is a product decision to reduce friction during the pilot phase.

### 2. Onboarding Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Complete   │───▶│   Complete   │───▶│   Complete   │───▶│   Eligible   │
│   Profile    │    │   Survey     │    │   Traits     │    │   for Match  │
│   (name,     │    │   (~100      │    │   (computed  │    │              │
│   year, etc) │    │   questions) │    │   server-side│    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

**Profile Requirements:**
- `display_name` (required)
- `cbs_year` (required: "26" or "27")
- `hometown` (required)
- `photo_urls` (at least 1 photo required)
- `gender_identity` (required: man, woman, nonbinary, other)
- `seeking_genders` (required: at least one selection)

### 3. The Survey (Questionnaire)

The survey is defined in `questions.json` and contains ~100 questions across 15 screens:

| Screen | Topics | Question Codes |
|--------|--------|----------------|
| Warm-up | Weekend preference | `WARM_*` |
| CBS Life | Cluster, post-MBA industry, recruiting stress | `CBS_*` |
| Big Five O | Openness (6 questions) | `BF_O_*` |
| Big Five C | Conscientiousness (6 questions) | `BF_C_*` |
| Big Five E | Extraversion (6 questions) | `BF_E_*` |
| NYC Life | Neighborhood | `NYC_*` |
| Big Five A | Agreeableness (6 questions) | `BF_A_*` |
| Big Five N | Neuroticism (6 questions) | `BF_N_*` |
| Conflict Repair | 15 conflict style questions | `CR_*` |
| Emotional Needs | Attachment, reassurance needs | `AN_*` |
| Life Architecture - Kids | Kids preferences, timeline | `LA_KIDS_*` |
| Life Architecture - Other | Marriage, NYC, career, faith, lifestyle | `LA_*`, `MOD_*` |
| Money | Financial attitudes | `MS_*` |
| Cadence & Home | Day-to-day rhythm | `CH_*` |
| Fun | Playful personality questions | `FUN_*` |

**Question Types:**
- `likert_1_5` - 5-point agreement scale
- `single_select` - Multiple choice
- `slider` - 0-100 slider (normalized to 0.0-1.0)

**Trait Computation (server-side):**
When a survey is completed, `traits.py` computes:
- Big Five scores (0.0-1.0 normalized)
- Conflict repair profile
- Life constraints (kids, etc.)
- Life preferences
- Modifier scores (importance + flexibility per domain)

### 4. Weekly Matching

**Trigger:** Admin calls `POST /admin/matches/run-weekly`

**Process:**
1. Fetch all eligible users (completed survey, not paused)
2. Build candidate pairs with compatibility scores
3. Apply hard gates (gender preference, recent matches, blocked pairs)
4. Apply soft filters (kids compatibility)
5. Run greedy one-to-one matching
6. Persist assignments

**Match Lifecycle:**
```
proposed → revealed → accepted/declined/expired
                ↓
           (user views match)
```

**States:**
- `proposed` - Initial state, user hasn't seen it yet
- `revealed` - User has viewed their match
- `accepted` - User accepted the match
- `declined` - User declined the match
- `expired` - 72 hours passed without action
- `no_match` - No compatible pairing found
- `blocked` - User blocked their match (hides profile)

### 5. Viewing Your Match

When a user views `/matches/current`:
1. Status transitions from `proposed` → `revealed` (if applicable)
2. Matched user's profile is fetched (photos, display name, contact)
3. "Dean of Dating" explanation is generated
4. Feedback eligibility is computed

**Match Display Includes:**
- Matched user's profile (photos, name, CBS year, hometown)
- Contact methods (email, phone, Instagram)
- Compatibility explanation (overall, pros, cons)
- Icebreakers
- Feedback form

---

## The Matching Algorithm

### Location: `api/app/services/matching.py`

### Step 1: Fetch Eligible Users

```python
def fetch_eligible_users(db, survey_slug, survey_version):
    # Users with:
    # - Completed survey
    # - Computed traits
    # - Gender identity and seeking preferences set
    # - Not paused (user_preferences.pause_matches = FALSE)
```

### Step 2: Build Candidate Pairs

For each pair of eligible users (A, B):

#### Hard Gates (must pass):

1. **Gender Preference Compatibility**
   ```python
   def _gender_preference_compatible(u, v):
       # A's gender must be in B's seeking_genders
       # B's gender must be in A's seeking_genders
       # Both must have identity + preferences defined
   ```

2. **Recent Pair Exclusion**
   ```python
   # Pairs matched in the last LOOKBACK_WEEKS (default: 6) are excluded
   recent_pairs = fetch_recent_pairs(db, week_start_date, lookback_weeks)
   ```

3. **Block List Exclusion**
   ```python
   # Pairs where either user blocked the other are excluded
   blocked_pairs = get_block_pairs_for_matching(db)
   ```

#### Soft Filters:

1. **Kids Compatibility Check**
   ```python
   def _kids_compatible(k1, k2):
       # Hard no ("no", "probably_not") vs hard yes ("yes", "probably")
       # is a mismatch, but doesn't hard-exclude
       # It sets score to 0.0 instead
   ```

### Step 3: Compute Compatibility Score

```python
def compute_compatibility(u_traits, v_traits, cfg):
    # 1. Big Five Similarity (70% weight default)
    big5_similarity = vector_similarity(u_big5_vec, v_big5_vec)
    
    # 2. Conflict Style Similarity (30% weight default)
    conflict_similarity = vector_similarity(u_cr_vec, v_cr_vec)
    
    # 3. Base Score
    base_score = big5_weight * big5_similarity + conflict_weight * conflict_similarity
    
    # 4. Life Architecture Modifier Penalty
    modifier_multiplier, penalties = _modifier_penalty(u_traits, v_traits, cfg)
    
    # 5. Total Score
    total = 0.0 if not kids_ok else base_score * modifier_multiplier
    
    return {
        "score_total": total,
        "score_breakdown": {
            "big5_similarity": ...,
            "conflict_similarity": ...,
            "kids_hard_check": bool,
            "modifier_multiplier": ...,
            "modifier_penalties": {...}
        }
    }
```

**Vector Similarity:**
```python
def _vector_similarity(a, b):
    # Euclidean distance normalized
    sq = sum((x - y) ** 2 for x, y in zip(a, b))
    max_dist = len(a) ** 0.5
    return max(0.0, 1.0 - (sq ** 0.5) / max_dist)
```

**Life Architecture Penalty:**
For each domain (marriage, kids, NYC, career, faith, social):
- Calculate preference mismatch (absolute difference)
- If mismatch > threshold (0.45), apply penalty
- Penalty = `1.0 - min(cap, scale * avg_importance * (1 - avg_flexibility))`

### Step 4: Greedy One-to-One Matching

```python
def greedy_one_to_one_match(pairs, min_score):
    matched = set()
    assignments = []
    
    # Sort by score descending
    for pair in sorted(pairs, key=lambda p: -p.score_total):
        if pair.score_total < min_score:  # Default: 0.55
            continue
        if pair.user_id in matched or pair.matched_user_id in matched:
            continue  # Skip if either already matched
        
        matched.add(pair.user_id)
        matched.add(pair.matched_user_id)
        assignments.append(pair)
    
    return assignments
```

**Result:** Each user gets at most one match per week. Users below `MIN_SCORE` or with no compatible candidates get `no_match` status.

### Step 5: Persist Assignments

```python
def create_weekly_assignments(db, week_start_date, expires_at, assignments, unmatched_user_ids):
    # Create bidirectional rows:
    # - User A → matched with B
    # - User B → matched with A
    # Each row has: score_total, score_breakdown JSON, status, expires_at
    
    # Create no_match rows for unmatched users
```

---

## Feature Deep Dive

### 1. Dean of Dating Explanations

**Location:** `api/app/services/copy_templates.py`

The "Dean of Dating" generates personalized match explanations using a template system:

```python
OVERALL_TEMPLATES = {
    "high": [  # score >= 0.72
        "The Dean of Dating has crunched the numbers, and this is a standout pairing...",
    ],
    "medium": [  # 0.58 <= score < 0.72
        "The Dean of Dating has identified a worthwhile connection here...",
    ],
    "low": [  # score < 0.58
        "The Dean of Dating sees a challenging but interesting pairing...",
    ],
}
```

**Generated Content:**
- `overall` - Main assessment paragraph
- `pros` - 2 strengths
- `cons` - 2 considerations
- `icebreakers` - Conversation starters

**Privacy Consideration:**
Sensitive terms (kids, faith, unconventional, structure) are filtered from explanations unless the user consented to sensitive explanations.

### 2. Match Feedback System

Users can submit feedback on matches:

**Fields:**
- `coffee_intent` (1-5) - How excited are you to meet?
- `met` (boolean) - Did you message them? (only available after Wednesday)
- `chemistry` (1-5) - If met, how was chemistry?
- `respect` (1-5) - If met, how was respect level?

**Constraints:**
- One submission per match per user
- `met`, `chemistry`, `respect` only available after 3 days (Wednesday)
- Feedback is **not shared** with the matched user

### 3. Safety Features

**Block System:**
- Users can block any other user by ID, email, or username
- Blocking immediately hides current week's match if it's that user
- Blocked pairs are excluded from future matching

**Report System:**
- Users can report their current match with reason + details
- Reports are stored for admin review

**Account Deletion:**
- Soft delete with anonymization
- Email replaced with `deleted+{uuid}@deleted.local`
- Match history updated to remove references
- User's match assignments removed

### 4. Chat System

**Location:** Migrations `011_chat_threads_messages.sql`

**Structure:**
- `chat_thread` - Thread between two users for a week
- `chat_message` - Individual messages

**Current State:** Basic thread/message storage exists, but in-app chat is not fully implemented in the UI.

### 5. User Preferences

**Pause Matches:**
```python
# Users can opt out of matching
PUT /users/me/preferences
{ "pause_matches": true }
```

Paused users are excluded from `fetch_eligible_users`.

### 6. Admin Features

**Admin Token:** All admin endpoints require `X-Admin-Token` header.

**Endpoints:**
- `POST /admin/matches/run-weekly` - Run matching for current week
- `GET /admin/matches/week/{date}` - View week summary
- `GET /admin/calibration/current-week` - Calibration report
- `POST /admin/seed` - Generate dummy users
- `GET /admin/reports/week/{date}` - View reports for a week
- `GET /admin/blocks/stats` - Block statistics

**Calibration Report:**
```json
{
  "week_start_date": "2026-02-17",
  "eligible_users": 120,
  "candidate_pair_count": 4560,
  "pair_score_distribution": {
    "percentiles": { "p10": 0.45, "p25": 0.55, "p50": 0.65, "p75": 0.75, "p90": 0.82 }
  },
  "assignment_counts": {
    "total_assignments": 120,
    "no_match_count": 8,
    "no_match_rate": 0.067
  }
}
```

### 7. Survey Versioning

**Tables:**
- `survey_definition` - Stores survey versions (draft and active)
- Supports rollback to previous published versions

**Flow:**
1. Admin creates draft from active
2. Admin modifies draft
3. Admin validates draft
4. Admin publishes draft (becomes new active)

---

## Database Schema

### Core Tables

#### `user_account`
```sql
id UUID PRIMARY KEY
email TEXT UNIQUE
username TEXT UNIQUE
password_hash TEXT
is_email_verified BOOLEAN
display_name TEXT
cbs_year TEXT  -- '26' or '27'
hometown TEXT
phone_number TEXT
instagram_handle TEXT
photo_urls JSONB  -- Array of URLs
gender_identity TEXT  -- man, woman, nonbinary, other
seeking_genders JSONB  -- Array
created_at TIMESTAMPTZ
last_login_at TIMESTAMPTZ
disabled_at TIMESTAMPTZ  -- Soft delete
```

#### `survey_session`
```sql
id UUID PRIMARY KEY
user_id TEXT
survey_slug TEXT
survey_version INT
status TEXT  -- in_progress, completed
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ
```

#### `survey_answer`
```sql
id UUID PRIMARY KEY
session_id UUID REFERENCES survey_session
question_code TEXT
answer_value JSONB
answered_at TIMESTAMPTZ
UNIQUE(session_id, question_code)
```

#### `user_traits`
```sql
id UUID PRIMARY KEY
user_id TEXT
survey_slug TEXT
survey_version INT
traits JSONB  -- Computed traits
computed_at TIMESTAMPTZ
UNIQUE(user_id, survey_slug, survey_version)
```

#### `weekly_match_assignment`
```sql
id UUID PRIMARY KEY
week_start_date DATE
user_id UUID
matched_user_id UUID  -- NULL for no_match
score_total NUMERIC
score_breakdown JSONB
status TEXT  -- proposed, revealed, accepted, declined, expired, no_match, blocked
created_at TIMESTAMPTZ
expires_at TIMESTAMPTZ
UNIQUE(week_start_date, user_id)
```

#### `match_event`
```sql
id UUID PRIMARY KEY
user_id UUID
week_start_date DATE
event_type TEXT  -- match_viewed, accept, decline, blocked_current_match, etc.
payload JSONB
created_at TIMESTAMPTZ
```

#### `match_feedback`
```sql
id UUID PRIMARY KEY
week_start_date DATE
user_id UUID
matched_user_id UUID
answers JSONB  -- coffee_intent, met, chemistry, respect
submitted_at TIMESTAMPTZ
UNIQUE(week_start_date, user_id)
```

#### `user_block`
```sql
id UUID PRIMARY KEY
user_id UUID
blocked_user_id UUID
created_at TIMESTAMPTZ
UNIQUE(user_id, blocked_user_id)
```

#### `match_report`
```sql
id UUID PRIMARY KEY
week_start_date DATE
user_id UUID
matched_user_id UUID
reason TEXT
details TEXT
created_at TIMESTAMPTZ
```

#### `chat_thread` & `chat_message`
```sql
-- chat_thread
id UUID PRIMARY KEY
week_start_date DATE
participant_a_id UUID
participant_b_id UUID
created_at TIMESTAMPTZ

-- chat_message
id UUID PRIMARY KEY
thread_id UUID REFERENCES chat_thread
sender_user_id UUID
body TEXT
created_at TIMESTAMPTZ
```

#### `user_preferences`
```sql
user_id UUID PRIMARY KEY
pause_matches BOOLEAN DEFAULT FALSE
updated_at TIMESTAMPTZ
```

#### `user_profile`
```sql
user_id UUID PRIMARY KEY
display_name TEXT
cbs_year TEXT
hometown TEXT
phone_number TEXT
instagram_handle TEXT
photo_urls JSONB
gender_identity TEXT
seeking_genders JSONB
updated_at TIMESTAMPTZ
```

### Auth Tables

#### `email_verification_token`
```sql
id UUID PRIMARY KEY
user_id UUID REFERENCES user_account
token TEXT UNIQUE
code_hash TEXT  -- Hashed 6-digit code
expires_at TIMESTAMPTZ
used_at TIMESTAMPTZ
failed_attempts INT DEFAULT 0
created_at TIMESTAMPTZ
```

#### `refresh_token`
```sql
id UUID PRIMARY KEY
user_id UUID REFERENCES user_account
token_hash TEXT UNIQUE
expires_at TIMESTAMPTZ
revoked_at TIMESTAMPTZ
created_at TIMESTAMPTZ
```

---

## API Reference

### Authentication Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/verify-email` | Verify email with 6-digit code |
| `POST` | `/auth/verify-email/resend` | Resend verification code |
| `POST` | `/auth/login` | Login (email/username + password) |
| `POST` | `/auth/refresh` | Refresh access token |
| `POST` | `/auth/logout` | Revoke refresh token |
| `GET` | `/auth/me` | Get current user info |
| `GET` | `/auth/username-availability` | Check if username available |

### User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/me/state` | Get onboarding state |
| `GET` | `/users/me/profile` | Get user profile |
| `PUT` | `/users/me/profile` | Update profile |
| `GET` | `/users/me/insights` | Get Dean of Dating profile insights |
| `DELETE` | `/users/me/account` | Delete account |
| `PUT` | `/users/me/username` | Update username |
| `GET` | `/users/me/preferences` | Get preferences |
| `PUT` | `/users/me/preferences` | Update preferences |
| `GET` | `/users/me/matches/history` | Get match history |
| `POST` | `/users/me/support/feedback` | Submit support feedback |
| `POST` | `/users/me/profile/photos` | Upload photos |

### Survey Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/survey/active` | Get active survey definition |
| `POST` | `/sessions` | Create new survey session |
| `GET` | `/sessions/{id}` | Get session with answers |
| `POST` | `/sessions/{id}/answers` | Save answers |
| `POST` | `/sessions/{id}/complete` | Complete session & compute traits |

### Match Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/matches/current` | Get current week's match |
| `GET` | `/matches/history` | Get historical matches |
| `POST` | `/matches/current/accept` | Accept current match |
| `POST` | `/matches/current/decline` | Decline current match |
| `POST` | `/matches/current/feedback` | Submit feedback |

### Safety Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/safety/block` | Block a user |
| `POST` | `/safety/unblock` | Unblock a user |
| `GET` | `/safety/blocks` | List blocked users |
| `POST` | `/safety/report` | Report current match |

### Chat Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/chat/threads` | List chat threads |
| `GET` | `/chat/threads/{id}` | Get thread with messages |
| `POST` | `/chat/threads/{id}/messages` | Send message |

### Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/matches/run-weekly` | Run weekly matching |
| `GET` | `/admin/matches/week/{date}` | Get week summary |
| `GET` | `/admin/calibration/current-week` | Get calibration report |
| `POST` | `/admin/seed` | Seed dummy users |
| `POST` | `/admin/seed-contact-info` | Add contact info to users |
| `GET` | `/admin/reports/week/{date}` | Get reports for week |
| `GET` | `/admin/blocks/stats` | Block statistics |
| `GET` | `/admin/survey/active` | Get survey admin info |
| `POST` | `/admin/survey/draft/from-active` | Create draft |
| `PUT` | `/admin/survey/draft/latest` | Update draft |
| `POST` | `/admin/survey/draft/latest/validate` | Validate draft |
| `POST` | `/admin/survey/draft/latest/publish` | Publish draft |
| `POST` | `/admin/survey/rollback` | Rollback to version |

---

## Key Decisions & Rationale

### 1. Email Verification Bypass

**Decision:** All new accounts are automatically verified. Email verification endpoints exist but don't gate access.

**Rationale:** Product decision to reduce friction during pilot. May be re-enabled for production.

**Location:** `api/app/main.py` - `auth_register()`:
```python
# Temporary product decision: bypass email verification gating for all newly created accounts.
auth_repo.set_user_verified(str(created["id"]))
```

### 2. Single-File API Structure

**Decision:** All API endpoints are in `main.py` (~1500 lines) rather than split into routers.

**Rationale:** Simplicity for a small team. Easy to search. May need refactoring as the codebase grows.

### 3. Bidirectional Match Assignments

**Decision:** When A matches with B, two rows are created:
- A → B (score, breakdown)
- B → A (score, breakdown)

**Rationale:** Allows independent status tracking. A can "accept" while B "declines". Simplifies querying by `user_id`.

### 4. Greedy Matching Algorithm

**Decision:** Use greedy one-to-one matching rather than optimization-based approaches (Hungarian algorithm, stable marriage).

**Rationale:**
- Simpler to implement and debug
- Deterministic results
- Works well with hard constraints (blocks, recent matches)
- O(n² log n) complexity acceptable for ~200 users

**Trade-off:** Not globally optimal. Some users may get worse matches than theoretically possible.

### 5. Gender Preference as Hard Gate

**Decision:** Gender preference compatibility is required for a match. No soft scoring.

**Rationale:** Avoids matching users who would never be interested. Reduces noise in the matching pool.

### 6. Lookback Weeks = 6

**Decision:** Users won't be matched with someone they matched with in the past 6 weeks.

**Rationale:** With ~200 users and weekly matching, 6 weeks provides variety while allowing re-pairing after sufficient time.

### 7. 72-Hour Match Expiry

**Decision:** Matches expire 72 hours after creation.

**Rationale:** Encourages timely action. Prevents stale matches from lingering.

### 8. Kids Compatibility as Score Zero

**Decision:** Mismatched kids preferences (yes vs no) result in score = 0, not exclusion.

**Rationale:** Allows users to see they had a potential match but a dealbreaker. Soft landing.

### 9. Sensitive Term Filtering

**Decision:** Words like "kids", "faith", "unconventional" are filtered from explanations.

**Rationale:** Privacy. Users may not want their match to know their specific views on sensitive topics.

### 10. "Dean of Dating" Persona

**Decision:** All match explanations use a consistent persona.

**Rationale:**
- Humanizes the algorithm
- Creates brand identity
- Makes feedback feel more personal

---

## Known Issues & Considerations

### 1. No Real Email Sending

**Issue:** Verification codes are logged to console but not actually emailed.

**Workaround:** Use `DEV_MODE=true` to get codes in logs. Registration auto-verifies.

**Impact:** Email verification is effectively disabled.

### 2. Chat Not Fully Implemented

**Issue:** Database tables exist for chat, but in-app chat UI is minimal.

**Current State:** Users are expected to contact via email/phone/Instagram.

### 3. SQLite for Local Development

**Issue:** The `cbs_match_dev.db` file suggests SQLite support, but production expects Postgres.

**Consideration:** Migration `001_init.sql` uses `pgcrypto` extension (Postgres-specific).

### 4. Mobile API Base URL Configuration

**Issue:** Different URLs needed for:
- iOS Simulator: `http://localhost:8000`
- Android Emulator: `http://10.0.2.2:8000`
- Physical Device: `http://{LAN_IP}:8000`

**Solution:** Set `EXPO_PUBLIC_API_BASE_URL` or use Settings screen.

### 5. Photo Storage is Local Filesystem

**Issue:** Photos stored in `/uploads` directory. Not suitable for production scaling.

**Consideration:** Would need S3/CloudStorage for production.

### 6. No Rate Limiting Persistence

**Issue:** Rate limits are in-memory. Reset on server restart.

**Impact:** Minor during pilot. May need Redis for production.

### 7. Admin Token is Static

**Issue:** Single `ADMIN_TOKEN` environment variable for all admin access.

**Consideration:** No admin user management or audit logging.

### 8. No Notification System

**Issue:** No push notifications or email notifications for new matches.

**Impact:** Users must check the app manually.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Required | Postgres connection string |
| `QUESTIONS_PATH` | `/app/questions.json` | Path to survey definition |
| `JWT_SECRET` | Required | Secret for JWT signing |
| `ADMIN_TOKEN` | None | Admin API access token |
| `DEV_MODE` | `false` | Auto-verify emails, dev code "123456" |
| `MATCH_EXPIRY_HOURS` | `72` | Hours before match expires |
| `MATCH_TIMEZONE` | `America/New_York` | Timezone for week calculations |
| `LOOKBACK_WEEKS` | `6` | Weeks to avoid repeat matches |
| `MIN_SCORE` | `0.55` | Minimum score for matching |
| `BIG5_WEIGHT` | `0.7` | Weight for Big Five similarity |
| `CONFLICT_WEIGHT` | `0.3` | Weight for conflict style similarity |
| `MISMATCH_THRESHOLD` | `0.45` | Threshold for life pref penalty |
| `MODIFIER_PENALTY_CAP` | `0.6` | Max penalty multiplier |
| `MODIFIER_PENALTY_SCALE` | `0.35` | Penalty scaling factor |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | JWT access token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token lifetime |
| `VERIFICATION_TOKEN_TTL_HOURS` | `24` | Email verification code lifetime |
| `RL_*_LIMIT` | Various | Rate limit counts per minute |

---

## Development & Deployment

### Quick Start

```bash
# Start everything (API + web + mobile)
cd /Users/thomascline/Desktop/cbs-match
npm run dev:up

# Or with Docker
docker compose up --build
```

### Access Points

| Service | URL |
|---------|-----|
| Web App | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Admin Dashboard | http://localhost:3000/admin |

### Common Commands

```bash
# Run tests
cd api && pytest -q

# Seed dummy users
python api/scripts/seed.py --n-users 120 --reset --clustered

# Run weekly matching
curl -X POST http://localhost:8000/admin/matches/run-weekly \
  -H "X-Admin-Token: dev-admin-token"

# View calibration report
curl http://localhost:8000/admin/calibration/current-week \
  -H "X-Admin-Token: dev-admin-token"

# Run smoke test
API_BASE_URL=http://localhost:8000 ADMIN_TOKEN=dev-admin-token \
  python scripts/smoke_pilot.py
```

### Make Targets

```bash
make up      # Start services
make down    # Stop services
make seed    # Seed dummy data
make test    # Run tests
make match   # Run weekly matching
```

---

## Summary for External Contributors

CBS Match is a **weekly matching platform** for CBS MBA students. To understand the codebase:

1. **Start with `questions.json`** - Understand what data is collected
2. **Read `matching.py`** - Core algorithm is ~200 lines
3. **Read `traits.py`** - How answers become personality scores
4. **Read `copy_templates.py`** - How matches are explained
5. **Read `main.py`** - All API endpoints in one file

**Key files to modify for improvements:**
- Matching algorithm: `api/app/services/matching.py`
- Personality computation: `api/app/traits.py`
- Explanation generation: `api/app/services/copy_templates.py`
- Survey questions: `questions.json`
- Web UI: `web/app/` (Next.js App Router)
- Mobile UI: `mobile/src/screens/`

**To add a new feature:**
1. Add database migration in `api/migrations/`
2. Add endpoint(s) in `api/app/main.py`
3. Add repository functions in `api/app/repo.py`
4. Add frontend components in `web/app/` or `mobile/src/screens/`
5. Add tests in `api/tests/`

---

*Documentation generated: February 17, 2026*
*Version: CBS Match v1.5*