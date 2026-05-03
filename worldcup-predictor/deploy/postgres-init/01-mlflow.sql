-- Bootstrap a separate database + role for the MLflow Tracking Server.
-- Mounted into the postgres container at /docker-entrypoint-initdb.d/ and
-- runs once on first volume creation.

CREATE USER mlflow WITH PASSWORD 'mlflow';
CREATE DATABASE mlflow OWNER mlflow;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO mlflow;
