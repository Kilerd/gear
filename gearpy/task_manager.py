import asyncio

from typing import Tuple, Any, Optional, Dict, List


class Manager:
    """
    任务管理员
    """

    def __init__(self, broker, args: Optional[Tuple]=None):
        """
        初始化
        :param broker: 使用哪种数据库作为任务储存介质
        :param args: 连接 broker 要用到的参数
        """

        self.broker = broker
        if args:
            self.args = args

        self.tasks: Dict[str, List[Any, Any, int, int]] = {}  # 用于储存爬虫任务类型

    def handle(self, task_name: str, worker: int = -1):
        """
        添加爬虫任务类型
        :param task_name: 爬虫名字
        :param worker: 这种任务最大同时执行任务个数
        :return: 装饰器
        """

        def decorator(task_class):

            # 储存这种爬虫任务类型
            self.tasks[task_name] = [
                self.broker(task_name, *self.args),  # 数据库连接
                task_class,  # 爬虫任务处理类
                asyncio.Semaphore(worker),  # 当前工作任务个数
                worker  # 最大工作个数
            ]

        return decorator

    async def init_all_broker(self):
        """
        初始化所有任务
        :return:
        """
        for task in self.tasks.items():
            await task[1][0].init_broker()

    async def new(self, task, data):
        """
        添加一个任务
        :param task: 任务类型
        :param data: 任务内容
        :return:
        """
        await self.tasks[task][0].push(data)  # 在该任务的数据库中插入该任务

    async def feedback(self, task, task_data, success=True):
        """
        把任务执行情况反馈给数据库
        :param task: 任务类型
        :param task_data: 任务内容
        :param success: 是否成功
        :return:
        """
        if success:

            # 成功时，把任务从 「正在工作队列」 中删除
            await self.tasks[task][0].delete(task_data, working_queue=True)
        else:

            # 失败时，把任务从「正在工作队列」中放回「准备工作队列」，具体实现 看 Broker.rollback 函数
            await self.tasks[task][0].rollback(task_data)

    async def __end_task(self, task):
        """
        任务完成时，正在执行任务 减 1
        :param task: 任务类型
        :return:
        """
        self.tasks[task][2] -= 1

    async def task_serve(self, task, task_class, task_data):
        """
        爬虫任务处理流程
        :param task: 任务类型
        :param task_class: 任务处理类
        :param task_data: 任务内容
        :return:
        """
        task_instance = task_class(task_data)  # 实例化任务处理类，同时把任务内容穿进去
        await task_instance.before()  # 执行 预处理函数
        try:
            ret = await task_instance.on_task()  # 执行 HTTP 请求
        except Exception as e:
            # 请求 HTTP 出错时，ret 设为 False，用于标记是否成功执行任务
            print('task processing raised', e, str(e))
            ret = False
        if ret:

            # 如果 HTTP 请求成功
            if await task_instance.handle():  # 执行 handle 函数，实际上时处理用户需要抓取哪些数据

                # 在抓取 用户数据时，成功就执行 success 函数
                await task_instance.success()
                await self.feedback(task, task_data)  # 反馈给数据库，任务执行成功
            else:
                # 抓取失败时，触发 failure 函数
                await task_instance.failure()
                await self.feedback(task, task_data, success=False)  # 反馈给数据库，任务失败
        else:

            # HTTP 请求失败时，也反馈给数据库，任务失败
            await self.feedback(task, task_data, success=False)

        # 任务执行个数减 1
        # await self.__end_task(task)

    async def task_list_serve(self, task, restore=False):
        """
        监听一种任务类型
        :param task: 任务类型
        :param restore: 是否把未完成的任务重新回滚进「准备工作队列」
        :return:
        """

        print('listening on list {}'.format(task))
        broker, task_class, _, worker_limited = self.tasks[task]  # 读取该种任务类型的信息
        await broker.init_broker()  # 初始化该种任务的数据库

        # 如果要恢复任务
        if restore:
            await broker.restore()

        # 死循环，读取任务
        while True:
            with (await self.tasks[task][2]):
            # while True:
            #     if not worker_limited > self.tasks[task][2] >= 0:  # 任务执行个数限制在允许范围呢
            #         await asyncio.sleep(.5)
            #         continue
            #
            #     self.tasks[task][2] += 1  # 执行任务数量加 1
                task_data = await broker.get_task()  # 从数据库读取一个任务
                # asyncio.gather(self.task_serve(task, task_class, task_data))  # 异步任务执行这个任务
                await self.task_serve(task, task_class, task_data)

    async def serve(self, tasks, restore=False):
        """
        异步启动系统
        :param tasks: 启动的任务类型
        :param restore: 是否把未完成的任务重新回滚进「准备工作队列」
        :return:
        """
        if not isinstance(tasks, list):
            tasks = [tasks]

        for task in tasks:
            if task in self.tasks:
                asyncio.gather(self.task_list_serve(task, restore))

    def serve_sync(self, tasks=None, restore=False):
        """
        同步启动爬虫系统
        :param tasks:
        :param restore:
        :return:
        """
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(self.serve(tasks, restore)))
        loop.run_forever()
        loop.close()

