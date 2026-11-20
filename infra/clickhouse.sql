CREATE DATABASE IF NOT EXISTS assemblylens;
CREATE TABLE IF NOT EXISTS assemblylens.events (
 id String, tenant String, action LowCardinality(String), payload String,
 received DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(received)
PARTITION BY toYYYYMM(received)
ORDER BY (tenant,id)
TTL received + INTERVAL 365 DAY;
-- Use FINAL or argMax when duplicate-sensitive: outbox delivery is at least once.
