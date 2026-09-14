# pkl-spire

Reusable Pkl configuration for SPIRE. The deployment target generates separate Docker Compose files for the server and agent. Shared SPIRE types live separately so future Compose-only and Kubernetes targets can reuse them.

## Status

Local configuration generator, tested with Pkl 0.32.1. Example images use SPIRE 1.15.3. Package version 0.1.0 is distributed through GitHub Releases. Image manifests support Linux amd64 and arm64. Runtime attestation remains to be tested on the intended hosts before deployment.

## Generate and validate

Install Pkl (`brew install pkl` on macOS). Python 3 is needed for tests; current Docker CLI and Compose are needed for deployment-file validation. No Docker daemon is required for these checks.

```sh
make render
make validate
```

If an older Docker CLI shadows Docker Desktop on macOS:

```sh
make validate DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
```

The output directory contains:

- `server.compose.yaml`: one SPIRE server with a published TCP port, run on the chosen server host.
- `server.conf`: JSON configuration accepted by SPIRE, with SQLite and persistent disk keys.
- `agent.compose.yaml`: run separately on each Linux host; uses host PID access and the local Docker socket.
- `agent.conf`: matching trust domain and server endpoint, with verified bootstrap and a per-host join-token file.

Configuration files are read-only bind mounts. Restart or recreate the relevant container after changing its configuration; rendering alone does not apply changes.

## Consumer configuration

Add a named dependency in your consumer's `PklProject`:

```pkl
amends "pkl:Project"

dependencies {
  ["spire"] {
    uri = "package://github.com/faisal-memon/pkl-spire/releases/download/v0.1.0/pkl-spire@0.1.0"
  }
}
```

Run `pkl project resolve` in that directory and check in `PklProject.deps.json` to pin the metadata checksum. Then create your consumer:

```pkl
amends "@spire/src/compose/Deployment.pkl"

trustDomain = "example.org"
serverAddress = "192.0.2.10"
spireVersion = "1.15.3"
hostRoot = "/var/lib/spire"
```

Then run `pkl eval -m out /path/to/consumer.pkl`. Example names and addresses are placeholders. This repository must not contain private environment values, credentials, or generated bootstrap tokens.

## Networking and host access

The server and agents communicate over the existing LAN using the configured server address and TCP port (8081 by default). No shared cross-host Docker network or orchestrator is required. Each workload mounts its local agent's Workload API socket. SPIRE bootstrap establishes trust in the server; network reachability alone does not establish trust.

Run the server Compose file only on the chosen server machine and the agent Compose file on every workload host, including the server host if needed. Each Compose project has its own name, so both can run on one host. The agent uses host PID sharing for process attestation.

The Docker socket grants powerful host access even when its bind mount is marked read-only. Only the agent receives it, not application workloads.

## Deployment sequence (after review)

1. Verify Linux amd64/arm64 image support and the host's Docker/cgroup compatibility. Choose the actual trust domain, server host, port, and data directory.
2. On the server host, create `<hostRoot>/server` owned by UID/GID 1000:1000 (the published server image's default), with restrictive permissions. Back up this directory: it contains the database and signing keys. Only one server replica may use it.
3. Copy `server.conf` and `server.compose.yaml` together to the server host and run `docker compose -f server.compose.yaml up -d`. Allow the configured server TCP port from the agent nodes. The server runs on that host only; this is not a highly available deployment.
4. Export the server's public trust bundle over an authenticated administrative connection. Create `<hostRoot>/bootstrap/bundle.pem` on each agent host. Do not use insecure bootstrap.
5. Generate a separate short-lived join token for each host. Save it to `<hostRoot>/bootstrap/join-token` with root-only access. Never reuse one token for multiple agents or commit tokens. Tokens provision initial identity; persisted agent data supports subsequent restarts. Expired agent state or lost storage may require fresh enrollment.
6. On each agent host, create `<hostRoot>/agent` and `<hostRoot>/bootstrap` owned by root with restrictive permissions, plus `<hostRoot>/sockets` suitable for sharing the Workload API socket. Copy `agent.conf` and `agent.compose.yaml` together, then start the agent with Compose. Review actual socket permissions before attaching workloads.
7. Create explicit workload registrations tied to each agent identity and Docker container labels. Mount `<hostRoot>/sockets` into a disposable workload and request its identity. Verify both allowed and unregistered workloads, then restart an agent and retest.

Rendering does not create directories, bootstrap trust, register identities, deploy services, or change existing Compose workloads. Kubernetes output and a registration controller are future work.

## Layout

- `src/core/Common.pkl`: shared validation types.
- `src/core/Server.pkl` and `Agent.pkl`: independently usable typed settings and defaults, without rendering logic.
- `src/render/ServerConfig.pkl` and `AgentConfig.pkl`: map typed settings into SPIRE's field names and serialize JSON.
- `src/compose/Deployment.pkl`: combines settings with Docker mounts, images, ports, and YAML output.
- `examples/compose.pkl`: generic consumer example.
- `tests/test_generation.py`: consumer overrides, validation failures, storage, and bootstrap invariants.

To render only a server configuration, amend `src/render/ServerConfig.pkl` in a consumer module and set `settings { trustDomain = "example.org" }`. For an agent, amend `AgentConfig.pkl` and supply its trust domain and server address. Neither renderer depends on Docker.

## References

- [SPIRE agent configuration and JSON support](https://github.com/spiffe/spire/blob/v1.15.3/doc/spire_agent.md)
- [SPIRE image entrypoints and ownership](https://github.com/spiffe/spire/blob/v1.15.3/Dockerfile)
- [Docker attestor](https://github.com/spiffe/spire/blob/v1.15.3/doc/plugin_agent_workloadattestor_docker.md)

## Releases

PRs run the generation tests, Compose validation, and package construction. Merges to `main` publish a release using `faisal-memon/pr-label-semver@v0`:

- `semver:major`: breaking configuration API changes.
- `semver:minor`: new backward-compatible capabilities.
- `semver:patch`: fixes; also the default when no version label is present.

The action calculates the next tag without writing it. Packaging injects that version through the `PKL_PACKAGE_VERSION` environment variable, so metadata, package URI, source links, and ZIP URL agree. Only successful validation and packaging proceed to tag/release creation. Assets upload into a draft release before publication. Release runs are serialized. A failed upload/publication may leave a draft release; recover that release instead of deleting or overwriting published package versions. A manual run from `main` can select a bump explicitly.

`PklProject` defaults to 0.1.0 for local development. To build another version locally, run `make package VERSION=0.2.0`. Do not edit the manifest version for each release or overwrite published versions. Consumer repositories keep exact versions and checksum lockfiles until deliberately upgraded.

Pkl is pinned to 0.32.1 in CI and its downloaded binary is checked against the release asset's SHA-256 digest. The setup action targets Linux amd64 runners.

Licensed under MIT; see LICENSE.
