# Self-hosted Redis for Fly.io with AOF persistence on a mounted volume.
FROM redis:7-alpine

# Persist to the mounted volume at /data (see fly.toml [[mounts]]).
CMD ["redis-server", "--appendonly", "yes", "--dir", "/data"]
