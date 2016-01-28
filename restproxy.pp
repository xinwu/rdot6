#
# Set config file parameters for connecting Neutron server to Big
# Switch controllers.
#
# === Parameters
#
# [*servers*]
# Comma-separated list of Big Switch controllers.
# The format is "IP:port,IP:port".
#
# [*server_auth*]
# Credentials for the Big Switch controllers.
# The format is "username:password".
#
# [*auto_sync_on_failure*]
# (optional) When a failover happens in active/passive Big Switch
# controllers, resynchronize with the new master server. Defaults to
# true.
#
# [*consistency_interval*]
# (optional) Interval of a keepalive message sent from Neutron server
# to a Big Switch controller. Defaults to 60.
#
# [*neutron_id*]
# (optional) Unique identifier of the Neutron instance for the Big
# Switch controller. Defaults to 'neutron'.
#
# [*server_ssl*]
# (optional) Whether Neutron should use SSL to talk to the Big Switch
# controllers. Defaults to true.
#
# [*ssl_cert_directory*]
# (optional) Directory where Big Switch controller certificate will be
# stored. Defaults to '/var/lib/neutron'.
#
# [*auth_tenant*]
# (optional) The tenant of the auth user
# Defaults to service
#
# [*auth_password*]
# (optional) The password to use for authentication (keystone)
# Defaults to false.
#
# [*auth_user*]
# (optional) The name of the auth user
# Defaults to neutron
#
# [*auth_url*]
# (optional) Complete public Identity API endpoint.
# Defaults to: false
#
# To make BCF3.5.1 work with RHOSP7.2
# /usr/share/openstack-puppet/modules/neutron/manifests/plugins/ml2/bigswitch/restproxy.pp
# replace above file with this file on both undercloud node
# and overcloud qcow2 image
#
class neutron::plugins::ml2::bigswitch::restproxy (
  $servers,
  $server_auth,

  $auto_sync_on_failure = true,
  $consistency_interval = 60,
  $neutron_id           = 'neutron',
  $server_ssl           = true,
  $ssl_cert_directory   = '/var/lib/neutron',

  $auth_tenant          = 'service',
  $auth_password        = false,
  $auth_user            = 'neutron',
  $auth_url             = false,
) {
  require ::neutron::plugins::ml2::bigswitch

  neutron_plugin_ml2 {
    'restproxy/servers'               : value => $servers;
    'restproxy/server_auth'           : value => $server_auth;

    'restproxy/auto_sync_on_failure'  : value => $auto_sync_on_failure;
    'restproxy/consistency_interval'  : value => $consistency_interval;
    'restproxy/neutron_id'            : value => $neutron_id;
    'restproxy/server_ssl'            : value => $server_ssl;
    'restproxy/ssl_cert_directory'    : value => $ssl_cert_directory;

    'restproxy/auth_tenant'           : value => hiera('neutron::server::auth_tenant', $auth_tenant);
    'restproxy/auth_password'         : value => hiera('neutron::server::auth_password', $auth_password);
    'restproxy/auth_user'             : value => hiera('nova::network::neutron::neutron_admin_username', $auth_user);
    'restproxy/auth_url'              : value => hiera('neutron::server::auth_uri', $auth_url);
  }
}
