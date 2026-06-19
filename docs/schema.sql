-- ============================================================
-- DynaConSurv HR System — PostgreSQL Schema v5
-- Architecture: 5 entity tables + shared lookups + polymorphic junctions
-- ============================================================

-- ── Extensions ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ════════════════════════════════════════════════════════════
-- USERS & ORG STRUCTURE
-- ════════════════════════════════════════════════════════════

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name   VARCHAR(300) NOT NULL,
    email       VARCHAR(300) NOT NULL UNIQUE,
    role        VARCHAR(50) NOT NULL DEFAULT 'hr',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role  ON users (role) WHERE is_active = true;
CREATE INDEX trgm_users_name ON users USING GIN (full_name gin_trgm_ops);

CREATE TABLE departments (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL UNIQUE,
    parent_id   INT REFERENCES departments(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_departments_parent ON departments (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX trgm_departments_name  ON departments USING GIN (name gin_trgm_ops);

CREATE TABLE positions (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(500) NOT NULL,
    department_id   INT REFERENCES departments(id),
    description     TEXT,
    employment_type VARCHAR(50) NOT NULL DEFAULT 'full_time',
    status          VARCHAR(50) NOT NULL DEFAULT 'open',
    required_tags   JSONB DEFAULT '[]'::jsonb,
    min_experience  SMALLINT,
    salary_min      NUMERIC(12,2),
    salary_max      NUMERIC(12,2),
    currency        VARCHAR(10) DEFAULT 'MYR',
    created_by      UUID REFERENCES users(id),
    posted_at       TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_positions_department ON positions (department_id) WHERE department_id IS NOT NULL;
CREATE INDEX idx_positions_status     ON positions (status) WHERE status = 'open' AND deleted_at IS NULL;
CREATE INDEX trgm_positions_title     ON positions USING GIN (title gin_trgm_ops);

CREATE TABLE hiring_stages (
    id            SERIAL PRIMARY KEY,
    position_id   INT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    sort_order    SMALLINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_hiring_stages_position ON hiring_stages (position_id);

-- ════════════════════════════════════════════════════════════
-- PROJECTS (for manpower assignment)
-- ════════════════════════════════════════════════════════════

CREATE TABLE hr_projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(500) NOT NULL,
    client      VARCHAR(500),
    description TEXT,
    start_date  DATE,
    end_date    DATE,
    status      VARCHAR(50) DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_hr_projects_status ON hr_projects (status);

-- ════════════════════════════════════════════════════════════
-- 5 MAIN ENTITY TABLES
-- Each owns its personal info. No shared persons table.
-- Pipeline: applicant → intern → staff (with past_applicant archive).
-- Manpower is separate pool (contract workers).
-- ════════════════════════════════════════════════════════════

-- ── 1. Applicant (active hiring pipeline) ──────────────────
CREATE TABLE applicant (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id     INT REFERENCES positions(id),
    department_id   INT REFERENCES departments(id),

    full_name       VARCHAR(300),
    email           VARCHAR(300),
    phone           VARCHAR(100),
    location        VARCHAR(500),
    linkedin        VARCHAR(500),
    website         VARCHAR(500),
    photo_path      VARCHAR(500),
    summary         TEXT,

    source          VARCHAR(100),
    status          VARCHAR(50) NOT NULL DEFAULT 'new',
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    notes           TEXT,
    raw_json        JSONB,

    assigned_to     UUID REFERENCES users(id),
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_applicant_email      ON applicant (email)     WHERE email IS NOT NULL;
CREATE INDEX idx_applicant_status     ON applicant (status)    WHERE deleted_at IS NULL;
CREATE INDEX idx_applicant_position   ON applicant (position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_applicant_department ON applicant (department_id) WHERE department_id IS NOT NULL;
CREATE INDEX idx_applicant_assigned   ON applicant (assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_applicant_applied    ON applicant (applied_at WHERE deleted_at IS NULL);
CREATE INDEX idx_applicant_rating     ON applicant (rating)    WHERE rating IS NOT NULL;
CREATE INDEX trgm_applicant_name      ON applicant USING GIN (full_name gin_trgm_ops);

-- ── 2. Past Applicant (archive — full snapshot) ────────────
CREATE TABLE past_applicant (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id    UUID NOT NULL,
    position_id     INT REFERENCES positions(id),

    full_name       VARCHAR(300),
    email           VARCHAR(300),
    phone           VARCHAR(100),
    location        VARCHAR(500),
    linkedin        VARCHAR(500),
    website         VARCHAR(500),
    photo_path      VARCHAR(500),
    summary         TEXT,

    source          VARCHAR(100),
    final_status    VARCHAR(50) NOT NULL,
    reason          TEXT,
    rating          SMALLINT,
    raw_json        JSONB,

    applied_at      TIMESTAMPTZ,
    archived_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_past_applicant_email  ON past_applicant (email) WHERE email IS NOT NULL;
CREATE INDEX idx_past_applicant_status ON past_applicant (final_status);
CREATE INDEX idx_past_applicant_date   ON past_applicant (archived_at);
CREATE INDEX trgm_past_applicant_name  ON past_applicant USING GIN (full_name gin_trgm_ops);

-- ── 3. Intern ──────────────────────────────────────────────
CREATE TABLE intern (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id    UUID,
    position_id     INT REFERENCES positions(id),
    department_id   INT REFERENCES departments(id),
    supervisor_id   UUID REFERENCES users(id),

    full_name       VARCHAR(300),
    email           VARCHAR(300),
    phone           VARCHAR(100),
    location        VARCHAR(500),
    photo_path      VARCHAR(500),

    start_date      DATE NOT NULL,
    end_date        DATE,
    stipend         NUMERIC(12,2),
    currency        VARCHAR(10) DEFAULT 'MYR',

    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_intern_email      ON intern (email)      WHERE email IS NOT NULL;
CREATE INDEX idx_intern_status     ON intern (status)     WHERE deleted_at IS NULL;
CREATE INDEX idx_intern_department ON intern (department_id) WHERE department_id IS NOT NULL;
CREATE INDEX idx_intern_supervisor ON intern (supervisor_id) WHERE supervisor_id IS NOT NULL;
CREATE INDEX idx_intern_start_date ON intern (start_date);
CREATE INDEX trgm_intern_name      ON intern USING GIN (full_name gin_trgm_ops);

-- ── 4. Staff ───────────────────────────────────────────────
CREATE TABLE staff (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id    UUID,
    intern_id       UUID,
    position_id     INT REFERENCES positions(id),
    department_id   INT REFERENCES departments(id),
    supervisor_id   UUID REFERENCES users(id),

    full_name       VARCHAR(300),
    email           VARCHAR(300),
    phone           VARCHAR(100),
    location        VARCHAR(500),
    photo_path      VARCHAR(500),

    employment_type VARCHAR(50) NOT NULL DEFAULT 'full_time',
    start_date      DATE NOT NULL,
    end_date        DATE,
    salary          NUMERIC(12,2),
    currency        VARCHAR(10) DEFAULT 'MYR',

    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_staff_email          ON staff (email)           WHERE email IS NOT NULL;
CREATE INDEX idx_staff_status         ON staff (status)          WHERE deleted_at IS NULL;
CREATE INDEX idx_staff_department     ON staff (department_id)   WHERE department_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_staff_position       ON staff (position_id)     WHERE position_id IS NOT NULL;
CREATE INDEX idx_staff_supervisor     ON staff (supervisor_id)   WHERE supervisor_id IS NOT NULL;
CREATE INDEX idx_staff_employment     ON staff (employment_type);
CREATE INDEX idx_staff_start_date     ON staff (start_date);
CREATE INDEX trgm_staff_name          ON staff USING GIN (full_name gin_trgm_ops);

-- ── 5. Manpower (contract workers) ─────────────────────────
CREATE TABLE manpower (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id    UUID,
    position_id     INT REFERENCES positions(id),

    full_name       VARCHAR(300),
    email           VARCHAR(300),
    phone           VARCHAR(100),

    agency          VARCHAR(500),
    project_id      INT REFERENCES hr_projects(id),

    start_date      DATE NOT NULL,
    end_date        DATE,
    contract_value  NUMERIC(12,2),
    currency        VARCHAR(10) DEFAULT 'MYR',

    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_manpower_email    ON manpower (email)     WHERE email IS NOT NULL;
CREATE INDEX idx_manpower_status   ON manpower (status)    WHERE deleted_at IS NULL;
CREATE INDEX idx_manpower_project  ON manpower (project_id) WHERE project_id IS NOT NULL;
CREATE INDEX idx_manpower_agency   ON manpower (agency)    WHERE agency IS NOT NULL;
CREATE INDEX trgm_manpower_name    ON manpower USING GIN (full_name gin_trgm_ops);

-- ════════════════════════════════════════════════════════════
-- SHARED LOOKUP TABLES (normalized, one row per unique value)
-- ════════════════════════════════════════════════════════════

CREATE TABLE skills (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(200) NOT NULL UNIQUE
);
CREATE INDEX trgm_skills_name ON skills USING GIN (name gin_trgm_ops);

CREATE TABLE tags (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(200) NOT NULL UNIQUE
);
CREATE INDEX trgm_tags_name ON tags USING GIN (name gin_trgm_ops);

CREATE TABLE degrees (
    id              SERIAL PRIMARY KEY,
    institution     VARCHAR(500) NOT NULL,
    degree          VARCHAR(500) NOT NULL,
    UNIQUE(institution, degree)
);
CREATE INDEX trgm_degrees_inst   ON degrees USING GIN (institution gin_trgm_ops);
CREATE INDEX trgm_degrees_degree ON degrees USING GIN (degree gin_trgm_ops);

CREATE TABLE certifications (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(500) NOT NULL,
    institute       VARCHAR(500),
    validity_start  DATE,
    validity_end    DATE,
    level           VARCHAR(100),
    UNIQUE(name, institute)
);
CREATE INDEX idx_certifications_name   ON certifications (name);
CREATE INDEX idx_certifications_level  ON certifications (level) WHERE level IS NOT NULL;
CREATE INDEX trgm_certifications_name  ON certifications USING GIN (name gin_trgm_ops);

-- ════════════════════════════════════════════════════════════
-- POLYMORPHIC JUNCTION TABLES
-- entity_type: 'applicant','past_applicant','intern','staff','manpower'
-- ════════════════════════════════════════════════════════════

CREATE TABLE entity_skills (
    entity_type VARCHAR(50) NOT NULL,
    entity_id   UUID NOT NULL,
    skill_id    INT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_type, entity_id, skill_id)
);
CREATE INDEX idx_entity_skills_skill ON entity_skills (skill_id);
CREATE INDEX idx_entity_skills_entity ON entity_skills (entity_type, entity_id);

CREATE TABLE entity_tags (
    entity_type VARCHAR(50) NOT NULL,
    entity_id   UUID NOT NULL,
    tag_id      INT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_type, entity_id, tag_id)
);
CREATE INDEX idx_entity_tags_tag ON entity_tags (tag_id);
CREATE INDEX idx_entity_tags_entity ON entity_tags (entity_type, entity_id);

CREATE TABLE entity_degrees (
    entity_type     VARCHAR(50) NOT NULL,
    entity_id       UUID NOT NULL,
    degree_id       INT NOT NULL REFERENCES degrees(id) ON DELETE CASCADE,
    graduation_year VARCHAR(4),
    result          VARCHAR(50),
    sort_order      SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (entity_type, entity_id, degree_id)
);
CREATE INDEX idx_entity_degrees_degree ON entity_degrees (degree_id);
CREATE INDEX idx_entity_degrees_entity ON entity_degrees (entity_type, entity_id);

CREATE TABLE entity_certifications (
    entity_type       VARCHAR(50) NOT NULL,
    entity_id         UUID NOT NULL,
    certification_id  INT NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    PRIMARY KEY (entity_type, entity_id, certification_id)
);
CREATE INDEX idx_entity_certs_cert   ON entity_certifications (certification_id);
CREATE INDEX idx_entity_certs_entity ON entity_certifications (entity_type, entity_id);

CREATE TABLE entity_experiences (
    id              SERIAL PRIMARY KEY,
    entity_type     VARCHAR(50) NOT NULL,
    entity_id       UUID NOT NULL,
    company         VARCHAR(500) NOT NULL,
    title           VARCHAR(500) NOT NULL,
    start_date      VARCHAR(7),
    end_date        VARCHAR(7),
    location        VARCHAR(500),
    description     JSONB DEFAULT '[]'::jsonb,
    sort_order      SMALLINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_entity_exp_entity  ON entity_experiences (entity_type, entity_id);
CREATE INDEX idx_entity_exp_company ON entity_experiences (company);
CREATE INDEX idx_entity_exp_title   ON entity_experiences (title);
CREATE INDEX trgm_entity_exp_co     ON entity_experiences USING GIN (company gin_trgm_ops);

CREATE TABLE entity_projects (
    id              SERIAL PRIMARY KEY,
    entity_type     VARCHAR(50) NOT NULL,
    entity_id       UUID NOT NULL,
    name            VARCHAR(500) NOT NULL,
    role            VARCHAR(500),
    start_date      VARCHAR(7),
    end_date        VARCHAR(7),
    description     JSONB DEFAULT '[]'::jsonb,
    sort_order      SMALLINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_entity_proj_entity ON entity_projects (entity_type, entity_id);
CREATE INDEX idx_entity_proj_name   ON entity_projects (name);

-- ════════════════════════════════════════════════════════════
-- HIRING PIPELINE: STATUS AUDIT + INTERVIEWS + TRANSITIONS
-- ════════════════════════════════════════════════════════════

-- ── Hiring Status Audit Log ────────────────────────────────
CREATE TABLE hiring_status (
    id              SERIAL PRIMARY KEY,
    applicant_id    UUID NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    stage_id        INT REFERENCES hiring_stages(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,
    from_status     VARCHAR(50),
    to_status       VARCHAR(50),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_hiring_status_applicant ON hiring_status (applicant_id);
CREATE INDEX idx_hiring_status_user      ON hiring_status (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_hiring_status_created   ON hiring_status (created_at);

-- ── Interview Schedule (separate from general calendar) ────
CREATE TABLE interview_schedule (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id    UUID NOT NULL,
    position_id     INT REFERENCES positions(id),
    stage_id        INT REFERENCES hiring_stages(id),
    interviewer_id  UUID REFERENCES users(id),

    title           VARCHAR(500) NOT NULL,
    scheduled_at    TIMESTAMPTZ NOT NULL,
    duration_mins   SMALLINT,
    location        VARCHAR(500),

    status          VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    notes           TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_interview_applicant   ON interview_schedule (applicant_id);
CREATE INDEX idx_interview_interviewer ON interview_schedule (interviewer_id) WHERE interviewer_id IS NOT NULL;
CREATE INDEX idx_interview_scheduled   ON interview_schedule (scheduled_at);
CREATE INDEX idx_interview_status      ON interview_schedule (status);

-- ── Entity Transitions (pipeline movement audit) ───────────
CREATE TABLE entity_transitions (
    id                SERIAL PRIMARY KEY,
    from_entity_type  VARCHAR(50) NOT NULL,
    from_entity_id    UUID NOT NULL,
    to_entity_type    VARCHAR(50) NOT NULL,
    to_entity_id      UUID NOT NULL,
    notes             TEXT,
    created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    transitioned_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_transitions_from ON entity_transitions (from_entity_type, from_entity_id);
CREATE INDEX idx_transitions_to   ON entity_transitions (to_entity_type, to_entity_id);
CREATE INDEX idx_transitions_date ON entity_transitions (transitioned_at);

-- ════════════════════════════════════════════════════════════
-- GENERAL CALENDAR (meetings, onboarding — NOT interviews)
-- ════════════════════════════════════════════════════════════

CREATE TABLE calendar_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    event_type      VARCHAR(50) NOT NULL,

    organizer_id    UUID REFERENCES users(id) ON DELETE SET NULL,

    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    location        VARCHAR(500),
    is_all_day      BOOLEAN NOT NULL DEFAULT false,
    status          VARCHAR(50) NOT NULL DEFAULT 'scheduled',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_calendar_organizer  ON calendar_events (organizer_id) WHERE organizer_id IS NOT NULL;
CREATE INDEX idx_calendar_time_range ON calendar_events (start_time, end_time);
CREATE INDEX idx_calendar_event_type ON calendar_events (event_type);
CREATE INDEX idx_calendar_status     ON calendar_events (status);

CREATE TABLE calendar_event_attendees (
    event_id    UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(50) DEFAULT 'attendee',
    response    VARCHAR(50) DEFAULT 'pending',
    PRIMARY KEY (event_id, user_id)
);
CREATE INDEX idx_event_attendees_user ON calendar_event_attendees (user_id);

-- ════════════════════════════════════════════════════════════
-- TRIGGERS: auto-update updated_at
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_positions_updated
    BEFORE UPDATE ON positions FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_hr_projects_updated
    BEFORE UPDATE ON hr_projects FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_applicant_updated
    BEFORE UPDATE ON applicant FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_intern_updated
    BEFORE UPDATE ON intern FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_staff_updated
    BEFORE UPDATE ON staff FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_manpower_updated
    BEFORE UPDATE ON manpower FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_interview_updated
    BEFORE UPDATE ON interview_schedule FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_calendar_events_updated
    BEFORE UPDATE ON calendar_events FOR EACH ROW EXECUTE FUNCTION update_timestamp();
