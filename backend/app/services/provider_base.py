from abc import ABC, abstractmethod

class BlockchainDataProvider(ABC):
    """
    Abstract Base Class ensuring infrastructure decoupling for Project Aegis.
    Allows easy swapping between mock datasets, enterprise RPC nodes, and public APIs.
    """
    
    @abstractmethod
    async def get_outbound_flow(self, address: str) -> list:
        pass

    @abstractmethod
    async def analyze_payload(self, tx_hash: str) -> str:
        pass