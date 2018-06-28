from gearpy import Manager, RedisBroker, Task
from gearpy.task import BasicTask
from gearpy.proxy import ProxyPool
import motor.motor_asyncio
import json
import asyncio
import random



manager = Manager(broker=RedisBroker, args=('localhost', 6400, 0))  # 建立管理员实例



@manager.handle('1', worker=10)
class TestTask(BasicTask):


    async def on_task(self):
        return True

    async def handle(self):
        print('task 1 get data {}'.format(self.data))
        return True


    async def success(self):
        # print('new task')
        # await manager.new('2', self.data)
        #
        await asyncio.sleep(random.randint(0, 2))
        for _ in range(random.randint(1, 5)):
            await manager.new('1', random.randint(1, 5))
        # print('end new task')


@manager.handle('2', worker=2)
class TestTask(BasicTask):

    async def on_task(self):
        return True

    async def handle(self):
        print('task 2 get data {}'.format(self.data))
        return True

    async def success(self):
        pass

manager.serve_sync(tasks=['1', '2'], restore=True)
