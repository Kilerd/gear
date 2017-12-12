from gearpy import TaskManager, Task, Kernel
from gearpy.provider import Queue
import asyncio
import re

jandan = TaskManager(provider=Queue(), worker=5)


class TestHandler(Task):

    async def on_handle(self):

        print("fetching url {}".format(self.url))

        all_li = self.content.find_all('li', id=re.compile('^comment-'))
        for li in all_li:
            text = li.find_all('p')
            content = '\n'.join([p.text for p in text])

    async def on_result(self):
        next_page = self.content.find('a', {'title': 'Older Comments'})

        await asyncio.sleep(10)

        if next_page:
            await jandan.add("http:{}".format(next_page.get('href')))


jandan.observe(TestHandler)


async def initial():
    await jandan.add("http://jandan.net/duan")

    await jandan.start_serve()

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(initial()))

loop.close()
