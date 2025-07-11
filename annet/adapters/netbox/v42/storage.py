import ssl
from typing import Optional

from adaptix import P
from adaptix.conversion import get_converter, link, link_constant, link_function
from annetbox.v42 import client_sync
from annetbox.v42 import models as api_models

from annet.adapters.netbox.common.adapter import (
    NetboxAdapter,
    get_connect_details,
    get_device_breed,
    get_device_hw,
)
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.adapters.netbox.v42.models import (
    InterfaceV42,
    IpAddressV42,
    NetboxDeviceV42,
    PrefixV42,
    Vlan,
    Vrf,
)
from annet.storage import Storage


class NetboxV42Adapter(NetboxAdapter[NetboxDeviceV42, InterfaceV42, IpAddressV42, PrefixV42]):
    def __init__(
        self,
        storage: Storage,
        url: str,
        token: str,
        ssl_context: ssl.SSLContext | None,
        threads: int,
    ):
        self.netbox = client_sync.NetboxV42(url=url, token=token, ssl_context=ssl_context, threads=threads)
        self.convert_device = get_converter(
            api_models.Device,
            NetboxDeviceV42,
            recipe=[
                link_function(get_device_breed, P[NetboxDeviceV42].breed),
                link_function(get_device_hw, P[NetboxDeviceV42].hw),
                link_function(get_connect_details, P[NetboxDeviceV42].connect_details),
                link_constant(P[NetboxDeviceV42].interfaces, factory=list),
                link_constant(P[NetboxDeviceV42].storage, value=storage),
                link(P[api_models.Device].name, P[NetboxDeviceV42].hostname),
                link(P[api_models.Device].name, P[NetboxDeviceV42].fqdn),
            ],
        )
        self.convert_interfaces = get_converter(
            list[api_models.Interface],
            list[InterfaceV42],
            recipe=[
                link_constant(P[InterfaceV42].ip_addresses, factory=list),
                link_constant(P[InterfaceV42].lag_min_links, value=None),
            ],
        )
        self.convert_ip_addresses = get_converter(
            list[api_models.IpAddress],
            list[IpAddressV42],
            recipe=[
                link_constant(P[IpAddressV42].prefix, value=None),
            ],
        )
        self.convert_ip_prefixes = get_converter(
            list[api_models.Prefix],
            list[PrefixV42],
        )

    def list_all_fqdns(self) -> list[str]:
        return [d.name for d in self.netbox.dcim_all_devices_brief().results]

    def list_devices(self, query: dict[str, list[str]]) -> list[NetboxDeviceV42]:
        return [self.convert_device(dev) for dev in self.netbox.dcim_all_devices(**query).results]

    def get_device(self, device_id: int) -> NetboxDeviceV42:
        return self.convert_device(self.netbox.dcim_device(device_id))

    def list_interfaces_by_devices(self, device_ids: list[int]) -> list[InterfaceV42]:
        interface_response = self.netbox.dcim_all_interfaces(device_id=device_ids)
        interfaces = interface_response.results
        return self.convert_interfaces(interfaces)

    def list_interfaces(self, ids: list[int]) -> list[InterfaceV42]:
        return self.convert_interfaces(self.netbox.dcim_all_interfaces(id=ids).results)

    def list_ipaddr_by_ifaces(self, iface_ids: list[int]) -> list[IpAddressV42]:
        return self.convert_ip_addresses(self.netbox.ipam_all_ip_addresses(interface_id=iface_ids).results)

    def list_ipprefixes(self, prefixes: list[str]) -> list[PrefixV42]:
        return self.convert_ip_prefixes(self.netbox.ipam_all_prefixes(prefix=prefixes).results)

    def list_all_vrfs(self) -> list[Vrf]:
        return self.netbox.ipam_all_vrfs().results

    def list_all_vlans(self) -> list[Vlan]:
        return self.netbox.ipam_all_vlans().results


class NetboxStorageV42(BaseNetboxStorage[NetboxDeviceV42, InterfaceV42, IpAddressV42, PrefixV42]):
    netbox: NetboxV42Adapter

    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        super().__init__(opts)
        self._all_vlans: list[Vlan] | None = None
        self._all_vrfs: list[Vrf] | None = None

    def _init_adapter(
        self,
        url: str,
        token: str,
        ssl_context: ssl.SSLContext | None,
        threads: int,
    ) -> NetboxAdapter[NetboxDeviceV42, InterfaceV42, IpAddressV42, PrefixV42]:
        return NetboxV42Adapter(self, url, token, ssl_context, threads)

    def resolve_all_vlans(self) -> list[Vlan]:
        if self._all_vlans is None:
            self._all_vlans = self.netbox.list_all_vlans()
        return self._all_vlans

    def resolve_all_vrfs(self) -> list[Vrf]:
        if self._all_vrfs is None:
            self._all_vrfs = self.netbox.list_all_vrfs()
        return self._all_vrfs
