from gearpy import Manager, RedisBroker, Task
import asyncio
from random import randint

manager = Manager(broker=RedisBroker, args=('localhost', 6400, 0))


@manager.handle('comment', worker=2)
class CommentTask(Task):

    def __init__(self, data):
        self.data = data

    async def check(self):
        return True

    async def on_task(self):
        return True

    async def handle(self):

        # comment = self.find('//div').then({
        #     'user': {
        #         'href': self.find_one('./fsfd'),
        #         'name': './aaa/dfsd'
        #     },
        #     'star': './fsfsdfsfs'
        #
        # })
        await asyncio.sleep(randint(0, 3))
        print('done')
        return False

    async def success(self):
        print(self.data, 'done')


    async def failure(self):
        print(self.data, 'failure')


@manager.handle('movie', worker=1)
class MovieTask(Task):
    pass


manager.serve(['comment'], restore=True)
