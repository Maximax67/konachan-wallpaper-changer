from typing import List, TypeVar, Generic

T = TypeVar("T")


class FixedSizeQueue(Generic[T]):

    def __init__(self, items: List[T]):
        self.buffer: List[T] = items
        self.size: int = len(items)
        self.count: int = len(items)
        self.start: int = 0

    def enqueue(self, item: T) -> None:
        if self.count == self.size:
            raise OverflowError("Queue is full")

        end = (self.start + self.count) % self.size
        self.buffer[end] = item
        self.count += 1

    def dequeue(self) -> T:
        if self.count == 0:
            raise IndexError("Queue is empty")

        item = self.buffer[self.start]
        self.start = (self.start + 1) % self.size
        self.count -= 1

        return item
