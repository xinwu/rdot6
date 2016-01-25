#!/bin/bash
# virt-customize -a overcloud-full.qcow2 --firstboot install_bigswitch_packages.sh
rpm -ivh --force /root/python-networking-bigswitch.rpm
rpm -ivh --force /root/openstack-neutron-bigswitch-lldp.rpm
rpm -ivh --force /root/openstack-neutron-bigswitch-agent.rpm
