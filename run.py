#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from aiohttp import web, ClientSession, ClientConnectorError
from argparse import ArgumentParser
from logging import error, getLogger
from os import path, environ
from uvloop import EventLoopPolicy
from yajl import dumps, loads
import asyncio

config = dict()
locks = dict()
version = dict()
routes = web.RouteTableDef()
api_url = 'https://api.github.com/'
token = None
workspace = None
description = None
user = None

event_ignored = ['check_run', 'check_suite', 'commit_comment', 'deployment', 'deployment_status', 'status', 'issues',
                 'installation', 'installation_repositories', 'issue_comment', 'repository_vulnerability_alert', 'star',
                 'marketplace_purchase', 'member', 'membership', 'milestone', 'organization', 'org_block', 'gollum',
                 'page_build', 'project_card', 'project_column', 'project', 'public', 'pull_request', 'fork', 'team',
                 'pull_request_review_comment', 'pull_request_review', 'repository', 'watch', 'team_add',  'label',
                 'deploy_key']

event_accepted = ['push', 'create', 'delete', 'release']


@routes.get('/ping')
async def get_handler(request):
    return web.Response(text = 'pong\n')


@routes.get('/version')
async def get_handler(request):
    return web.Response(text=version)


@routes.post('/sync')
async def get_handler(request):
    try:
        data = {'repository': {'full_name': request.rel_url.query['id']}}
    except KeyError:
        return web.Response(text='Wrong payload\n', status=400)

    return await synchronize(data)


@routes.post('/')
async def post_handler(request):
    try:
        event = request.headers['X-GitHub-Event']
    except KeyError:
        return web.HTTPBadRequest()

    if event == 'ping':
        return web.Response(text='pong\n')

    if event in event_ignored:
        return web.Response(text='event in the ignored list\n')

    if event not in event_accepted:
        error('Unknown event, %s', event)
        return web.Response(text="Unknown event" + event + '\n', status=400)

    data = (await request.read()).decode('UTF-8')

    try:
        data = loads(data)
    except ValueError:
        error('Bad request, %s', data)
        return web.HTTPBadRequest()

    return await synchronize(data)


async def synchronize(data):
    try:
        repository = data['repository']['full_name'].lower()
    except ValueError:
        error('Bad request, %s', data)
        return web.HTTPBadRequest()
    except KeyError:
        return web.Response(text='Wrong payload\n', status=400)

    if repository not in config:
        return web.Response(text='Repository not found in the config\n', status=404)

    async with config[repository]['lock']:
        trg_path = path.join(workspace + '/', repository)
        src_url = 'https://github.com/' + repository
        dst_url = 'https://' + user + ':' + token + '@github.com/' + config[repository]['target']
        cmd_list = list()
        if not path.isdir(trg_path):
            cmd_list.append('LC_ALL=en_GB git clone --mirror ' + src_url + ' ' + trg_path)
            cmd_list.append('LC_ALL=en_GB git -C ' + trg_path + ' remote set-url --push origin ' + dst_url)
        cmd_list.append('LC_ALL=en_GB git -C ' + trg_path + ' fetch -p -m origin')
        cmd_list.append('LC_ALL=en_GB git -C ' + trg_path + ' push --mirror')
        for cmd in cmd_list:
            process = await asyncio.create_subprocess_shell(cmd,
                                                            stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()

            if 'fetch' in cmd:
                stderr = stderr.decode()
                if '->' in stderr:
                    text = 'Synchronized\n'
                else:
                    text = 'Already synchronized\n'

        return web.Response(text=text)


async def target_create():

    tasks = list()

    sem = asyncio.Semaphore(5)

    async with ClientSession() as session:
        for repository in config:
            task = asyncio.ensure_future(target_create_bounded(repository, sem, session))
            tasks.append(task)

        result = await asyncio.gather(*tasks)
        if 0 in result:
            return False

    return True


async def target_create_bounded(repository, sem, session):
    async with sem:
        return await target_create_one(repository, session)


async def target_create_one(repository, session):
    target = config[repository]['target']

    url = api_url + 'repos/' + target
    try:
        async with session.get(url) as response:
            status = response.status
    except ClientConnectorError:
        error('target_create_one_check, %s, %s', target, 'connection error')
        return False
    except TimeoutError:
        error('target_create_one_check, %s, %s', target, 'timeout error')
        return False
    except Exception as exception:
        error('target_create_one_check, %s, %s', target, exception)
        return False

    if status == 404:
        data = dumps({'name': target.split('/')[1]})
        url = api_url + 'orgs/' + target.split('/')[0] + '/repos' + '?access_token=' + token
        try:
            async with session.post(url, data=data) as response:
                status = response.status
        except ClientConnectorError:
            error('target_create_one_create, %s, %s', repository, 'connection error')
            return False
        except TimeoutError:
            error('target_create_one_create, %s, %s', repository, 'timeout error')
            return False
        except Exception as exception:
            error('target_create_one_create, %s, %s', repository, exception)
            return False

        if status != 201:
            error('target_create_one_create, %s, %s %s', repository, 'status code', status)
            return False

        url = api_url + 'repos/' + target + '?access_token=' + token
        data = dumps({'description': description + source})
        try:
            async with session.patch(url, data=data) as response:
                status = response.status
        except ClientConnectorError:
            error('target_create_one_change, %s, %s', repository, 'connection error')
            return False
        except TimeoutError:
            error('target_create_one_change, %s, %s', repository, 'timeout error')
            return False
        except Exception as exception:
            error('target_create_one_change, %s, %s', repository, exception)
            return False
    if status in [200, 201]:
        return True


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('--ip', default='0.0.0.0', help='ip to use, default is 0.0.0.0')
    parser.add_argument('--port', default=8080, help='port to use, default is 8080')
    parser.add_argument('--config', default='/opt/config.json', help='path to config file, default is /opt/config.json')

    args = parser.parse_args()

    getLogger().setLevel(40)

    if 'GH_USER' in environ:
        user = environ['GH_USER']
    else:
        error('GH_USER not provided in the Env')
        exit(1)

    if 'TOKEN' in environ:
        token = environ['TOKEN']
    else:
        error('TOKEN not provided in the Env')
        exit(1)

    version_path = './version'
    if not path.isfile(version_path):
        error('Version file not found')
        exit(1)
    try:
        with open(version_path) as f:
            version_file = f.read().split('\n')
            version['build'] = version_file[0]
            version['commit'] = version_file[1]
            version = dumps(version, indent=4)
    except IndexError:
        error('Unsupported version file type')
        exit(1)

    if not path.isfile(args.config):
        error('Config file not found')
        exit(1)
    try:
        with open(args.config) as file:
            temp = loads(file.read())
    except ValueError:
        error('Unsupported config type')
        exit(1)
    try:
        for element in temp['repositories']:
            source = element['source'].lower()
            config[source] = dict()
            config[source]['target'] = element['target']
    except KeyError:
        error('Config is not correct')
        exit(1)

    if len(config) == 0:
        error('Repository list is empty')
        exit(1)

    if 'workspace' not in temp:
        workspace = '/tmp/reposynchronizer'
    else:
        workspace = temp['workspace']

    if 'description' not in temp:
        description = 'This is a mirror repo. Please fork from https://github.com/'
    else:
        description = temp['description']

    if not path.isdir(workspace):
        error('Workspace not exists')
        exit(1)

    res = asyncio.run(target_create())
    if not res:
        error("target_create returned an error, exit")
        exit(1)

    asyncio.set_event_loop_policy(EventLoopPolicy())

    for element in config:
        config[element]['lock'] = asyncio.Lock()

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, host=args.ip, port=args.port)
