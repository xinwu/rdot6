#!/bin/bash
rpm -ivh --force /root/python-networking-bigswitch-2015.3.11-1.fc25.noarch.rpm
rpm -ivh --force /root/openstack-neutron-bigswitch-agent-2015.3.11-1.fc25.noarch.rpm
rpm -ivh --force /root/openstack-neutron-bigswitch-lldp-2015.3.11-1.fc25.noarch.rpm
rpm -ivh --force /root/python-horizon-bsn-2015.3.1-1.el7.centos.noarch.rpm
rpm -ivh --force /root/ivs-3.6.0-1.el7.centos.x86_64.rpm
systemctl enable neutron-bsn-lldp.service
systemctl restart neutron-bsn-lldp.service
