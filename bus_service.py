# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com
# mail: goctaprog@gmail.com
"""service class for I/O bus operation"""

from abc import ABC, abstractmethod


class BusAdapter(ABC):
    """Proxy between I/O bus and device I/O class"""
    @abstractmethod
    def __init__(self, bus, address):
        pass

    @abstractmethod
    def read_register(self, reg_addr, bytes_count=2):
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        pass

    @abstractmethod
    def write_register(self, reg_addr, value: int, bytes_count=2, byte_order: str = "big"):
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        pass
