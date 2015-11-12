import time
import json
import random
import logging

try:
    from io import StringIO
except Exception:
    from StringIO import StringIO

from nose import SkipTest
from nose.tools import assert_equal, assert_set_equal

from pomp.core.base import BaseDownloadWorker
from pomp.core.engine import Pomp
from pomp.contrib.urllibtools import (
    UrllibHttpRequest, UrllibHttpResponse, UrllibAdapterMiddleware,
)
from pomp.core.utils import PY3

try:
    from pomp.contrib.concurrenttools import (
        ConcurrentDownloader, ConcurrentUrllibDownloader,
    )
except ImportError:
    raise SkipTest('concurrent future not available')

from tools import DummyCrawler
from tools import RequestResponseMiddleware, CollectRequestResponseMiddleware
from mockserver import HttpServer, make_sitemap

logging.basicConfig(level=logging.DEBUG)


log = logging.getLogger(__name__)


class MockedDownloadWorker(BaseDownloadWorker):
    sitemap = make_sitemap(level=2, links_on_page=2)

    def get_one(self, request):
        time.sleep(random.uniform(0.3, 0.6))
        key = request.url.replace('http://localhost', '')
        res = self.sitemap.get(key)
        if PY3:
            return UrllibHttpResponse(request, StringIO(json.dumps(res)))
        else:
            return UrllibHttpResponse(
                request, StringIO(unicode(json.dumps(res)))  # noqa for unicode
            )


class MockedDownloadWorkerWithException(BaseDownloadWorker):
    def get_one(self, request):
        raise Exception('some thing wrong in request processing')


class TestContribConcurrent(object):

    def test_concurrent_downloader(self):
        req_resp_midlleware = RequestResponseMiddleware(
            prefix_url='http://localhost',
            request_factory=UrllibHttpRequest,
        )

        collect_middleware = CollectRequestResponseMiddleware()

        downloader = ConcurrentDownloader(
            pool_size=5,
            worker_class=MockedDownloadWorker,
            worker_kwargs=None,
            middlewares=(collect_middleware,)
        )
        downloader.middlewares.insert(0, req_resp_midlleware)

        pomp = Pomp(
            downloader=downloader,
            pipelines=[],
        )

        class Crawler(DummyCrawler):
            ENTRY_REQUESTS = '/root'

        pomp.pump(Crawler())

        assert_set_equal(
            set([r.url.replace('http://localhost', '')
                for r in collect_middleware.requests]),
            set(MockedDownloadWorker.sitemap.keys())
        )

    def test_exception_on_worker(self):
        req_resp_midlleware = RequestResponseMiddleware(
            prefix_url='http://localhost',
            request_factory=UrllibHttpRequest,
        )

        collect_middleware = CollectRequestResponseMiddleware()

        downloader = ConcurrentDownloader(
            pool_size=5,
            worker_class=MockedDownloadWorkerWithException,
            worker_kwargs=None,
            middlewares=(collect_middleware,)
        )
        downloader.middlewares.insert(0, req_resp_midlleware)

        pomp = Pomp(
            downloader=downloader,
            pipelines=[],
        )

        class Crawler(DummyCrawler):
            ENTRY_REQUESTS = '/root'

        pomp.pump(Crawler())

        assert_equal(len(collect_middleware.requests), 1)
        assert_equal(len(collect_middleware.exceptions), 1)


class TestContribConcurrentUrllib(object):

    @classmethod
    def setupClass(cls):
        cls.httpd = HttpServer(sitemap=make_sitemap(level=2, links_on_page=2))
        cls.httpd.start()

    @classmethod
    def teardownClass(cls):
        cls.httpd.stop()

    def test_concurrent_urllib_downloader(self):
        req_resp_midlleware = RequestResponseMiddleware(
            prefix_url=self.httpd.location,
            request_factory=lambda x: x,
        )

        collect_middleware = CollectRequestResponseMiddleware()

        downloader = ConcurrentUrllibDownloader(
            middlewares=[UrllibAdapterMiddleware(), collect_middleware]
        )

        downloader.middlewares.insert(0, req_resp_midlleware)

        pomp = Pomp(
            downloader=downloader,
            pipelines=[],
        )

        class Crawler(DummyCrawler):
            ENTRY_REQUESTS = '/root'

        pomp.pump(Crawler())

        assert_set_equal(
            set([r.url.replace(self.httpd.location, '')
                for r in collect_middleware.requests]),
            set(self.httpd.sitemap.keys())
        )
