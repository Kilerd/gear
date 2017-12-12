import asyncio


class Queue(asyncio.Queue):

    async def push(self, item):

        await self.put(item)

    async def pull(self):

        return await self.get()
