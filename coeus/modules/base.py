"""Abstract base class for all Coeus intelligence modules."""

from abc import ABC, abstractmethod
from coeus.models import ModuleResult


class BaseModule(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'whois', 'dns'."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description."""

    @property
    def requires_api_key(self) -> bool:
        return False

    @abstractmethod
    async def execute(self, target: str, context: dict) -> ModuleResult:
        """Run the module against target (a domain name).

        context carries data from previously completed modules
        (e.g., company name from WHOIS for use by EDGAR).

        Must not raise -- return _fail() on error.
        """

    def _ok(self, data: dict, findings=None, scores=None) -> ModuleResult:
        return ModuleResult(
            module_name=self.name,
            success=True,
            data=data,
            findings=findings or [],
            scores=scores or [],
        )

    def _fail(self, error: str) -> ModuleResult:
        return ModuleResult(module_name=self.name, success=False, error=error)
