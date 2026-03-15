#!/bin/bash
# Create additional databases needed by services.
# Runs automatically on first postgres init (docker-entrypoint-initdb.d).
#
# Currently the main 'nexus' database is created by POSTGRES_DB env var.
# Add extra CREATE DATABASE statements here if new services need isolation.
set -e

echo "Database initialization complete — using default nexus database."
