from typing import Iterable, Optional, TypeVar, Generic

T = TypeVar("T")


class DownloadedImagesListNode(Generic[T]):
    def __init__(self, value: T):
        self.value = value
        self.prev: Optional["DownloadedImagesListNode[T]"] = None
        self.next: Optional["DownloadedImagesListNode[T]"] = None


class DownloadedImagesList(Generic[T]):
    def __init__(self) -> None:
        self.head: Optional[DownloadedImagesListNode[T]] = None
        self.tail: Optional[DownloadedImagesListNode[T]] = None
        self.pointer: Optional[DownloadedImagesListNode[T]] = None
        self.size = 0
        self.position_from_start = 0

    @classmethod
    def from_iterable(cls, values: Iterable[T]) -> "DownloadedImagesList[T]":
        new_list = cls()
        for value in values:
            new_list.append(value)

        return new_list

    def append(self, value: T) -> None:
        node = DownloadedImagesListNode(value)
        if not self.head:
            self.head = self.tail = node
            self.pointer = node
        else:
            assert self.tail is not None  # type safety
            self.tail.next = node
            node.prev = self.tail
            self.tail = node

        self.size += 1

    def pop_left(self) -> T:
        if not self.head:
            raise IndexError("pop from empty list")

        node = self.head
        self.head = node.next

        if self.head:
            self.head.prev = None
        else:
            self.tail = None

        if self.pointer == node:
            self.pointer = self.head
            self.position_from_start = 0
        else:
            self.position_from_start -= 1

        self.size -= 1

        return node.value

    def __len__(self) -> int:
        return self.size

    def clear(self) -> None:
        self.head = self.tail = self.pointer = None
        self.size = self.position_from_start = 0

    def move_next(self) -> None:
        if not self.pointer:
            return

        if self.pointer.next:
            self.position_from_start += 1
            self.pointer = self.pointer.next
        else:
            self.position_from_start = 0
            self.pointer = self.head

    def move_prev(self) -> None:
        if not self.pointer:
            return

        if self.pointer.prev:
            self.position_from_start -= 1
            self.pointer = self.pointer.prev
        else:
            self.position_from_start = 0
            self.pointer = self.head

    def current(self) -> Optional[T]:
        if self.pointer:
            return self.pointer.value

        return None
