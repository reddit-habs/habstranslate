from collections import deque


class LRUContext:

    def __init__(self, path, size=100):
        self._path = path
        self._set = LRUSet(size)
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._set.add(line.strip())
        except FileNotFoundError:
            pass

    def __enter__(self):
        return self._set

    def __exit__(self, *args):
        with open(self._path, 'w') as f:
            for item in self._set.items():
                f.write(item)
                f.write("\n")


class LRUSet:

    def __init__(self, size=100):
        self._size = size
        self._queue = deque()
        self._set = set()

    def __len__(self):
        return len(self._queue)

    def add(self, item):
        self._queue.append(item)
        self._set.add(item)
        if len(self._queue) > self._size:
            item = self._queue.popleft()
            self._set.remove(item)

    def has(self, item):
        return item in self._set

    def items(self):
        for item in self._queue:
            yield item
