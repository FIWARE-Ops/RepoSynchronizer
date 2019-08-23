![FIWARE Banner](https://nexus.lab.fiware.org/content/images/fiware-logo1.png)

# GitHub Repository Synchronizer
[![Docker badge](https://img.shields.io/docker/pulls/fiware/service.reposynchronizer.svg)](https://hub.docker.com/r/fiware/service.reposynchronizer/)
[![Build Status](https://travis-ci.org/FIWARE-Ops/RepoSynchronizer.svg?branch=master)](https://travis-ci.org/FIWARE-Ops/RepoSynchronizer)

## Overview
This project is part of [FIWARE](https://fiware.org) OPS infrastructure.
It synchronize (mirror) GitHub repositories in automatic mode, as service (synchronize commits, releases, create and delete operations).

## How to run
```console
$ docker run -it --rm \
             -e TOKEN=${TOKEN} \
             -e GH_USER=${USER} \
             -p 0.0.0.0:${PORT}:${PORT} \
             fiware/service.reposynchronizer \
             --ip 0.0.0.0 \
             --port ${PORT} \
             --config ${PATH_TO_CONFIG}
```
```console
$ curl http://localhost:${PORT}/ping
```
## How to configure
+ To work with GitHub, you should provide a valid token with an environment variable TOKEN and username with environment variable GH_USER.
+ Sample config is located [here](./config-example.json). 

## How to use
Ping
```console
$ curl http://localhost:${PORT}/ping
```
Get version
```console
$ curl http://localhost:${PORT}/version
```

## GitHub integration
This project works as an endpoint and it should receive notifications from GitHub, so you should configure the webhook in the GitHub repository:
* application/json
* push, create, delete, release events
* no secrets
