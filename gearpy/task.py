import aiohttp
import async_timeout
from bs4 import BeautifulSoup


class BasicTask:

    def __init(self, content):
        self.content = content

    async def on_task(self):
        pass

    async def on_handle(self):
        pass

    async def on_result(self):
        pass


class HTTP:

    GET = 'get'
    POST = 'post'
    PATCH = 'patch'
    PUT = 'put'
    DELETE = 'delete'


class Task(BasicTask):

    def __init__(self, content):

        self.url = content

        self.method = HTTP.GET
        self.header = {}
        self.proxy = None
        self.time_out = 0

        self.response = None
        self.content = None

    async def on_task(self):
        if self.method not in [HTTP.GET, HTTP.POST, HTTP.DELETE, HTTP.PUT, HTTP.PATCH]:
            raise ValueError('unknown http method')
        if self.time_out > 0:
            with async_timeout.timeout(self.time_out):
                async with aiohttp.ClientSession() as session:
                    async with getattr(session, self.method)(self.url) as response:
                        self.response = response
                        self.content = BeautifulSoup(await response.text(), 'lxml')
        else:
            async with aiohttp.ClientSession() as session:
                async with getattr(session, self.method)(self.url) as response:
                    self.response = response
                    self.content = BeautifulSoup(await response.text(), 'lxml')

    async def on_handle(self):
        """
        handle what you want
        :return:
        """
        pass

    async def on_result(self):
        """

        :return:
        """
        pass
