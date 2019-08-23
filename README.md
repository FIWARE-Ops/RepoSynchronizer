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
             -p 0.0.0.0:8080:8080 \
             fiware/service.reposynchronizer \
             --ip 0.0.0.0 \
             --port ${PORT} \
             --config ${PATH_TO_CONFIG}
```
```console
$ curl http://localhost:8080/ping
```
## How to configure
+ To work with GitHub, you should provide a valid token with an environment variable TOKEN.
+ Sample config is located [here](./config-example.json). 

## How to use
Ping
```console
$ curl http://localhost:8080/ping
```
Get version
```console
$ curl http://localhost:8000/version
```

## GitHub integration
This project works as an endpoint and it should receive notifications from GitHub, so you should configure the webhook in the GitHub repository:
* application/json
* push, create, delete, release events
* no secrets
