import os
import sys
import time
import json
import random
import logging
import multiprocessing
from wsgiref.util import setup_testing_defaults
from wsgiref.simple_server import make_server


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('mockserver')


devnull = open(os.devnull, 'w')


class RedirectStdStreams(object):
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


def simple_app(environ, start_response):
    setup_testing_defaults(environ)

    status = '200 OK'
    headers = [('Content-type', 'text/plain')]

    start_response(status, headers)

    ret = ["%s: %s\n" % (key, value)
           for key, value in environ.iteritems()]
    return ret


def sitemap_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]

    start_response(status, headers)

    requested_url = environ['PATH_INFO']
    if requested_url == '/sleep':
        time.sleep(2)
        response = 'Done'
    else:
        response = sitemap_app.sitemap.get(requested_url)
    log.debug('Requested url: %s, response: %s', requested_url, response)
    try:
        ret = [json.dumps(response).encode('utf-8')]
    except Exception:
        log.exception("bla-bla")
    log.debug('Requested url: %s, ret: %s', requested_url, ret)
    return ret


def make_reponse_body(items, links):
    return {
        'items': items,
        'links': links,
    }


def make_sitemap(level=3, links_on_page=3, sitemap=None, entry='/root'):
    sitemap = sitemap if sitemap else {}
    if level == 0:
        return sitemap

    def make_entry(url, sitemap, links_on_page):
        sitemap.update({
            url: make_reponse_body(
                ['a', 'b'],
                ['%s/%s' % (url, i) for i in range(0, links_on_page)],
            )
        })

    for lev in range(0, level):
        make_entry(entry, sitemap, links_on_page)
        for child in range(0, links_on_page):
            child_url = '%s/%s' % (entry, child)
            make_entry(child_url, sitemap, links_on_page if level > 1 else 0)
            make_sitemap(level=level - 1, sitemap=sitemap, entry=child_url)

    return sitemap


class HttpServer(object):

    def __init__(self, host='localhost', port=None, app=None, sitemap=None):
        app = app or sitemap_app
        self.sitemap = sitemap or {}

        # inject sitemap to app
        app.sitemap = self.sitemap

        self.host = host
        self.port = port or (8000 + random.randint(0, 100))
        self.location = 'http://%s:%s' % (self.host, self.port)

        self.httpd = make_server(self.host, self.port, app)
        self.process = multiprocessing \
            .Process(target=self.httpd.serve_forever)

    def start(self):
        log.debug('Start http server: %s', self)
        with RedirectStdStreams(stdout=devnull, stderr=devnull):
            self.process.start()

    def stop(self):
        log.debug('Stop http server: %s', self)
        self.process.terminate()
        self.process.join()
        self.httpd.server_close()
