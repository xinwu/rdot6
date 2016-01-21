# Copyright 2014 Big Switch Networks, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from enum import Enum
import os
from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from os_net_config import impl_ifcfg
from os_net_config import objects
from os_net_config import utils
import re
from sets import Set
import subprocess
import sys

# constants for RHOSP
NET_CONF_PATH = "/etc/os-net-config/config.json"
HIERA_DIR_PATH = "/etc/puppet/hieradata"
COMPUTE_FILE_PATH = "%s/compute.yaml" % HIERA_DIR_PATH
IVS_DAEMON_ARGS = (r'''DAEMON_ARGS="--hitless --inband-vlan 4092'''
                   '''%(uplink_interfaces)s%(internal_ports)s\"''')
IVS_CONFIG_PATH = "/etc/sysconfig/ivs"
OVS_AGENT_CONFIG_PATH = "/etc/neutron/plugins/ml2/openvswitch_agent.ini"

class BCFMode(Enum):
    UNKNOWN = 0
    MODE_P_ONLY = 5
    MODE_P_V = 6

opt_ovs_group = cfg.OptGroup(name='ovs',
                    title='ovs configuration for ovs agent')
ovs_opts = [
    cfg.StrOpt('integration_bridge', default='br-int',
                help=('integration ovs bridge')),
    cfg.StrOpt('bridge_mappings', default='datacentre:br-ex',
                help=('list of <physical_network>:<bridge> tuples'))
]
cfg.CONF.register_group(opt_ovs_group)
cfg.CONF.register_opts(ovs_opts, opt_ovs_group)

LOG = log.getLogger(__name__)
DOMAIN = "neutron-bsn-lldp"
log.register_options(cfg.CONF)
log.setup(cfg.CONF, DOMAIN)


def get_bcf_mode():
    """Get bcf deployment mode.

    :returns: UNKNOWN, MODE_P_ONLY or MODE_P_V.
    """
    if not os.path.isfile(NET_CONF_PATH):
        return BCFMode.UNKNOWN

    while True:
        if os.path.isdir(HIERA_DIR_PATH):
            break
    if not os.path.isfile(COMPUTE_FILE_PATH):
        return BCFMode.MODE_P_ONLY

    try:
        json_data = open(NET_CONF_PATH).read()
        data = jsonutils.loads(json_data)
    except:
        return BCFMode.UNKNOWN
    network_config = data.get('network_config')
    for config in network_config:
        if config.get('type') != 'ovs_bridge':
            continue
        if config.get('name').lower() == 'ivs':
            return BCFMode.MODE_P_V
        else:
            return BCFMode.MODE_P_ONLY
  
    return BCFMode.UNKNOWN


def get_mac_str(network_interface):
    with open("/sys/class/net/%s/address" % network_interface) as f:
        return f.read().strip()


def get_uplinks_and_chassisid():
    """Get uplinks and chassis_id in RHOSP environment.

    :returns: a list of uplinks names and one chassis_id
        which is the first active nic's mac address.
    """
    intf_indexes = []
    while True:
        if not os.path.isfile(NET_CONF_PATH):
            time.sleep(1)
            continue
        try:
            json_data = open(NET_CONF_PATH).read()
            data = jsonutils.loads(json_data)
        except ValueError:
            time.sleep(1)
            continue
        network_config = data.get('network_config')
        for config in network_config:
            if config.get('type') != 'ovs_bridge':
                continue
            members = config.get('members')
            for member in members:
                if member.get('type') != 'ovs_bond':
                    continue
                nics = member.get('members')
                for nic in nics:
                    if nic.get('type') != 'interface':
                        continue
                    nic_name = nic.get('name')
                    indexes = map(int, re.findall(r'\d+', nic_name))
                    if len(indexes) == 1:
                        intf_indexes.append(indexes[0] - 1)
                break
            break
        break

    active_intfs = utils.ordered_active_nics()
    intf_len = len(active_intfs)
    chassis_id = "00:00:00:00:00:00"
    if len(active_intfs) != 0:
        chassis_id = get_mac_str(active_intfs[0])
    intfs = []
    for index in intf_indexes:
        if index < intf_len:
            intfs.append(active_intfs[index])
    return intfs, chassis_id


