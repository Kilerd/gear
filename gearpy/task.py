import aiohttp
import async_timeout
from lxml import etree


class BasicTask:

    def __init__(self, data):
        self.data = data

    async def before(self):
        pass

    async def on_task(self):
        pass

    async def handle(self):
        pass

    async def success(self):

        pass

    async def failure(self):
        pass

class HTTP:

    GET = 'get'
    POST = 'post'
    PATCH = 'patch'
    PUT = 'put'
    DELETE = 'delete'


class Task(BasicTask):

    def __init__(self, data):

        self.data = data

        self.method = HTTP.GET
        self.headers = {}
        self.proxy = None
        self.time_out = 0

        self.response = None
        self.content = None
        self.tree = None
        self.url = None

    async def __fetch(self, session):
        if self.url:
            async with getattr(session, self.method)(self.url, proxy=self.proxy) as response:
                self.response = response
                self.content = await response.text()
                self.tree = etree.HTML(self.content)

    async def check(self):
        # print('check function with status is', self.response.status)
        return self.response.status == 200

    async def on_task(self):
        if self.method not in [HTTP.GET, HTTP.POST, HTTP.DELETE, HTTP.PUT, HTTP.PATCH]:
            raise ValueError('unknown http method')

        if self.time_out > 0:
            with async_timeout.timeout(self.time_out):
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    await self.__fetch(session)
        else:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                await self.__fetch(session)

        return await self.check()

    async def handle(self):
        """
        :return:
        """
        pass

    async def success(self):
        pass

    async def failure(self):
        pass

