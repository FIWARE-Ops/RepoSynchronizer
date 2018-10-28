![FIWARE Banner](https://nexus.lab.fiware.org/content/images/fiware-logo1.png)

# GitHub Repository Synchronizer
[![Docker badge](https://img.shields.io/docker/pulls/fiware/service.reposynchronizer.svg)](https://hub.docker.com/r/fiware/service.reposynchronizer/)
[![Build Status](https://travis-ci.org/FIWARE-Ops/RepoSynchronizer.svg?branch=master)](https://travis-ci.org/FIWARE-Ops/RepoSynchronizer)

## Overview
This project is part of [FIWARE](https://fiware.org) OPS infrastructure.
It synchronize (mirror) GitHub repositories in automatic mode, as service (synchronize commits, releases, create and delete operations).

## How to run
```console
$ docker run -e TOKEN=${TOKEN} \
             -e TOKEN_GITHUB=${TOKEN_GITHUB} \
             -p 0.0.0.0:${PORT}:${PORT} \
             fiware/service.githubreposynchronizer \
             --ip 0.0.0.0 \
             --port ${PORT} \
             --config ${PATH_TO_CONFIG} \
             --threads ${THREADS} \
             --socks ${SOCKS} \
             --user ${USER}
```
```console
$ curl http://localhost:8000/ping
```

## How to configure
Sample config is located [here](./config-example.json).
You should provide a valid token for GitHub with an environment variable TOKEN_GITHUB.
TOKEN is used to protect the API endpoint "/config", if not specified, the endpoint will be inaccessible.
You can mount workspace from host (add option `-v` to `docker run` command, target path should be the same, as in config) to preserve it's state.

## How to use
Ping
```console
$ curl http://localhost:8000/ping
```
Get version
```console
$ curl http://localhost:8000/version
```
Get current config
```console
$ curl http://localhost:8000/config?token=${TOKEN}
```
Sync
```console
$ curl -X POST http://localhost:8000/sync?repo=${SOURCE_REPO}
```
## GitHub integration
This project works as an endpoint and it should receive notifications from GitHub, so you should configure the webhook in the GitHub repository:
* application/json
* all events
* no secrets
