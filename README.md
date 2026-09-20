# pkl-spire

Reusable Pkl configuration for SPIRE. The deployment module renders separate Docker Compose files for a SPIRE server and its agents, while the core and renderer modules can be reused by other targets later.

## Example

Add the package to a consumer's `PklProject`:

```pkl
amends "pkl:Project"

dependencies {
  ["spire"] {
    uri = "package://github.com/faisal-memon/pkl-spire/releases/download/v0.1.0/pkl-spire@0.1.0"
  }
}
```

Then create a deployment:

```pkl
amends "@spire/src/compose/Deployment.pkl"

trustDomain = "example.org"
serverAddress = "192.0.2.10"
hostRoot = "/var/lib/spire"
```

The SPIRE image version has a module default and can be overridden when a deployment needs a specific version. Replace the example trust domain and address for a real environment.

## Generate and validate

Install Pkl (`brew install pkl` on macOS). Python 3 and Docker Compose are needed for the local checks; a running Docker daemon is not required.

```sh
make render
make validate
```

The generated directory contains server and agent Compose files plus their JSON configuration. Rendering does not deploy containers or create bootstrap credentials.

## Consumer configuration

Run `pkl project resolve` in the consumer repository and commit `PklProject.deps.json` to pin the package checksum. Render the consumer with:

```sh
pkl eval -m out /path/to/consumer.pkl
```

Keep private environment values, credentials, bootstrap tokens, and generated files out of this repository.

## Networking and host access

The server and agents communicate over the configured LAN address and TCP port. No shared Docker network or orchestrator is required. Workloads use the local agent's Workload API socket.

The agent uses host PID sharing and the Docker socket for process attestation. The Docker socket grants powerful host access, so it must not be exposed to application workloads.

## Layout

- `src/core`: shared typed settings and validation.
- `src/render`: SPIRE configuration renderers.
- `src/compose/Deployment.pkl`: Compose deployment model and output.
- `examples/compose.pkl`: generic consumer example.
- `tests/test_generation.py`: generation and validation tests.

## References

- [SPIRE agent configuration](https://github.com/spiffe/spire/blob/v1.15.3/doc/spire_agent.md)
- [SPIRE Docker attestor](https://github.com/spiffe/spire/blob/v1.15.3/doc/plugin_agent_workloadattestor_docker.md)

Licensed under MIT; see [LICENSE](LICENSE).
