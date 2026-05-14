
from .fivesim import FiveSimProvider

# Singleton instance
# In the future, this file can act as a ProviderManager that dispatches calls 
# to the appropriate provider (5sim, SMS-Activate, etc.) based on settings.

class ProviderManager:
    def __init__(self):
        self.primary_provider = FiveSimProvider()
        
    def get_provider(self):
        # Currently we only support 5sim as the primary provider
        return self.primary_provider

# Initialize manager
manager = ProviderManager()
# Expose the primary provider directly for backward compatibility or direct usage
current_provider = manager.get_provider()
