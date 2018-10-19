#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import json as jsn
import socket
import threading
import http.server
import requests
import os
import sys
import subprocess
import datetime
import argparse


def check_repo_in_config(repo_param):
    for repo in config['repositories']:
        if repo['source'] == repo_param:
            return 'source'
        if repo['target'] == repo_param:
            return 'target'

    return False


def get_repo_pair_in_config(repo_param):
    for repo in config['repositories']:
        if repo['source'] == repo_param:
            return repo['target']
        if repo['target'] == repo_param:
            return repo['source']

    return False


def sync(repo_param):
    events[repo_param].acquire()
    with open(os.devnull, 'w') as f:
        path = os.path.join(config['workspace'], repo_param.split('/')[1])
        src_url = 'https://github.com/' + repo_param
        dst_url = 'https://' + user + ':' + token_github + '@github.com/' + get_repo_pair_in_config(repo_param)
        if not os.path.isdir(path):
            os.makedirs(path)
            subprocess.call(['git', 'clone', '--mirror', src_url, path], stdout=f, stderr=f)
            subprocess.call(['git', 'remote', 'set-url', '--push', 'origin', dst_url], cwd=path, stdout=f, stderr=f)
        subprocess.call(['git', 'fetch', '-p', '-m', 'origin'], cwd=path, stdout=f, stderr=f)
        subprocess.call(['git', 'push', '--mirror'], cwd=path, stdout=f, stderr=f)
    if validate_sync():
        message = {'message': 'Sync succeeded'}
        code = 200
    else:
        message = {'message': 'Sync failed'}
        code = 500

    events[repo_param].release()
    return message, code


def release(repo, body):
    data = dict()
    data['tag_name'] = body['release']['tag_name']
    data['name'] = body['release']['name']
    data['body'] = body['release']['body']
    data['draft'] = body['release']['draft']
    data['prerelease'] = body['release']['prerelease']

    data_json = jsn.dumps(data)

    url = 'https://api.github.com/repos/' + repo + '/releases?access_token=' + token_github

    response = requests.post(url, data=data_json, headers={'Content-Type': 'application/json'})

    if response.status_code in [200, 201]:
        return True
    else:
        return False


def target_create(target):
    message = dict()
    response = requests.get('https://api.github.com/repos/' + target + '?access_token=' + token_github)
    if response.status_code == 404:
        data_func = dict()
        data_func['name'] = target.split('/')[1]
        data_func = jsn.dumps(data_func)
        url = 'https://api.github.com/orgs/' + target.split('/')[0] + '/repos' + '?access_token=' + token_github
        response = requests.post(url, data=data_func, headers={'Content-Type': 'application/json'})
        if response.status_code == 201:
            message['message'] = 'Target repository has been successfully created'
            message['code'] = 201
        else:
            message['message'] = 'Target repository has not been created'
            message['code'] = 500
    else:
        message['message'] = 'Target repository already created'
        message['code'] = 200

    message['cmd'] = 'target_create'
    message['repo'] = target
    print(jsn.dumps(message, indent=2))


def validate_sync():
    return True


def parse_request_line(request_line):
    request_line = request_line.split('HTTP')[0].strip()
    method = request_line.split('/')[0].strip()
    cmd = request_line.split('/')[1].strip().split('?')[0]
    param = dict()
    if cmd in ['sync', 'change', 'config']:
        if len(request_line.split('?')) > 1:
            for element in request_line.split('?')[1].split('&'):
                if element.split('=')[0] in ['repo', 'obj', 'token']:
                    param[element.split('=')[0]] = element.split('=')[1]

    if method == 'GET' and cmd in cmd_get_rl:
        return cmd, param
    if method == 'POST' and cmd in cmd_post_rl:
        return cmd, param

    return False, None


