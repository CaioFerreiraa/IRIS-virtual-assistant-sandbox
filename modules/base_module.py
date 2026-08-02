from abc import ABC, abstractmethod


class BaseModule(ABC):
    call_name: str
    name: str

    @abstractmethod
    def run(self, call_name: str, payload: dict) -> dict:
        raise NotImplementedError
