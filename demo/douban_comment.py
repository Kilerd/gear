from gearpy import Manager, RedisBroker, Task
from gearpy.proxy import ProxyPool
from douban.utils import *
import motor.motor_asyncio
import json
import asyncio
import traceback


manager = Manager(broker=RedisBroker, args=('localhost', 6400, 0))  # 建立管理员实例

proxy = ProxyPool()  # 代理池实例

# 数据库连接
client = motor.motor_asyncio.AsyncIOMotorClient('localhost', 27017)
database = client['douban']


# 添加代理池任务
@manager.handle('proxy', worker=)
class ProxyTask(Task):

    def __init__(self, data):
        super().__init__(data)
        self.url = data

    async def handle(self):
        json_body = json.loads(self.content)
        for item in json_body:
            ip, port, priority = item
            proxy.add(ip, port, priority)

        return True

    async def success(self):
        await asyncio.sleep(30)
        await manager.new('proxy', 'http://localhost:4000')


# 添加电影评论任务，最大工作 5
@manager.handle('comment', worker=5)
class CommentTask(Task):

    def __init__(self, data):
        super().__init__(data)

        # 从数据库中读取出该任务的内容
        self.id = self.data['id']  # 电影ID
        self.page = self.data['page']  # 评论的页面
        self.type = self.data['type']  # 评论的类型

        self.has_next_page = True  # 是否存在下一页

    async def before(self):
        """
        任务预处理
        :return:
        """

        self.proxy = await proxy.get()  # 从代理池中捞一个代理 IP 出来

        # 伪造 HTTP 请求头，让他看起来更像一次正常人类的访问
        self.headers['Cookie'] = 'bid={}'.format(random_bid())
        self.headers['User-Agent'] = random_user_agent()
        self.headers['Accept-Language'] = 'zh-CN,zh'
        # Referer:https://movie.douban.com/explore
        self.headers['Referer'] = 'https://movie.douban.com/subject/{}/?from=showing'.format(self.id)
        # Accept-Encoding:gzip, deflate, br
        self.headers['Accept-Encoding'] = 'gzip, deflate, br'
        # Accept:*/*
        self.headers['Accept'] = '*/*'

        # HTTP 请求超时时间
        self.time_out = 3

        # 构建 访问的 HTTP URL
        self.url = 'https://movie.douban.com/subject/{}/comments?start={}&limit=20&sort={}&status=P&percent_type='.format(self.id, self.page*20, self.type)

        print('fetching comment page with id {} page {} proxy {}'.format(self.id, self.page, self.proxy))

    async def handle(self):
        """
        定义用户查询的内容
        :return:
        """
        save_num = 0  # 记录储存了多少条新评论

        # 如果访问失败则反馈任务失败
        if '检测到有异常请求' in self.content:
            return False

        # XPATH 方式读取出所有评论
        all_comment = self.tree.xpath('//*[@id="comments"]/div[@class="comment-item"]')

        # 如果有 0 条评论，那么证明没有下一页了
        if len(all_comment) == 0:
            self.has_next_page = False

        else:

            # 逐条读取评论
            for comment in all_comment:
                try:
                    # 全部都是 XPATH 的读取方式，读取你想要的内容
                    user = comment.xpath('./div[2]/h3/span[2]/a')
                    user_href = user[0].attrib['href']
                    user_name = user[0].text
                    votes = comment.xpath('./div[2]/h3/span[1]/span')[0].text

                    star = comment.xpath('./div[2]/h3/span[2]/span[2]/@class')[0]
                    star = star.split(' ')[0][7:] if 'rating' in star else 0

                    date = comment.xpath('./div[2]/h3/span[2]/span[@class="comment-time "]')[0].text.strip().strip(
                        '\n').strip()

                    content = comment.xpath('./div[2]/p')[0].text

                    # 判断是否在数据库中
                    comment_existed = await database.movies.find({'user_name': user_name, 'content': content}).count()

                    if comment_existed == 0:
                        # 如果数据库中找不到，那么插入数据库
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
                except Exception as e:
                    print('  handle function raise', e, str(e))

            print('saving {} comment from id {} page {}'.format(save_num, self.id, self.page))

        return True

    async def success(self):
        """
        任务成功时触发的函数
        :return:
        """
        proxy.feedback(self.proxy)  # 任务成功，代表刚刚用的 代理 IP 可用，则反馈给代理池
        await asyncio.sleep(3)  # 等待3秒，以免速度过快

        # 判断是否还有下一页
        if self.page <= 9:

            # 插入一个新的任务，即下一页
            await manager.new('comment', {
                'id': self.id,
                'page': self.page + 1,
                'type': self.type
            })
        if self.page == 10:
            # 如果已经是第10 页，那么重新从第 0 页开始爬
            await manager.new('comment', {
                'id': self.id,
                'page': 0,
                'type': self.type
            })


async def initial():
    await manager.init_all_broker()  # 初始化所有数据库队列

    # await manager.new('proxy', 'http://localhost:4000')
    # async for movie in database.movies.find():
    #     print(movie['mid'], movie['content'])
    #     await manager.new('comment', {
    #         'id': movie['mid'],
    #         'page': 1,
    #         'type': 'new_score'
    #     })
    #     await manager.new('comment', {
    #         'id': movie['mid'],
    #         'page': 1,
    #         'type': 'time'
    #     })

    # 执行两种任务，评论任务，代理任务
    await manager.serve(['comment', 'proxy'], restore=True)


# 启动任务
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(initial()))
loop.run_forever()
loop.close()
