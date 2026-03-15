-- Agent Registry: stores AgentConfig objects created by the builder.
-- Runs on first postgres init via docker-entrypoint-initdb.d.

CREATE TABLE IF NOT EXISTS nexus_agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    instructions    TEXT NOT NULL DEFAULT '',
    role            VARCHAR(50) NOT NULL DEFAULT 'worker',

    -- Feature toggles (mirror AgentConfig fields)
    include_todo        BOOLEAN NOT NULL DEFAULT TRUE,
    include_filesystem  BOOLEAN NOT NULL DEFAULT FALSE,
    include_subagents   BOOLEAN NOT NULL DEFAULT FALSE,
    include_skills      BOOLEAN NOT NULL DEFAULT FALSE,
    include_memory      BOOLEAN NOT NULL DEFAULT FALSE,
    include_web         BOOLEAN NOT NULL DEFAULT FALSE,
    context_manager     BOOLEAN NOT NULL DEFAULT TRUE,

    -- Limits
    token_limit     INTEGER,
    cost_budget_usd DOUBLE PRECISION,

    -- Runtime metadata
    status          VARCHAR(50) NOT NULL DEFAULT 'ready',
    total_runs      INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_run_at     TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_nexus_agents_name ON nexus_agents (name);
CREATE INDEX IF NOT EXISTS idx_nexus_agents_created ON nexus_agents (created_at DESC);
