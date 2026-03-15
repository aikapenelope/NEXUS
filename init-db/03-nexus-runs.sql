-- Run history: stores every agent execution for the dashboard traces view.
-- Runs on first postgres init via docker-entrypoint-initdb.d.

CREATE TABLE IF NOT EXISTS nexus_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID,
    agent_name      VARCHAR(255) NOT NULL DEFAULT 'anonymous',
    prompt          TEXT NOT NULL DEFAULT '',
    output          TEXT NOT NULL DEFAULT '',
    model           VARCHAR(255) NOT NULL DEFAULT '',
    role            VARCHAR(50) NOT NULL DEFAULT 'worker',

    -- Token usage
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,

    -- Performance
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(50) NOT NULL DEFAULT 'completed',

    -- Source: 'build', 'run', 'cerebro', 'copilot'
    source          VARCHAR(50) NOT NULL DEFAULT 'run',

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nexus_runs_created ON nexus_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_nexus_runs_agent ON nexus_runs (agent_id);
CREATE INDEX IF NOT EXISTS idx_nexus_runs_source ON nexus_runs (source);
