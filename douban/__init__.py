import asyncio
import re
import aiohttp
import json
import logging
import aiofiles
import random

import motor.motor_asyncio

from gearpy import Queue
from gearpy import TaskManager, Task

from douban.utils import *

logging.getLogger(__name__).addHandler(logging.NullHandler())


class ProxyPool:

    def __init__(self):
        self.__pool = {}

    def add(self, ip, port, priority):

        if 'http://{}:{}'.format(ip, port) not in self.__pool:
            self.__pool['http://{}:{}'.format(ip, port)] = {
                'priority': priority,
                'unused_time': 20
            }
        else:
            self.__pool['http://{}:{}'.format(ip, port)]['priority'] = priority
            self.__pool['http://{}:{}'.format(ip, port)]['unused_time'] += priority

    async def get(self):
        is_done = False
        proxy = None

        while not is_done:
            proxies = self.__pool.items()
            proxies_sorted = sorted(list(proxies), reverse=True, key=lambda x: x[1]['unused_time'])
            if len(proxies_sorted) > 0:
                self.__pool[proxies_sorted[0][0]]['unused_time'] -= 1
                proxy = proxies_sorted[0][0]
                is_done = True

            if not is_done:
                await asyncio.sleep(1)

        return proxy

    def feedback(self, item):
        self.__pool[item]['unused_time'] += 1


proxy_pool = ProxyPool()

proxy_manager = TaskManager(provider=Queue(), worker=1)
movies = TaskManager(provider=Queue(), worker=1)
comments = TaskManager(provider=Queue(), worker=5)

client = motor.motor_asyncio.AsyncIOMotorClient('localhost', 27017)
database = client['douban']

@proxy_manager.observe
class GetProxy(Task):

    async def on_task(self):
        logging.info("getting proxy list from local...")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as r:
                json_body = json.loads(await r.text())
                for proxy in json_body:
                    ip, port, priority = proxy
                    proxy_pool.add(ip, port, priority)

    async def on_result(self):
        await asyncio.sleep(60)
        await proxy_manager.add("http://localhost:4000")


class ProxyTask(Task):

    async def on_before(self):

        self.proxy = await proxy_pool.get()


@movies.observe
class TestHandler(ProxyTask):

    def __init__(self, content):
        super().__init__(content)

        self.page = content
        self.has_next_page = True

    async def on_before(self):

        self.headers['Cookie'] = 'bid={}'.format(random_bid())
        self.headers['User-Agent'] = random_user_agent()
        self.headers['Accept-Language'] = 'zh-CN,zh'
        # Referer:https://movie.douban.com/explore
        self.headers['Referer'] = 'https://movie.douban.com/explore'
        # X-Requested-With:XMLHttpRequest
        self.headers['X-Requested-With'] = 'XMLHttpRequest'
        # Accept-Encoding:gzip, deflate, br
        self.headers['Accept-Encoding'] = 'gzip, deflate, br'
        # Accept:*/*
        self.headers['Accept'] = '*/*'

        self.time_out = 3
        self.url = 'https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit=20&page_start={}'.format(int(self.page)*20)

    async def on_handle(self):

        print("fetching movie info page {}".format(self.page))

        data_json = json.loads(self.content)
        if len(data_json['subjects']) != 0:
            for movie in data_json['subjects']:

                movie_existed = await database.movies.find({'title': movie['title']}).count()
                if movie_existed == 0:
                    print('saving movie {}'.format(movie['title']))
                    await database.movies.insert_one({
                        'mid': movie['id'],
                        'title': movie['title'],
                        'rate': movie['rate']
                    })
        else:
            self.has_next_page = False

    async def on_result(self):
        if self.has_next_page:

            proxy_pool.feedback(self.proxy)
            await asyncio.sleep(1)
            await movies.add(int(self.page) + 1)


@comments.observe
class Comment(ProxyTask):

    def __init__(self, comment):
        super().__init__(comment)

        self.id = comment['id']
        self.page = comment['page']
        self.type = comment['type']
        self.has_next_page = True

    async def on_before(self):

        # self.proxy = 'http://127.0.0.1:3128'
        self.proxy = await proxy_pool.get()

        self.headers['Cookie'] = 'bid={}'.format(random_bid())
        self.headers['User-Agent'] = random_user_agent()
        self.headers['Accept-Language'] = 'zh-CN,zh'
        # Referer:https://movie.douban.com/explore
        self.headers['Referer'] = 'https://movie.douban.com/subject/{}/?from=showing'.format(self.id)
        # Accept-Encoding:gzip, deflate, br
        self.headers['Accept-Encoding'] = 'gzip, deflate, br'
        # Accept:*/*
        self.headers['Accept'] = '*/*'

        self.time_out = 3

        self.url = 'https://movie.douban.com/subject/{}/comments?start={}&limit=20&sort=new_score&status=P&percent_type='.format(self.id, self.page*20)

        # print('fetching comment page with id {} page {} proxy {}'.format(self.id, self.page, self.proxy))

    async def on_handle(self):

        save_num = 0
        all_comment = self.tree.xpath('//*[@id="comments"]/div[@class="comment-item"]')
        if '检测到有异常请求' in self.content:
            raise ValueError()

        if len(all_comment) == 0:
            self.has_next_page = False

        else:
            for comment in all_comment:
                user = comment.xpath('./div[2]/h3/span[2]/a')
                user_href = user[0].attrib['href']
                user_name = user[0].text
                votes = comment.xpath('./div[2]/h3/span[1]/span')[0].text

                star = comment.xpath('./div[2]/h3/span[2]/span[2]/@class')[0]
                star = star.split(' ')[0][7:] if 'rating' in star else 0

                date = comment.xpath('./div[2]/h3/span[2]/span[@class="comment-time "]')[0].text.strip().strip('\n').strip()

                content = comment.xpath('./div[2]/p')[0].text

                comment_existed = await database.movies.find({'user_name': user_name, 'content': content}).count()
                if comment_existed == 0:
                    save_num += 1
                    await database.comments.insert_one({
                        'mid': self.id,
                        'user_href': user_href,
                        'user_name': user_name,
                        'votes': int(votes),
                        'star': int(star),
                        'date': date,
                        'content': content
                    })

            print('saving {} comment from id {} page {} with proxy {}'.format(save_num, self.id, self.page, self.proxy))

    async def on_result(self):
        proxy_pool.feedback(self.proxy)
        await asyncio.sleep(1)
        if self.has_next_page:
            await comments.add({
                'id': self.id,
                'page': self.page + 1,
                'type': self.type
            })



async def initial():

    proxy_manager.start_serve(['http://localhost:4000'])
    # movies.start_serve([0])
    async for movie in database.movies.find():
        await comments.add({
            'id': movie['mid'],
            'page': 0,
            'type': 'new_score'
        })
        await comments.add({
            'id': movie['mid'],
            'page': 0,
            'type': 'time'
        })

    comments.start_serve()
#
#
# loop = asyncio.get_event_loop()
# loop.run_until_complete(asyncio.gather(initial()))
# loop.run_forever()
# loop.close()
