"""
这个文件是用来定义任务储存介质的
"""
import abc
import aioredis
import json


class BasicBroker:
    """
    储存介质的抽象类
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    async def push(self, item):
        """
        把任务放进「准备执行队列」
        :param item: 任务内容
        :return:
        """
        pass

    @abc.abstractmethod
    async def delete(self, item, working_queue=False) -> int:
        """
        从队列中删除任务
        :param item: 任务内容
        :param working_queue: 如果是 True 的话，从「工作中队列」删除，否则，从「准备执行队列」删除
        :return: 返回删除任务的个数
        """
        pass

    @abc.abstractmethod
    async def get_task(self):
        """
        从「准备执行队列」获取一个任务，然后从队列中删除，同时把它插入「工作中队列」
        :return: 任务内容
        """
        pass

    @abc.abstractmethod
    async def restore(self) -> int:
        """
        恢复机制，用于应用重启时。把「工作中队列」的任务全部放入「准备执行队列」
        :return: 返回恢复的任务个数
        """
        pass


class RedisBroker(BasicBroker):
    """
    基于 Redis 数据库的任务储存介质
    """

    def __init__(self, name: str, host: str='localhost', port: int=6379, db: int=0):
        """
        初始化函数
        :param name: 队列名称
        :param host: 数据库地址
        :param port: 数据库端口
        :param db: 第几个数据库
        """
        self.name = name
        self.host = host
        self.port = port
        self.db = db
        self.con = None

    @property
    def __ready_queue(self):
        """
        用 「队列名称:ready」 表示「准备执行队列」
        :return:
        """
        return '{}:ready'.format(self.name)

    @property
    def __working_queue(self):
        """
        用 「队列名称: working」 表示「工作中队列」
        :return:
        """
        return '{}:working'.format(self.name)

    async def init_broker(self):
        """
        初始化函数，用于连接数据库
        :return:
        """
        # 连接数据库
        self.con = await aioredis.create_pool(
            'redis://{}:{}/{}'.format(self.host, self.port, self.db),
            minsize=5, maxsize=10
        )

    async def push(self, item):
        """
        把任务放进「准备执行队列」
        :param item: 任务内容
        :return:
        """
        await self.con.execute('LPUSH', self.__ready_queue, json.dumps(item))

    async def delete(self, item, working_queue=False) -> int:
        """
        从队列中删除任务
        :param item: 任务内容
        :param working_queue: 如果是 True 的话，从「工作中队列」删除，否则，从「准备执行队列」删除
        :return: 返回删除任务的个数
        """

        queue = self.__working_queue if working_queue else self.__ready_queue  # 判断是从哪个队列删除

        return await self.con.execute('LREM', queue, 0, json.dumps(item))  # 删除

    async def rollback(self, item):
        """
        从「工作中队列」中删除，然后把任务放入「准备执行队列」
        :param item: 任务内容
        :return:
        """
        await self.delete(item, working_queue=True)  # 删除任务
        await self.push(item)  # 插入任务

    async def restore(self):
        """
        恢复机制，用于应用重启时。把「工作中队列」的任务全部放入「准备执行队列」
        :return: 返回恢复的任务个数
        """
        while await self.con.execute('LLEN', self.__working_queue) > 0:  # 只要「工作中队列」还有任务就执行，知道队列为空
            await self.con.execute('BRPOPLPUSH', self.__working_queue, self.__ready_queue, 0)  # 执行一次 rollback 操作

        return 1

    async def get_task(self):
        """
        从「准备执行队列」获取一个任务，然后从队列中删除，同时把它插入「工作中队列」
        :return: 任务内容
        """
        task = await self.con.execute('BRPOPLPUSH', self.__ready_queue, self.__working_queue, 0)
        return json.loads(task)
