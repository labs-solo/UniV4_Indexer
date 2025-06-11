## Envio ERC20 Template

*Please refer to the [documentation website](https://docs.envio.dev) for a thorough guide on all [Envio](https://envio.dev) indexer features*

### Run

```bash
pnpm dev
```

Visit http://localhost:8080 to see the GraphQL Playground, local password is `testing`.

### Configuration

The indexer uses several ports for different services:
- `8080`: GraphQL/Hasura interface for querying indexed data
- `9898`: Metrics endpoint for monitoring (configurable via `METRICS_PORT`)
- `5432`: PostgreSQL database for data storage

If you encounter port conflicts, you can modify the metrics port by setting the `METRICS_PORT` environment variable in your `.env` file:

```bash
METRICS_PORT=9899  # Use any available port
```

For other port configurations:
- GraphQL port can be modified in docker-compose.yml
- Database port can be changed in docker-compose.yml and .env

### Generate files from `config.yaml` or `schema.graphql`

```bash
pnpm codegen
```

### Pre-requisites

- [Node.js (use v18 or newer)](https://nodejs.org/en/download/current)
- [pnpm (use v8 or newer)](https://pnpm.io/installation)
- [Docker desktop](https://www.docker.com/products/docker-desktop/)

### Troubleshooting

If you encounter the error `EADDRINUSE: address already in use :::9898`:
1. Check if another instance of the indexer is running
2. Set a different `METRICS_PORT` in your `.env` file
3. Kill any stray processes: `pkill -f "envio dev"`

For other port-related issues:
1. Check if ports 8080 or 5432 are in use
2. Modify the corresponding port mappings in docker-compose.yml
3. Update any related environment variables in .env
