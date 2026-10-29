# URL Shortener Service with Click Analytics

Create short links, redirect by short code (HTTP 302) and read per-link details and click analytics. All operations are public (no authentication).

## Features

- Submit a long URL and receive a new short link identified by a service-generated short code. Clients cannot supply a custom alias.
- Each create submission produces a new, independent short link with its own short code and click count, even if the same long URL was submitted before.
- Only absolute http or https URLs are accepted. Any other value is rejected with a 4xx response and no short link is created.
- Requesting a short code redirects (302) to the original long URL.
- Each successful redirect increments the click count by exactly one and records the timestamp of the most recent click. There is no de-duplication or bot filtering.
- Retrieve a short link's details (short code, original long URL, creation timestamp).
- Retrieve a short link's analytics (total click count and last-click timestamp) through a separate per-link call. A link never clicked reports a click count of 0 and a null last-click timestamp.
- Redirect, details and analytics return 404 Not Found for an unknown short code.

## Prerequisites

- Stack: java21-springboot3-maven (Java 21 and Maven).

## Build and test

```
mvn -q -B verify
```

## Run

```
sh -c java -jar target/*.jar
```

## Configuration

Environment variables:

| Variable | Description |
|----------|-------------|
| PORT | HTTP port (required) |
| DB_PATH | SQLite database file path (default `app.db`) |

## Non-functional features

None specified.

## Startup readiness line

When the service is ready it prints:

```
SERVICE_READY port=<port>
```

See [docs/API.md](docs/API.md) for the API reference.
