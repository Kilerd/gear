import asyncio


class ProxyPool:
    """
    简易代理池
    """

    def __init__(self):
        """
        初始化
        """
        self.__pool = {}  # 把池的内容设置为空

    def add(self, ip, port, priority):
        """
        添加一个代理 IP
        :param ip: IP 地址
        :param port: IP 端口
        :param priority: 权重，越高越好
        :return:
        """
        # 判断代理池中有没有该 IP
        if 'http://{}:{}'.format(ip, port) not in self.__pool:

            # 若不存在，添加进 IP 代理池
            self.__pool['http://{}:{}'.format(ip, port)] = {
                'priority': priority,
                'unused_time': 20  # 设置可使用次数为 20 次
            }
        else:

            # 若存在，则更新数据
            self.__pool['http://{}:{}'.format(ip, port)]['priority'] = priority  # 重制权重
            self.__pool['http://{}:{}'.format(ip, port)]['unused_time'] += priority  # 添加可使用次数

    async def get(self):
        """
        从代理池中读取一个 IP
        :return:
        """
        is_done = False
        proxy = None

        while not is_done:
            proxies = self.__pool.items()  # 获取所有 IP
            proxies_sorted = sorted(list(proxies), reverse=True, key=lambda x: x[1]['unused_time'])  # 根据「可使用次数」排序
            if len(proxies_sorted) > 0:
                # 读取出最高次数的IP
                self.__pool[proxies_sorted[0][0]]['unused_time'] -= 1  # 「可使用次数」减 1
                proxy = proxies_sorted[0][0]
                is_done = True

            if not is_done:
                await asyncio.sleep(1)  # 代理池为空时，等待1秒后重新读取

        return proxy

    def feedback(self, item):
        """
        反馈机制，用于优质IP的反馈。让优质IP 可以使用更多次数
        :param item: 代理 IP 地址
        :return:
        """
        self.__pool[item]['unused_time'] += 1  # 「可使用次数」 加 1
