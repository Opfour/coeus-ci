"""Module registry."""

from coeus.modules.whois_mod import WhoisModule
from coeus.modules.dns_mod import DnsModule
from coeus.modules.headers import HeadersModule
from coeus.modules.ssl_mod import SslModule
from coeus.modules.tech import TechModule
from coeus.modules.edgar import EdgarModule
from coeus.modules.nonprofit import NonprofitModule
from coeus.modules.dba import DbaModule

ALL_MODULES = [
    WhoisModule(),
    DnsModule(),
    HeadersModule(),
    SslModule(),
    TechModule(),
    EdgarModule(),
    NonprofitModule(),
    DbaModule(),
]