class Handler(http.server.BaseHTTPRequestHandler):

    def reply(self, message=dict(), silent=False, code=200, cmd='', repo=''):
        self.send_response(code)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(bytes(jsn.dumps(message, indent=2) + '\n', 'utf8'))

        if not silent:
            message['code'] = code
            if self.headers.get('X-Real-IP'):
                message['ip'] = self.headers.get('X-Real-IP')
            else:
                message['ip'] = self.client_address[0]
            message['request'] = self.requestline
            message['date'] = datetime.datetime.now().isoformat()
            if cmd:
                message['cmd'] = cmd
            if repo:
                message['repo'] = repo
            if self.headers.get('X-GitHub-Delivery'):
                message['gh'] = self.headers.get('X-GitHub-Delivery')
            print(jsn.dumps(message, indent=2))
        return

    def log_message(self, format, *args):
        return

    def do_POST(self):
        # temp:
        print("debug: ", self.requestline)
        print("debug: ", self.headers.get('X-GitHub-Event'))

        cmd, param = parse_request_line(self.requestline)
        if not cmd:
            cmd = self.headers.get('X-GitHub-Event')

        if not cmd:
            message = {'message': 'Request not found'}
            self.reply(message, code=404)
            return

        if cmd not in cmd_post:
            message = {'message': 'Request not found'}
            self.reply(message, code=404, cmd=cmd)
            return

        if cmd in cmd_post_hr_ignored:
            message = {'message': 'Request in ignored list'}
            self.reply(message, cmd=cmd)
            return

        if cmd == 'ping':
            message = {'message': 'Pong'}
            self.reply(message, cmd=cmd)
            return

        if cmd not in cmd_post_rl or cmd == 'hook':
            content_length = int(self.headers.get('content-length'))

            if content_length == 0:
                message = {'message': 'Length Required'}
                self.reply(message, code=411, cmd=cmd)
                return

            body = self.rfile.read(content_length).decode('utf-8')

            try:
                body = jsn.loads(body)
            except ValueError:
                message = {'message': 'Unsupported media type'}
                self.reply(message, code=400, cmd=cmd)
                return

        status = True
        if cmd in cmd_post_rl and cmd != 'hook':
            if 'repo' in param:
                repo = param['repo']
            else:
                status = False
        elif 'repository' in body:
            if 'full_name' in body['repository']:
                repo = body['repository']['full_name']
            else:
                status = False
        else:
            status = False

        if not status:
            message = {'message': 'Bad request'}
            self.reply(message, code=400, cmd=cmd)
            return

        check = check_repo_in_config(repo)

        if not check:
            message = {'message': 'Repo not found'}
            self.reply(message, code=404, cmd=cmd, repo=repo)
            return

        if check == 'source':
            if cmd == 'release':
                status = False
                if 'action' in body:
                    if body['action'] == 'published':
                        status = release(get_repo_pair_in_config(repo), body)

                if not status:
                    message = {'message': 'Sync failed'}
                    code = 500
                else:
                    message = {'message': 'Sync succeeded'}
                    code = 200
            else:
                message, code = sync(repo)

            if cmd == 'hook':
                message = {'message': 'Please, change the webhook config as described here: https://github.com/Fiware/developmentGuidelines/blob/master/repo_webhook.mediawiki'}
                code = 500

            self.reply(message, code=code, cmd=cmd, repo=repo)
            return

        if check == 'target':
            if cmd == 'sync':
                message, code = sync(get_repo_pair_in_config(repo))
                self.reply(message, code=code, cmd=cmd, repo=repo)
                return
            else:
                message = {'message': 'Target repo, ignored'}
                self.reply(message, cmd=cmd, repo=repo)
                return

        message = {'message': 'Hook not found'}
        self.reply(message, code=404, cmd=cmd, repo=repo)
        return

    def do_GET(self):
        cmd, param = parse_request_line(self.requestline)
        if not cmd:
            message = {'message': 'Request not found'}
            self.reply(message, code=404)
            return

        if cmd == 'ping':
            message = {'message': 'Pong'}
            self.reply(message, silent=True, cmd=cmd)
            return

        if cmd == 'version':
            message = {'message': version}
            self.reply(message, cmd=cmd)
            return

        if cmd == 'config':
            status = False
            if 'token' in param:
                if param['token'] == token:
                    message = {'message': config}
                    self.reply(message, cmd=cmd)
                else:
                    status = True
            else:
                status = True

            if status:
                message = {'message': 'Access denied'}
                self.reply(message, code=401, cmd=cmd)
            return

        if cmd == 'hook':
            message = {'message': 'Please, change the webhook config as described here: https://github.com/Fiware/developmentGuidelines/blob/master/repo_webhook.mediawiki'}
            self.reply(message, cmd=cmd, code=500)
            return

