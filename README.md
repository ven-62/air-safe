# AIR-SAFE API

AIR-SAFE is a FastAPI backend for an air quality monitoring system. ESP32 devices send station readings to the server, the backend stores the data in PostgreSQL, and admin/front-end clients can read the latest data or send commands to stations.

## Prerequisites

Before you start, install:

- Python 3.10 or newer
- Git
- PostgreSQL, either on your local machine or from a hosted provider

The backend uses these Python packages:

- FastAPI
- Uvicorn
- SQLAlchemy
- psycopg2-binary
- python-dotenv

## Clone the repository

```bash
git clone https://github.com/ven-62/air-safe.git
```

If you already have the repository open in VS Code, you can skip the clone step and start from the project folder.

## Create and activate a virtual environment

On Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run this once in the same terminal:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

On Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

## Install dependencies

With the virtual environment activated, install the required packages:

```bash
pip install -r requirements.txt
```

## Set up the database

This project connects to PostgreSQL using the values in the `.env` file. The connection string is built from `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`.

### Option 1: Local PostgreSQL

1. Install PostgreSQL on your machine.
2. Start the PostgreSQL service.
3. Create a database and user for AIR-SAFE.
4. Make sure the database credentials can be used from the backend.

Example using `psql`:

```sql
CREATE DATABASE air_safe;
CREATE USER airsafe_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE air_safe TO airsafe_user;
```

Then use your local host settings in `.env`.

### Option 2: Hosted PostgreSQL

You can also use a hosted PostgreSQL provider such as Neon, Supabase, Railway, or Render.

1. Create a PostgreSQL database on the provider.
2. Copy the host, port, username, password, and database name.
3. If the provider gives you a connection string, split it into the `.env` values used by this project.

This backend uses `sslmode=require` in the database connection, which is suitable for most hosted PostgreSQL services.

### Important note about table creation

When the server starts, it runs `Base.metadata.create_all(bind=engine)`, so the database tables are created automatically as long as the database credentials are correct and the database is reachable.

## Create the `.env` file

Create a file named `.env` in the project root and add the following variables:

```env
DB_NAME=air_safe
DB_HOST=localhost
DB_PASSWORD=your_password
DB_PORT=5432
DB_USER=airsafe_user
SECRET_KEY=your_secret_key
```

### Example values

For a local PostgreSQL setup:

```env
DB_NAME=air_safe
DB_HOST=localhost
DB_PASSWORD=your_password
DB_PORT=5432
DB_USER=postgres
SECRET_KEY=change_this_to_a_long_random_string
```

For a hosted PostgreSQL setup, replace `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, and `DB_NAME` with the values provided by your database service.

## Run the server

Start the API with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server should now be available at:

```text
http://127.0.0.1:8000
```

Interactive API docs are available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## API endpoints

The application exposes three main route groups:

### Root

- `GET /` returns a simple connection status response.

### Station data routes

Base path: `/stn`

- `POST /stn/{station_id}/readings` receives sensor readings from a station and stores/processes the incoming data.
- `POST /stn/{station_id}/report` is reserved for retrieving station-related data, but the current implementation is still a placeholder.

Headers required by these station routes:

- `AS-Auth-Key`

### Dashboard read routes

Base path: `/read`

- `GET /read/{station_id}` returns pollutant data for a specific station for dashboard or frontend consumption.

### Command routes

Base path: `/cmd`

These endpoints are intended for admin or server-side command operations. They use signed request headers.

- `POST /cmd/station/{station_id}` sends a command to one station.
- `POST /cmd/stations` sends a command to multiple stations.
- `POST /cmd/stations/all` sends a command to all stations.
- `GET /cmd/stations/add` adds a new station to the system.
- `GET /cmd/stations/remove` removes an existing station.
- `GET /cmd/stations/modify` updates station details.
- `GET /cmd/list` returns station information for the requested station id.

Headers required by the command routes:

- `AS-Timestamp`
- `AS-Nonce`
- `AS-Signature`

### Request notes

- `POST /cmd/station/{station_id}`, `POST /cmd/stations`, and `POST /cmd/stations/all` expect a JSON body matching the command schema used by the backend.
- The `add`, `remove`, `modify`, and `list` command endpoints currently accept a request body/query payload named `data` in the code and are verified with the same signature headers.
- If you are integrating a frontend or another service, make sure the payload you sign matches the server-side JSON serialization used by the backend.

## Example startup flow

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Provision a PostgreSQL database locally or on a hosting platform.
5. Create the `.env` file with the correct database credentials and `SECRET_KEY`.
6. Start the server with Uvicorn.
7. Open `http://127.0.0.1:8000/docs` to test the endpoints.

## Troubleshooting

- If the app fails to connect to the database, double-check the `.env` values and confirm the PostgreSQL server is running.
- If you are using a local database and connection errors mention SSL, confirm that your PostgreSQL server supports SSL or switch to a hosted provider that does.
- If dependency installation fails, make sure the virtual environment is activated before running `pip install -r requirements.txt`.