def generate_ifcfg_activate_ports():
    """Generate ifcfg and restart ports.

    :returns: an object of IfcfgNetConfig,
        a list of ivs physical uplinks,
        and a list of ivs internal ports.
    """
    provider = impl_ifcfg.IfcfgNetConfig(noop=True, root_dir='')
    intfs = []
    if os.path.exists(NET_CONF_PATH):
        try:
            json_data = open(NET_CONF_PATH).read()
            intfs = jsonutils.loads(json_data).get("network_config")
        except:
            LOG.error('Fail to load file at: %s' % NET_CONF_PATH)
            return 1
    for intf in intfs:
        obj = objects.object_from_json(intf)
        provider.add_object(obj)

    # store the route on physical nics
    route_dict = {}

    # store the ovs internal port ifcfg
    internal_port_dict = {}
    internal_ports = []

    # store uplink ifcfg
    phy_link_dict = {}
    uplinks = []

    for intf, data in provider.interface_data.iteritems():
        # ivs does not need bond
        if "bond" in intf:
            match = re.search('BOND_IFACES="(.+?)"', data)
            if match:
                uplinks = match.group(1).split()
            continue

        # if route is assigned to physical port
        if ("vlan" not in intf and "ivs" not in intf):
            route_data = provider.route_data.get(intf, '')
            route_path = provider.root_dir + impl_ifcfg.route_config_path(intf)
            route_dict[route_path] = route_data

        intf_path = provider.root_dir + impl_ifcfg.ifcfg_config_path(intf)
        # update data for internal port
        if "TYPE=OVSIntPort" in data:
            # delete all lines starts with OVS_
            d = re.sub("OVS_.*?\n", '', data, flags=re.DOTALL)
            # replace all ovs with ivs
            d = re.sub("ovs", 'ivs', d, flags=re.DOTALL)
            # replace all OVS with IVS
            d = re.sub("OVS", 'IVS', d, flags=re.DOTALL)
            internal_port_dict[intf_path] = d
            internal_ports.append(intf)
        else: # update data for physical port
            phy_link_dict[intf_path] = data

    # make sure noop is turned off for ifdown and ifup
    provider.noop = False

    # write route
    for location, data in route_dict.iteritems():
        provider.write_config(location, data)

    # write internal port config
    for location, data in internal_port_dict.iteritems():
        provider.write_config(location, data)

    # write physical ports config, restart uplinks
    for uplink in uplinks:
        provider.ifdown(uplink)
    for location, data in phy_link_dict.iteritems():
        provider.write_config(location, data)
    for uplink in uplinks:
        provider.ifup(uplink)

    LOG.info("IVS uplinks: %s" % ','.join(uplinks))
    LOG.info("IVS internal_ports %s" % ','.join(internal_ports))
    return provider, uplinks, internal_ports


def config_reload_ivs():
    """Configure and reload ivs with uplinks and internal ports.

    """
    provider, uplinks, internal_ports = generate_ifcfg_activate_ports()

    # -u p1p1 -u p1p2
    uplink_str_array = []
    for uplink in uplinks:
        uplink_str_array.append(' -u ')
        uplink_str_array.append(uplink)
    uplink_str = ''.join(uplink_str_array)

    # --internal-port=vlan201 --internal-port=vlan202
    internal_port_str_array = []
    for internal_port in internal_ports:
        internal_port_str_array.append(' --internal-port=')
        internal_port_str_array.append(internal_port)
    internal_port_str = ''.join(internal_port_str_array)

    # generate ivs configuration
    ivs_daemon_args = IVS_DAEMON_ARGS % {
        'internal_ports': uplink_str,
        'uplink_interfaces': internal_port_str}

    # read ivs configure file
    with open(IVS_CONFIG_PATH, "r") as f:
        existing_args = f.read()

    # don't do anything if ivs config remains the same
    if ivs_daemon_args == existing_args:
        return

    # write new config to ivs config file
    with open(IVS_CONFIG_PATH, "w") as f:
        f.write(ivs_daemon_args)

    # stop and disable neutron-openvswitch-agent
    subprocess.call("systemctl disable neutron-openvswitch-agent",
                    shell=True)
    subprocess.call("systemctl stop neutron-openvswitch-agent",
                    shell=True)

    # start neutron-bsn-agent
    subprocess.call("systemctl restart neutron-bsn-agent",
                    shell=True)

    # delete br-int
    cfg.CONF(default_config_files=[OVS_AGENT_CONFIG_PATH])
    br_int = cfg.CONF.ovs.integration_bridge
    subprocess.call("ovs-vsctl del-br %s" % br_int, shell=True)

    # delete other bridges
    br_map = cfg.CONF.ovs.bridge_mappings.split(',')
    for m in br_map:
        br = m.split(':')[1]
        subprocess.call("ovs-vsctl del-br %s" % br, shell=True)

    # restart ivs, assign ip to internal ports
    subprocess.call("rm -f /etc/sysconfig/network-scripts/ifcfg-ivs", shell=True)
    subprocess.call("ovs-vsctl del-br ivs", shell=True)
    subprocess.call("systemctl restart ivs", shell=True)
    for internal_port in internal_ports:
        provider.ifup(internal_port)