class Thread(threading.Thread):
    def __init__(self, i):
        threading.Thread.__init__(self)
        self.i = i
        self.daemon = True
        self.start()

    def run(self):
        httpd = http.server.HTTPServer(address, Handler, False)

        httpd.socket = sock
        httpd.server_bind = self.server_close = lambda self: None

        httpd.serve_forever()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', dest="ip", default='0.0.0.0', help='ip address (default: 0.0.0.0)', action="store")
    parser.add_argument('--port', dest="port", default=8000, help='port (default: 8000)', action="store")
    parser.add_argument('--config', dest='config_path', default='/opt/config.json',
                        help='path to config file (default: /opt/config.json)',  action="store")
    parser.add_argument('--user', dest='user', default='Fiware-ops', help='github user (default: Fiware-ops)',
                        action="store")
    parser.add_argument('--threads', dest='threads', default=0, help='threads to start (default: len(repos)//2 + 3)',
                        action="store")
    parser.add_argument('--socks', dest='socks', default=0, help='threads to start (default: threads)',  action="store")

    args = parser.parse_args()

    ip = args.ip
    port = args.port
    user = args.user
    threads = args.threads
    socks = args.socks
    config_path = args.config_path

    if 'TOKEN_GITHUB' in os.environ:
        token_github = os.environ['TOKEN_GITHUB']
    else:
        print(jsn.dumps({'message': 'TOKEN_GITHUB not found', 'code': 500, 'cmd': 'start'}, indent=2))
        token_github = None
        sys.exit(1)

    if 'TOKEN' in os.environ:
        token = os.environ['TOKEN']
    else:
        print(jsn.dumps({'message': 'TOKEN not found', 'code': 404, 'cmd': 'start'}, indent=2))
        token = None

    if not os.path.isfile(config_path):
        print(jsn.dumps({'message': 'Config file not found', 'code': 500, 'cmd': 'start'}, indent=2))
        config_file = None
        sys.exit(1)

    try:
        with open(config_path) as f:
            config = jsn.load(f)
    except ValueError:
        print(jsn.dumps({'message': 'Unsupported config type', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    print(jsn.dumps({'message': 'Checking config and repos', 'code': 200, 'cmd': 'start'}, indent=2))

    if 'repositories' not in config:
        print(jsn.dumps({'message': 'Entity repositories not found in config', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)
    elif len(config['repositories']) == 0:
        print(jsn.dumps({'message': 'Repositories list is empty', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)
    elif 'workspace' not in config:
        print(jsn.dumps({'message': 'Workspace not defined, use defaults', 'code': 404, 'cmd': 'start'}, indent=2))
        config['workspace'] = '/tmp/reposynchronizer'
    elif not os.path.isdir(config['workspace']):
        print(jsn.dumps({'message': 'Workspace not exists', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    for el in config['repositories']:
        if 'source' in el and 'target' in el:
            target_create(el['target'])
        else:
            print(jsn.dumps({'message': 'Error found in config', 'code': 500, 'cmd': 'start'}, indent=2))
            sys.exit(1)

    if threads == 0:
        threads = len(config['repositories'])//2 + 3
    if socks == 0:
        socks = threads

    address = (ip, port)

    cmd_get_rl = ['ping', 'config', 'version', 'hook']
    cmd_post_rl = ['sync', 'hook']
    cmd_post_hr = ['ping', 'push', 'create', 'delete', 'release']
    cmd_post_hr_ignored = ['check_run', 'check_suite', 'commit_comment', 'deployment', 'deployment_status', 'status',
                           'gollum', 'installation', 'installation_repositories', 'issue_comment', 'issues', 'label',
                           'marketplace_purchase', 'member', 'membership', 'milestone', 'organization', 'org_block',
                           'page_build', 'project_card', 'project_column', 'project', 'public', 'pull_request', 'fork',
                           'pull_request_review_comment', 'pull_request_review', 'repository', 'watch', 'team_add',
                           'repository_vulnerability_alert', 'team']
    cmd_post = cmd_post_rl + cmd_post_hr + cmd_post_hr_ignored

    version_file = open(os.path.split(os.path.abspath(__file__))[0] + '/version').read().split('\n')
    version = dict()
    version['build'] = version_file[0]
    version['commit'] = version_file[1]

    events = dict()
    for el in config['repositories']:
        events[el['source']] = threading.BoundedSemaphore(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(socks)

    [Thread(i) for i in range(threads)]

    print(jsn.dumps({'message': 'Service started', 'code': 200, 'threads': threads, 'socks': socks}, indent=2))

    while True:
        time.sleep(9999)
