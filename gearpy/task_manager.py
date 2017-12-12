import asyncio


class TaskManager:

    def __init__(self, provider=None, worker=-1):

        self.__provider = provider
        self.__observer = []
        self.__worker = worker

        self._count = -1

    def observe(self, handler):
        if handler not in self.__observer:
            self.__observer.append(handler)

    async def __on_task_finish(self):
        self._count -= 1

    async def __handler(self, handler_class, item):

        handler_instance = handler_class(item)
        await handler_instance.on_task()
        await handler_instance.on_handle()
        await handler_instance.on_result()
        await self.__on_task_finish()

    async def start_serve(self):
        while True:
            if self._count >= self.__worker >= 0:
                await asyncio.sleep(0.1)
                continue

            self._count += 1
            item = await self.__provider.pull()

            for handler in self.__observer:
                asyncio.gather(self.__handler(handler, item))

    async def add(self, task):
        await self.__provider.push(task)
