from app.connectors.adapters import HttpConnector, MockConnector, VkApiConnector
from app.connectors.base import BaseConnector
from app.models import Account, Platform, SourceMode


def create_connector(account: Account) -> BaseConnector:
    if account.source_mode == SourceMode.MOCK:
        return MockConnector(account)
    if account.source_mode == SourceMode.HTTP:
        # VK can run directly against official VK API when base URL is not set.
        if account.platform == Platform.VK and not account.api_base_url:
            return VkApiConnector(account)
        return HttpConnector(account)
    raise ValueError(f"Unsupported source mode: {account.source_mode}")
