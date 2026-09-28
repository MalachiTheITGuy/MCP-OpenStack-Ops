"""
OpenStack Network (Neutron) Service Functions

This module contains functions for managing networks, subnets, routers,
security groups, floating IPs, and other networking components.
"""

import logging
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


def get_network_details(network_name: str = "all") -> List[Dict[str, Any]]:
    """
    Get detailed information about networks in current project.
    
    Args:
        network_name: Name of specific network or "all" for all networks
    
    Returns:
        List of network dictionaries with detailed information for current project
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection, get_current_project_id, validate_resource_ownership
        conn = get_openstack_connection()
        current_project_id = get_current_project_id()
        
        networks = []
        
        if network_name.lower() == "all":
            for network in conn.network.networks():
                # Get project ID first
                network_project = getattr(network, 'project_id', None) or getattr(network, 'tenant_id', None)
                
                # Enhanced project validation with utility functions
                if (validate_resource_ownership(network, "Network") or 
                    getattr(network, 'is_shared', False) or 
                    getattr(network, 'is_router_external', False)):  # Include shared and external networks
                    
                    # Get subnets for this network with project validation
                    subnets = []
                    for subnet in conn.network.subnets():
                        if getattr(subnet, 'network_id', None) == network.id:
                            # Enhanced validation using utility functions
                            if validate_resource_ownership(subnet, "Subnet"):
                                subnets.append({
                                    'id': subnet.id,
                                    'name': getattr(subnet, 'name', 'unnamed'),
                                    'cidr': getattr(subnet, 'cidr', 'unknown'),
                                    'ip_version': getattr(subnet, 'ip_version', 4),
                                    'gateway_ip': getattr(subnet, 'gateway_ip', None),
                                    'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False)
                                })

                    networks.append({
                        'id': network.id,
                        'name': getattr(network, 'name', 'unnamed'),
                        'status': getattr(network, 'status', 'unknown'),
                        'admin_state_up': getattr(network, 'is_admin_state_up', True),
                        'shared': getattr(network, 'is_shared', False),
                        'external': getattr(network, 'is_router_external', False),
                        'provider_network_type': getattr(network, 'provider_network_type', None),
                        'provider_physical_network': getattr(network, 'provider_physical_network', None),
                        'provider_segmentation_id': getattr(network, 'provider_segmentation_id', None),
                        'mtu': getattr(network, 'mtu', 1500),
                        'tenant_id': getattr(network, 'tenant_id', 'unknown'),
                        'project_id': network_project,
                        'created_at': str(getattr(network, 'created_at', 'unknown')),
                        'updated_at': str(getattr(network, 'updated_at', 'unknown')),
                        'subnets': subnets,
                        'subnet_count': len(subnets)
                    })
        else:
            # Get specific network
            for network in conn.network.networks():
                if getattr(network, 'name', '') == network_name or network.id == network_name:
                    # Check if network is accessible by current project
                    network_project = getattr(network, 'project_id', None) or getattr(network, 'tenant_id', None)
                    if (network_project == current_project_id or 
                        getattr(network, 'is_shared', False) or 
                        getattr(network, 'is_router_external', False)):
                        
                        # Get subnets for this network
                        subnets = []
                        for subnet in conn.network.subnets():
                            if getattr(subnet, 'network_id', None) == network.id:
                                subnet_project = getattr(subnet, 'project_id', None) or getattr(subnet, 'tenant_id', None)
                                if subnet_project == current_project_id:
                                    subnets.append({
                                        'id': subnet.id,
                                        'name': getattr(subnet, 'name', 'unnamed'),
                                        'cidr': getattr(subnet, 'cidr', 'unknown'),
                                        'ip_version': getattr(subnet, 'ip_version', 4),
                                        'gateway_ip': getattr(subnet, 'gateway_ip', None),
                                        'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False),
                                        'dns_nameservers': getattr(subnet, 'dns_nameservers', []),
                                        'allocation_pools': getattr(subnet, 'allocation_pools', [])
                                    })
                        
                        networks.append({
                            'id': network.id,
                            'name': getattr(network, 'name', 'unnamed'),
                            'status': getattr(network, 'status', 'unknown'),
                            'admin_state_up': getattr(network, 'is_admin_state_up', True),
                            'shared': getattr(network, 'is_shared', False),
                            'external': getattr(network, 'is_router_external', False),
                            'provider_network_type': getattr(network, 'provider_network_type', None),
                            'provider_physical_network': getattr(network, 'provider_physical_network', None),
                            'provider_segmentation_id': getattr(network, 'provider_segmentation_id', None),
                            'mtu': getattr(network, 'mtu', 1500),
                            'tenant_id': getattr(network, 'tenant_id', 'unknown'),
                            'project_id': network_project,
                            'created_at': str(getattr(network, 'created_at', 'unknown')),
                            'updated_at': str(getattr(network, 'updated_at', 'unknown')),
                            'subnets': subnets,
                            'subnet_count': len(subnets)
                        })
                        break
        
        return networks
        
    except Exception as e:
        logger.error(f"Failed to get network details: {e}")
        return [
            {
                'id': 'net-1', 'name': 'demo-network', 'status': 'ACTIVE',
                'admin_state_up': True, 'shared': False, 'external': False,
                'subnets': [], 'error': str(e)
            }
        ]


def set_networks(action: str, network_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage networks (create, delete, update, list).
    
    Args:
        action: Action to perform (create, delete, update, list)
        network_name: Name of the network (required for create/delete/update)
        **kwargs: Additional parameters
    
    Returns:
        Result of the network operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import (
            find_resource_by_name_or_id,
            get_openstack_connection,
        )
        conn = get_openstack_connection()
        
        if action.lower() == 'create':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name is required for create action'
                }
            
            # Network creation parameters
            create_params = {
                'name': network_name,
                'admin_state_up': kwargs.get('admin_state_up', True)
            }
            
            # Optional parameters
            if kwargs.get('description'):
                create_params['description'] = kwargs['description']
            if kwargs.get('shared') is not None:
                create_params['is_shared'] = kwargs['shared']
            if kwargs.get('external') is not None:
                create_params['is_router_external'] = kwargs['external']
            if kwargs.get('provider_network_type'):
                create_params['provider_network_type'] = kwargs['provider_network_type']
            if kwargs.get('provider_physical_network'):
                create_params['provider_physical_network'] = kwargs['provider_physical_network']
            if kwargs.get('provider_segmentation_id'):
                create_params['provider_segmentation_id'] = kwargs['provider_segmentation_id']
            if kwargs.get('mtu'):
                create_params['mtu'] = kwargs['mtu']
            
            network = conn.network.create_network(**create_params)
            return {
                'success': True,
                'message': f'Network "{network_name}" created successfully',
                'network': {
                    'id': network.id,
                    'name': network.name,
                    'status': network.status,
                    'admin_state_up': network.is_admin_state_up
                }
            }
            
        elif action.lower() == 'delete':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name or ID is required for delete action'
                }
            
            # Find the network using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id, get_openstack_connection
            conn = get_openstack_connection()
            
            network = find_resource_by_name_or_id(
                conn.network.networks(), 
                network_name, 
                "Network"
            )

            if not network:
                return {
                    'success': False,
                    'message': f'Network "{network_name}" not found or not accessible in current project'
                }

            conn.network.delete_network(network)
            return {
                'success': True,
                'message': f'Network "{network_name}" deleted successfully'
            }
            
        elif action.lower() == 'update':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name or ID is required for update action'
                }
            
            # Use the project-scoped helper so update cannot reach outside the
            # current project, matching this function's own delete branch.
            network = find_resource_by_name_or_id(
                conn.network.networks(), network_name, 'network'
            )
            
            if not network:
                return {
                    'success': False,
                    'message': f'Network "{network_name}" not found'
                }
            
            # Update parameters
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('admin_state_up') is not None:
                update_params['admin_state_up'] = kwargs['admin_state_up']
            if kwargs.get('shared') is not None:
                update_params['is_shared'] = kwargs['shared']
            if kwargs.get('mtu'):
                update_params['mtu'] = kwargs['mtu']
            # These were unreachable: a network could not be renamed, and its
            # QoS policy, port-security setting or DNS domain could never change.
            if kwargs.get('name'):
                update_params['name'] = kwargs['name']
            if kwargs.get('qos_policy_id') is not None:
                update_params['qos_policy_id'] = kwargs['qos_policy_id'] or None
            if kwargs.get('port_security_enabled') is not None:
                update_params['is_port_security_enabled'] = kwargs['port_security_enabled']
            if kwargs.get('dns_domain') is not None:
                update_params['dns_domain'] = kwargs['dns_domain']
            
            if update_params:
                updated_network = conn.network.update_network(network, **update_params)
                return {
                    'success': True,
                    'message': f'Network "{network_name}" updated successfully',
                    'network': {
                        'id': updated_network.id,
                        'name': updated_network.name,
                        'status': updated_network.status,
                        'admin_state_up': updated_network.is_admin_state_up
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
        
        elif action.lower() == 'list':
            # Use existing get_network_details function
            return get_network_details("all")
            
        else:
            return {
                'success': False,
                'message': f'Unsupported action: {action}. Supported actions: create, delete, update, list'
            }
    
    except Exception as e:
        logger.error(f"Network management failed: {e}")
        return {
            'success': False,
            'message': f'Network management failed: {str(e)}'
        }


def get_security_groups() -> List[Dict[str, Any]]:
    """
    Get list of security groups with rules for current project.
    
    Returns:
        List of security group dictionaries for current project
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        current_project_id = conn.current_project_id
        security_groups = []
        
        for sg in conn.network.security_groups():
            # Filter by current project
            sg_project_id = getattr(sg, 'project_id', None) or getattr(sg, 'tenant_id', None)
            if sg_project_id == current_project_id:
                rules = []
                for rule in getattr(sg, 'security_group_rules', []):
                    rules.append({
                        'id': rule.get('id', 'unknown'),
                        'direction': rule.get('direction', 'unknown'),
                        'protocol': rule.get('protocol', 'any'),
                        'port_range_min': rule.get('port_range_min'),
                        'port_range_max': rule.get('port_range_max'),
                        'remote_ip_prefix': rule.get('remote_ip_prefix'),
                        'remote_group_id': rule.get('remote_group_id'),
                        'ethertype': rule.get('ethertype', 'IPv4')
                    })
                
                security_groups.append({
                    'id': sg.id,
                    'name': getattr(sg, 'name', 'unnamed'),
                    'description': getattr(sg, 'description', ''),
                    'tenant_id': getattr(sg, 'tenant_id', 'unknown'),
                    'project_id': getattr(sg, 'project_id', 'unknown'),
                    'created_at': str(getattr(sg, 'created_at', 'unknown')),
                    'updated_at': str(getattr(sg, 'updated_at', 'unknown')),
                    'rules': rules,
                    'rule_count': len(rules)
                })
        
        logger.info(f"Retrieved {len(security_groups)} security groups for project {current_project_id}")
        return security_groups
    except Exception as e:
        logger.error(f"Failed to get security groups: {e}")
        return [
            {
                'id': 'default-sg', 'name': 'default', 'description': 'Default security group',
                'rules': [{'direction': 'ingress', 'protocol': 'tcp', 'port_range_min': 22, 'port_range_max': 22}],
                'error': str(e)
            }
        ]


def get_floating_ips() -> List[Dict[str, Any]]:
    """
    Get list of floating IPs for current project.
    
    Returns:
        List of floating IP dictionaries for current project
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        current_project_id = conn.current_project_id
        floating_ips = []
        
        for fip in conn.network.ips():
            # Filter by current project
            fip_project_id = getattr(fip, 'project_id', None) or getattr(fip, 'tenant_id', None)
            if fip_project_id == current_project_id:
                floating_ips.append({
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(fip, 'fixed_ip_address', None),
                    'port_id': getattr(fip, 'port_id', None),
                    'router_id': getattr(fip, 'router_id', None),
                    'status': getattr(fip, 'status', 'unknown'),
                    'tenant_id': getattr(fip, 'tenant_id', 'unknown'),
                    'project_id': getattr(fip, 'project_id', 'unknown'),
                    'floating_network_id': getattr(fip, 'floating_network_id', 'unknown'),
                    'created_at': str(getattr(fip, 'created_at', 'unknown')),
                    'updated_at': str(getattr(fip, 'updated_at', 'unknown')),
                    'description': getattr(fip, 'description', '')
                })
        
        logger.info(f"Retrieved {len(floating_ips)} floating IPs for project {current_project_id}")
        return floating_ips
    except Exception as e:
        logger.error(f"Failed to get floating IPs: {e}")
        return [
            {
                'id': 'fip-1', 'floating_ip_address': '192.168.1.100',
                'fixed_ip_address': None, 'status': 'DOWN', 'error': str(e)
            }
        ]


def set_floating_ip(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage floating IPs (allocate, release, associate, disassociate).
    
    Args:
        action: Action to perform (allocate, release, associate, disassociate, list)
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the floating IP operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            floating_ips = []
            for fip in conn.network.ips():
                floating_ips.append({
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(fip, 'fixed_ip_address', None),
                    'port_id': getattr(fip, 'port_id', None),
                    'status': getattr(fip, 'status', 'unknown')
                })
            return {
                'success': True,
                'floating_ips': floating_ips,
                'count': len(floating_ips)
            }
            
        elif action.lower() == 'allocate':
            # The public tool forwards `floating_network_id`; older callers pass
            # `network`/`network_name`. Previously only the latter two were read,
            # so `set_floating_ip(action="allocate", ...)` was unreachable
            # end-to-end through the tool.
            network_ref = (
                kwargs.get('floating_network_id')
                or kwargs.get('network')
                or kwargs.get('network_name')
                or kwargs.get('external_network_id')
            )
            subnet_id = kwargs.get('subnet_id')
            description = kwargs.get('description')
            
            if not network_ref:
                return {
                    'success': False,
                    'message': 'floating_network_id (or network) is required for allocate action'
                }
            
            # Find the external network by name or ID. The external check is
            # only enforced when the attribute is actually present, because some
            # deployments do not populate is_router_external on the resource.
            external_network = None
            for network in conn.network.networks():
                if getattr(network, 'name', '') == network_ref or network.id == network_ref:
                    if getattr(network, 'is_router_external', True):
                        external_network = network
                        break
            
            if not external_network:
                # Distinguish "no such network" from "exists but not external"
                exists = any(
                    getattr(n, 'name', '') == network_ref or n.id == network_ref
                    for n in conn.network.networks()
                )
                if exists:
                    return {
                        'success': False,
                        'message': f'Network "{network_ref}" is not an external (router) network'
                    }
                return {
                    'success': False,
                    'message': f'External network "{network_ref}" not found'
                }
            
            create_params = {
                'floating_network_id': external_network.id
            }
            
            if subnet_id:
                create_params['subnet_id'] = subnet_id
            
            fip = conn.network.create_ip(**create_params)
            
            return {
                'success': True,
                'message': f'Floating IP allocated successfully',
                'floating_ip': {
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'status': getattr(fip, 'status', 'unknown'),
                    'floating_network_id': getattr(fip, 'floating_network_id', 'unknown')
                }
            }
            
        elif action.lower() == 'release':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for release action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            conn.network.delete_ip(fip)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} released successfully'
            }
            
        elif action.lower() == 'associate':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            port_id = kwargs.get('port_id')
            fixed_ip_address = kwargs.get('fixed_ip_address')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
                
            if not port_id:
                return {
                    'success': False,
                    'message': 'port_id is required for associate action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            update_params = {'port_id': port_id}
            if fixed_ip_address:
                update_params['fixed_ip_address'] = fixed_ip_address
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} associated successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None)
                }
            }
            
        elif action.lower() == 'disassociate':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            updated_fip = conn.network.update_ip(fip, port_id=None)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} disassociated successfully'
            }
        
        elif action.lower() == 'show':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for show action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            return {
                'success': True,
                'floating_ip': {
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(fip, 'fixed_ip_address', None),
                    'port_id': getattr(fip, 'port_id', None),
                    'router_id': getattr(fip, 'router_id', None),
                    'status': getattr(fip, 'status', 'unknown'),
                    'tenant_id': getattr(fip, 'tenant_id', 'unknown'),
                    'project_id': getattr(fip, 'project_id', 'unknown'),
                    'floating_network_id': getattr(fip, 'floating_network_id', 'unknown'),
                    'description': getattr(fip, 'description', ''),
                    'created_at': str(getattr(fip, 'created_at', 'unknown')),
                    'updated_at': str(getattr(fip, 'updated_at', 'unknown'))
                }
            }
            
        elif action.lower() == 'set':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for set action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Update parameters
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('port_id') is not None:
                update_params['port_id'] = kwargs['port_id']
            if kwargs.get('fixed_ip_address') is not None:
                update_params['fixed_ip_address'] = kwargs['fixed_ip_address']
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} updated successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None),
                    'description': getattr(updated_fip, 'description', '')
                }
            }
            
        elif action.lower() == 'unset':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for unset action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Unset parameters (clear them)
            update_params = {}
            unset_properties = kwargs.get('properties', [])
            
            if 'description' in unset_properties:
                update_params['description'] = ''
            if 'port' in unset_properties:
                update_params['port_id'] = None
                update_params['fixed_ip_address'] = None
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No properties specified to unset'
                }
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} properties unset successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None)
                }
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: allocate, release, associate, disassociate, list, show, set, unset'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage floating IP: {e}")
        return {
            'success': False,
            'message': f'Failed to manage floating IP: {str(e)}',
            'error': str(e)
        }


def get_floating_ip_pools() -> List[Dict[str, Any]]:
    """
    Get list of floating IP pools (external networks).
    
    Returns:
        List of floating IP pool dictionaries
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        pools = []
        
        for network in conn.network.networks():
            if getattr(network, 'is_router_external', False):
                # Count available and used floating IPs
                used_ips = 0
                total_ips = 0
                
                for subnet in conn.network.subnets():
                    if getattr(subnet, 'network_id', None) == network.id:
                        # Calculate total IPs from allocation pools
                        allocation_pools = getattr(subnet, 'allocation_pools', [])
                        for pool in allocation_pools:
                            # Simple IP range calculation (this could be more sophisticated)
                            total_ips += 100  # Placeholder calculation
                
                # Count used floating IPs
                for fip in conn.network.ips():
                    if getattr(fip, 'floating_network_id', None) == network.id:
                        used_ips += 1
                
                pools.append({
                    'id': network.id,
                    'name': getattr(network, 'name', 'unnamed'),
                    'network_id': network.id,
                    'total_ips': total_ips,
                    'used_ips': used_ips,
                    'available_ips': total_ips - used_ips,
                    'admin_state_up': getattr(network, 'is_admin_state_up', True)
                })
        
        return pools
    except Exception as e:
        logger.error(f"Failed to get floating IP pools: {e}")
        return [{
            'id': 'pool-error',
            'name': 'Error retrieving pools',
            'error': str(e)
        }]


def set_floating_ip_port_forwarding(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage floating IP port forwarding rules.
    
    Args:
        action: Action to perform (create, delete, list, show, set)
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the port forwarding operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            floating_ip_id = kwargs.get('floating_ip_id')
            floating_ip_address = kwargs.get('floating_ip_address')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for list action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Get port forwarding rules for this floating IP
            port_forwardings = []
            try:
                for pf in conn.network.port_forwardings(floatingip=fip.id):
                    port_forwardings.append({
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown'),
                        'internal_port_id': getattr(pf, 'internal_port_id', None),
                        'description': getattr(pf, 'description', '')
                    })
            except Exception as e:
                logger.warning(f"Could not retrieve port forwarding rules: {e}")
                # Return empty list if port forwarding is not supported
                
            return {
                'success': True,
                'floating_ip_id': fip.id,
                'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                'port_forwardings': port_forwardings,
                'count': len(port_forwardings)
            }
            
        elif action.lower() == 'create':
            floating_ip_id = kwargs.get('floating_ip_id')
            floating_ip_address = kwargs.get('floating_ip_address')
            protocol = kwargs.get('protocol', 'tcp')
            external_port = kwargs.get('external_port')
            internal_port = kwargs.get('internal_port')
            internal_ip_address = kwargs.get('internal_ip_address')
            internal_port_id = kwargs.get('internal_port_id')
            description = kwargs.get('description', '')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
                
            if not external_port or not internal_port:
                return {
                    'success': False,
                    'message': 'external_port and internal_port are required for create action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            create_params = {
                'protocol': protocol,
                'external_port': external_port,
                'internal_port': internal_port
            }
            
            if internal_ip_address:
                create_params['internal_ip_address'] = internal_ip_address
            if internal_port_id:
                create_params['internal_port_id'] = internal_port_id
            if description:
                create_params['description'] = description
            
            try:
                pf = conn.network.create_port_forwarding(floatingip=fip.id, **create_params)
                return {
                    'success': True,
                    'message': f'Port forwarding rule created successfully',
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', protocol),
                        'external_port': getattr(pf, 'external_port', external_port),
                        'internal_port': getattr(pf, 'internal_port', internal_port),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', internal_ip_address)
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create port forwarding rule: {str(e)}',
                    'note': 'Port forwarding may not be supported in this OpenStack deployment'
                }
                
        elif action.lower() == 'delete':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for delete action'
                }
            
            try:
                conn.network.delete_port_forwarding(port_forwarding_id, floatingip=floating_ip_id)
                return {
                    'success': True,
                    'message': f'Port forwarding rule deleted successfully'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete port forwarding rule: {str(e)}'
                }
                
        elif action.lower() == 'show':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for show action'
                }
            
            try:
                pf = conn.network.get_port_forwarding(port_forwarding_id, floatingip=floating_ip_id)
                return {
                    'success': True,
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown'),
                        'internal_port_id': getattr(pf, 'internal_port_id', None),
                        'description': getattr(pf, 'description', ''),
                        'created_at': str(getattr(pf, 'created_at', 'unknown')),
                        'updated_at': str(getattr(pf, 'updated_at', 'unknown'))
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to get port forwarding rule: {str(e)}'
                }
                
        elif action.lower() == 'set':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for set action'
                }
            
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('internal_ip_address'):
                update_params['internal_ip_address'] = kwargs['internal_ip_address']
            if kwargs.get('internal_port'):
                update_params['internal_port'] = kwargs['internal_port']
            if kwargs.get('internal_port_id'):
                update_params['internal_port_id'] = kwargs['internal_port_id']
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
            
            try:
                pf = conn.network.update_port_forwarding(
                    port_forwarding_id, 
                    floatingip=floating_ip_id, 
                    **update_params
                )
                return {
                    'success': True,
                    'message': f'Port forwarding rule updated successfully',
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown')
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to update port forwarding rule: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unsupported action: {action}. Supported actions: create, delete, list, show, set'
            }
            
    except Exception as e:
        logger.error(f"Port forwarding management failed: {e}")
        return {
            'success': False,
            'message': f'Port forwarding management failed: {str(e)}'
        }


def get_routers() -> List[Dict[str, Any]]:
    """
    Get list of routers with detailed information for current project.
    
    Returns:
        List of router dictionaries for current project
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        current_project_id = conn.current_project_id
        routers = []
        
        for router in conn.network.routers():
            # Filter by current project
            router_project_id = getattr(router, 'project_id', None) or getattr(router, 'tenant_id', None)
            if router_project_id == current_project_id:
                # Get router interfaces (ports)
                interfaces = []
                try:
                    for port in conn.network.ports():
                        if getattr(port, 'device_id', '') == router.id and \
                           getattr(port, 'device_owner', '').startswith('network:router_interface'):
                            interfaces.append({
                                'port_id': port.id,
                                'subnet_id': getattr(port, 'fixed_ips', [{}])[0].get('subnet_id', 'unknown') if getattr(port, 'fixed_ips', []) else 'unknown',
                                'ip_address': getattr(port, 'fixed_ips', [{}])[0].get('ip_address', 'unknown') if getattr(port, 'fixed_ips', []) else 'unknown'
                            })
                except Exception as e:
                    logger.warning(f"Failed to get router interfaces for {router.id}: {e}")
                
                routers.append({
                    'id': router.id,
                    'name': getattr(router, 'name', 'unnamed'),
                    'status': getattr(router, 'status', 'unknown'),
                    'admin_state_up': getattr(router, 'is_admin_state_up', True),
                    'external_gateway_info': getattr(router, 'external_gateway_info', None),
                    'tenant_id': getattr(router, 'tenant_id', 'unknown'),
                    'project_id': getattr(router, 'project_id', 'unknown'),
                    'created_at': str(getattr(router, 'created_at', 'unknown')),
                    'updated_at': str(getattr(router, 'updated_at', 'unknown')),
                    'description': getattr(router, 'description', ''),
                    'ha': getattr(router, 'is_ha', False),
                    'distributed': getattr(router, 'is_distributed', False),
                    # Static routes were never surfaced, so the routing table
                    # was invisible even though the SDK exposes it.
                    'routes': getattr(router, 'routes', []),
                    'interfaces': interfaces,
                    'interface_count': len(interfaces)
                })
        
        logger.info(f"Retrieved {len(routers)} routers for project {current_project_id}")
        return routers
    except Exception as e:
        logger.error(f"Failed to get routers: {e}")
        return [
            {
                'id': 'router-1', 'name': 'demo-router', 'status': 'ACTIVE',
                'admin_state_up': True, 'interfaces': [], 'error': str(e)
            }
        ]


def set_routers(action: str, router_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack routers.

    Args:
        action: Action to perform (list, show, create, set, delete, add_interface, remove_interface)
        router_name: Name or ID of router (for specific operations)
        **kwargs: Additional parameters

    Returns:
        Result of the router operation
    """
    try:
        from ..connection import get_openstack_connection, find_resource_by_name_or_id
        conn = get_openstack_connection()

        if action.lower() == 'list':
            return {'success': True, 'routers': get_routers(), 'message': f'Retrieved {len(get_routers())} routers'}

        if action.lower() == 'show':
            routers = get_routers()
            for router in routers:
                if router['name'] == router_name or router['id'] == router_name:
                    return {'success': True, 'router': router, 'message': f'Found router {router_name}'}
            return {'success': False, 'message': f'Router {router_name} not found'}

        if action.lower() == 'create':
            create_params = {}
            create_params['name'] = kwargs.get('name', router_name)
            create_params['admin_state_up'] = kwargs.get('admin_state_up', True)
            if 'description' in kwargs:
                create_params['description'] = kwargs['description']
            if 'ha' in kwargs:
                create_params['ha'] = kwargs['ha']
            if 'distributed' in kwargs:
                create_params['distributed'] = kwargs['distributed']
            if kwargs.get('mtu'):
                return {
                    'success': False,
                    'message': 'mtu is not settable on a router; set it on the '
                               'network instead (the network MTU must already be '
                               'low enough to fit the router)'
                }
            external_network_id = kwargs.get('external_network_id')
            if external_network_id:
                create_params['external_gateway_info'] = {
                    'network_id': external_network_id,
                    'enable_snat': kwargs.get('enable_snat', True),
                }
                if 'gateway_ip' in kwargs:
                    create_params['external_gateway_info']['external_fixed_ips'] = [{'subnet_id': kwargs.get('subnet_id', ''), 'ip_address': kwargs['gateway_ip']}]
            router = conn.network.create_router(**create_params)
            return {'success': True, 'router': {'id': router.id, 'name': router.name, 'status': router.status}, 'message': f'Router {router.name} created'}

        if action.lower() == 'set':
            if not router_name:
                return {'success': False, 'message': 'router_name is required for set action'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            update_params = {}
            if 'name' in kwargs:
                update_params['name'] = kwargs['name']
            if 'description' in kwargs:
                update_params['description'] = kwargs['description']
            if 'admin_state_up' in kwargs:
                update_params['admin_state_up'] = kwargs['admin_state_up']
            if 'ha' in kwargs:
                update_params['ha'] = kwargs['ha']
            if 'distributed' in kwargs:
                update_params['distributed'] = kwargs['distributed']
            if kwargs.get('mtu'):
                return {
                    'success': False,
                    'message': 'mtu is not settable on a router; set it on the '
                               'network instead (the network MTU must already be '
                               'low enough to fit the router)'
                }
            if 'external_network_id' in kwargs:
                if not kwargs['external_network_id']:
                    # Neutron expresses 'no external gateway' as an empty object.
                    # Only a truthy value used to write this key, so detaching a
                    # gateway was impossible.
                    update_params['external_gateway_info'] = {}
                else:
                    update_params['external_gateway_info'] = {
                        'network_id': kwargs['external_network_id'],
                        'enable_snat': kwargs.get('enable_snat', True),
                    }
                    if 'gateway_ip' in kwargs and kwargs['gateway_ip']:
                        update_params['external_gateway_info']['external_fixed_ips'] = [{
                            'subnet_id': kwargs.get('subnet_id', ''),
                            'ip_address': kwargs['gateway_ip'],
                        }]
            router = conn.network.update_router(router, **update_params)
            return {'success': True, 'router': {'id': router.id, 'name': router.name, 'status': router.status}, 'message': f'Router {router_name} updated'}

        if action.lower() in ('add_routes', 'remove_routes'):
            if not router_name:
                return {'success': False, 'message': f'router_name is required for {action} action'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            # routes arrive as a list of {destination, nexthop} dicts
            routes = kwargs.get('routes') or []
            if not routes:
                return {'success': False, 'message': 'routes is required and must be a non-empty list'}
            route_body = {'routes': list(routes)}
            if action.lower() == 'add_routes':
                conn.network.add_extra_routes_to_router(router, route_body)
            else:
                conn.network.remove_extra_routes_from_router(router, route_body)
            updated = conn.network.update_router(router)
            verb = 'added to' if action.lower() == 'add_routes' else 'removed from'
            return {
                'success': True,
                'router': {
                    'id': updated.id,
                    'name': updated.name,
                    'routes': getattr(updated, 'routes', []),
                },
                'message': f'{len(routes)} route(s) {verb} router {router_name}',
            }

        if action.lower() in ('add_gateway', 'remove_gateway'):
            if not router_name:
                return {'success': False, 'message': f'router_name is required for {action} action'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            if action.lower() == 'remove_gateway':
                conn.network.remove_gateway_from_router(router, external_gateway_info={})
                return {
                    'success': True,
                    'router': {'id': router.id, 'name': router.name},
                    'message': f'External gateway removed from router {router_name}',
                }
            ext_net = kwargs.get('external_network_id') or kwargs.get('external_network')
            if not ext_net:
                return {'success': False, 'message': 'external_network_id is required for add_gateway action'}
            gateway_info = {'network_id': ext_net, 'enable_snat': kwargs.get('enable_snat', True)}
            if kwargs.get('gateway_ip'):
                gateway_info['external_fixed_ips'] = [{
                    'subnet_id': kwargs.get('subnet_id', ''),
                    'ip_address': kwargs['gateway_ip'],
                }]
            conn.network.add_gateway_to_router(router, external_gateway_info=gateway_info)
            return {
                'success': True,
                'router': {'id': router.id, 'name': router.name},
                'message': f'External gateway {ext_net} added to router {router_name}',
            }

        if action.lower() == 'delete':
            if not router_name:
                return {'success': False, 'message': 'router_name is required for delete action'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            conn.network.delete_router(router)
            return {'success': True, 'message': f'Router {router_name} deleted'}

        if action.lower() == 'add_interface':
            if not router_name:
                return {'success': False, 'message': 'router_name is required for add_interface action'}
            subnet_id = kwargs.get('subnet_id')
            if not subnet_id:
                return {'success': False, 'message': 'subnet_id is required for add_interface'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            interface = conn.network.add_interface_to_router(router, subnet_id=subnet_id)
            # add_interface_to_router returns the raw response body (a dict),
            # not a resource object, so field access must be by key.
            info = interface if isinstance(interface, dict) else interface.to_dict()
            return {'success': True, 'interface': {
                'id': info.get('port_id') or info.get('id'),
                'subnet_id': info.get('subnet_id'),
                'network_id': info.get('network_id'),
                'device_id': info.get('device_id'),
            }, 'message': f'Interface added to router {router_name}'}

        if action.lower() == 'remove_interface':
            if not router_name:
                return {'success': False, 'message': 'router_name is required for remove_interface action'}
            subnet_id = kwargs.get('subnet_id')
            if not subnet_id:
                return {'success': False, 'message': 'subnet_id is required for remove_interface'}
            router = find_resource_by_name_or_id(conn.network.routers(), router_name, "Router")
            if not router:
                return {'success': False, 'message': f'Router "{router_name}" not found or not accessible in current project'}
            conn.network.remove_interface_from_router(router, subnet_id=subnet_id)
            return {'success': True, 'message': f'Interface removed from router {router_name}'}

        return {'success': False, 'message': f'Unknown action: {action}'}
    except Exception as e:
        logger.error(f"Failed to set routers: {e}")
        return {'success': False, 'message': str(e)}


def set_network_ports(action: str, port_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage network ports.
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        port_name: Name or ID of port (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the port operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            ports = []
            for port in conn.network.ports():
                ports.append({
                    'id': port.id,
                    'name': getattr(port, 'name', 'unnamed'),
                    'network_id': getattr(port, 'network_id', 'unknown'),
                    'status': getattr(port, 'status', 'unknown'),
                    'admin_state_up': getattr(port, 'is_admin_state_up', True),
                    'device_id': getattr(port, 'device_id', ''),
                    'device_owner': getattr(port, 'device_owner', ''),
                    'mac_address': getattr(port, 'mac_address', 'unknown'),
                    'fixed_ips': getattr(port, 'fixed_ips', []),
                    'security_groups': getattr(port, 'security_group_ids', [])
                })
            return {
                'success': True,
                'ports': ports,
                'count': len(ports)
            }
            
        elif action.lower() == 'show':
            if not port_name:
                return {
                    'success': False,
                    'message': 'port_name is required for show action'
                }
            
            # Find the port
            for port in conn.network.ports():
                if getattr(port, 'name', '') == port_name or port.id == port_name:
                    return {
                        'success': True,
                        'port': {
                            'id': port.id,
                            'name': getattr(port, 'name', 'unnamed'),
                            'network_id': getattr(port, 'network_id', 'unknown'),
                            'status': getattr(port, 'status', 'unknown'),
                            'admin_state_up': getattr(port, 'is_admin_state_up', True),
                            'device_id': getattr(port, 'device_id', ''),
                            'device_owner': getattr(port, 'device_owner', ''),
                            'mac_address': getattr(port, 'mac_address', 'unknown'),
                            'fixed_ips': getattr(port, 'fixed_ips', []),
                            'security_groups': getattr(port, 'security_group_ids', []),
                            'created_at': str(getattr(port, 'created_at', 'unknown')),
                            'updated_at': str(getattr(port, 'updated_at', 'unknown'))
                        }
                    }
            
            return {
                'success': False,
                'message': f'Port "{port_name}" not found'
            }
            
        elif action.lower() == 'create':
            network_id = kwargs.get('network_id')
            name = kwargs.get('name', port_name)
            
            if not network_id:
                return {
                    'success': False,
                    'message': 'network_id is required for create action'
                }
            
            create_params = {'network_id': network_id}
            if name:
                create_params['name'] = name
            
            # Optional parameters
            if 'admin_state_up' in kwargs:
                create_params['is_admin_state_up'] = kwargs['admin_state_up']
            if 'fixed_ips' in kwargs:
                create_params['fixed_ips'] = kwargs['fixed_ips']
            if 'security_groups' in kwargs:
                create_params['security_group_ids'] = kwargs['security_groups']
            
            port = conn.network.create_port(**create_params)
            
            return {
                'success': True,
                'message': f'Port "{name or port.id}" created successfully',
                'port': {
                    'id': port.id,
                    'name': getattr(port, 'name', 'unnamed'),
                    'network_id': getattr(port, 'network_id', 'unknown'),
                    'status': getattr(port, 'status', 'unknown'),
                    'mac_address': getattr(port, 'mac_address', 'unknown')
                }
            }
            
        elif action.lower() == 'delete':
            if not port_name:
                return {
                    'success': False,
                    'message': 'port_name is required for delete action'
                }
            
            # Find the port using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            port = find_resource_by_name_or_id(
                conn.network.ports(), 
                port_name, 
                "Network Port"
            )
            
            if not port:
                return {
                    'success': False,
                    'message': f'Port "{port_name}" not found or not accessible in current project'
                }
                    
            conn.network.delete_port(port)
            return {
                'success': True,
                'message': f'Port "{port_name}" deleted successfully'
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show, create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage network port: {e}")
        return {
            'success': False,
            'message': f'Failed to manage network port: {str(e)}',
            'error': str(e)
        }


def set_subnets(action: str, subnet_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage network subnets.
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        subnet_name: Name or ID of subnet (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the subnet operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            subnets = []
            for subnet in conn.network.subnets():
                subnets.append({
                    'id': subnet.id,
                    'name': getattr(subnet, 'name', 'unnamed'),
                    'network_id': getattr(subnet, 'network_id', 'unknown'),
                    'cidr': getattr(subnet, 'cidr', 'unknown'),
                    'ip_version': getattr(subnet, 'ip_version', 4),
                    'gateway_ip': getattr(subnet, 'gateway_ip', None),
                    'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False),
                    'allocation_pools': getattr(subnet, 'allocation_pools', []),
                    'dns_nameservers': getattr(subnet, 'dns_nameservers', [])
                })
            return {
                'success': True,
                'subnets': subnets,
                'count': len(subnets)
            }
            
        elif action.lower() == 'show':
            if not subnet_name:
                return {
                    'success': False,
                    'message': 'subnet_name is required for show action'
                }
            
            # Find the subnet
            for subnet in conn.network.subnets():
                if getattr(subnet, 'name', '') == subnet_name or subnet.id == subnet_name:
                    return {
                        'success': True,
                        'subnet': {
                            'id': subnet.id,
                            'name': getattr(subnet, 'name', 'unnamed'),
                            'network_id': getattr(subnet, 'network_id', 'unknown'),
                            'cidr': getattr(subnet, 'cidr', 'unknown'),
                            'ip_version': getattr(subnet, 'ip_version', 4),
                            'gateway_ip': getattr(subnet, 'gateway_ip', None),
                            'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False),
                            'allocation_pools': getattr(subnet, 'allocation_pools', []),
                            'dns_nameservers': getattr(subnet, 'dns_nameservers', []),
                            'host_routes': getattr(subnet, 'host_routes', []),
                            'created_at': str(getattr(subnet, 'created_at', 'unknown')),
                            'updated_at': str(getattr(subnet, 'updated_at', 'unknown'))
                        }
                    }
            
            return {
                'success': False,
                'message': f'Subnet "{subnet_name}" not found'
            }
            
        elif action.lower() == 'create':
            network_id = kwargs.get('network_id')
            cidr = kwargs.get('cidr')
            name = kwargs.get('name', subnet_name)
            
            if not network_id:
                return {
                    'success': False,
                    'message': 'network_id is required for create action'
                }
                
            if not cidr:
                return {
                    'success': False,
                    'message': 'cidr is required for create action'
                }
            
            create_params = {
                'network_id': network_id,
                'cidr': cidr,
                'ip_version': kwargs.get('ip_version', 4)
            }
            
            if name:
                create_params['name'] = name
            if 'gateway_ip' in kwargs:
                create_params['gateway_ip'] = kwargs['gateway_ip']
            if 'enable_dhcp' in kwargs:
                create_params['is_dhcp_enabled'] = kwargs['enable_dhcp']
            if 'dns_nameservers' in kwargs:
                create_params['dns_nameservers'] = kwargs['dns_nameservers']
            if 'allocation_pools' in kwargs:
                create_params['allocation_pools'] = kwargs['allocation_pools']
            
            subnet = conn.network.create_subnet(**create_params)
            
            return {
                'success': True,
                'message': f'Subnet "{name or subnet.id}" created successfully',
                'subnet': {
                    'id': subnet.id,
                    'name': getattr(subnet, 'name', 'unnamed'),
                    'network_id': getattr(subnet, 'network_id', 'unknown'),
                    'cidr': getattr(subnet, 'cidr', 'unknown'),
                    'gateway_ip': getattr(subnet, 'gateway_ip', None)
                }
            }
            
        elif action.lower() == 'delete':
            if not subnet_name:
                return {
                    'success': False,
                    'message': 'subnet_name is required for delete action'
                }
            
            # Find the subnet using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            subnet = find_resource_by_name_or_id(
                conn.network.subnets(), 
                subnet_name, 
                "Subnet"
            )
            
            if not subnet:
                return {
                    'success': False,
                    'message': f'Subnet "{subnet_name}" not found or not accessible in current project'
                }
            
            conn.network.delete_subnet(subnet)
            return {
                'success': True,
                'message': f'Subnet "{subnet_name}" deleted successfully'
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show, create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage subnet: {e}")
        return {
            'success': False,
            'message': f'Failed to manage subnet: {str(e)}',
            'error': str(e)
        }

def set_network_qos_policies(action: str, policy_name: str = None, **kwargs) -> Dict[str, Any]:
    """Manage Neutron QoS policies and the rules attached to them.

    Replaces a stub that returned `{'success': False}` for every action.
    """
    from ..connection import (
        find_resource_by_name_or_id,
        get_openstack_connection,
    )
    conn = get_openstack_connection()

    if action.lower() == 'list':
        policies = []
        for policy in conn.network.qos_policies():
            policies.append({
                'id': policy.id,
                'name': policy.name,
                'description': getattr(policy, 'description', None),
                'shared': getattr(policy, 'is_shared', False),
                'project_id': getattr(policy, 'project_id', None),
                'rules': [rule_type for rule_type in (
                    getattr(policy, 'rules', None) or [])],
            })
        return {
            'success': True,
            'policies': policies,
            'message': f'Found {len(policies)} QoS polic(y/ies)',
        }

    if action.lower() == 'show':
        if not policy_name:
            return {'success': False, 'message': 'policy_name is required for show action'}
        policy = find_resource_by_name_or_id(
            conn.network.qos_policies(), policy_name, 'QoS policy')
        if not policy:
            return {
                'success': False,
                'message': f'QoS policy "{policy_name}" not found or not accessible in current project',
            }
        rules = []
        for rule_type in (getattr(policy, 'rules', None) or []):
            rules.extend(_collect_qos_rules(conn, policy, rule_type))
        return {
            'success': True,
            'policy': {
                'id': policy.id,
                'name': policy.name,
                'description': getattr(policy, 'description', None),
                'shared': getattr(policy, 'is_shared', False),
                'project_id': getattr(policy, 'project_id', None),
                'rules': rules,
            },
            'message': f'QoS policy {policy.name} retrieved',
        }

    if action.lower() == 'create':
        create_params = {'name': policy_name}
        if not policy_name:
            return {'success': False, 'message': 'policy_name is required for create action'}
        if 'description' in kwargs:
            create_params['description'] = kwargs['description']
        if 'shared' in kwargs:
            create_params['shared'] = kwargs['shared']
        policy = conn.network.create_qos_policy(**create_params)
        return {
            'success': True,
            'policy': {'id': policy.id, 'name': policy.name},
            'message': f'QoS policy {policy.name} created',
        }

    if action.lower() == 'set':
        if not policy_name:
            return {'success': False, 'message': 'policy_name is required for set action'}
        policy = find_resource_by_name_or_id(
            conn.network.qos_policies(), policy_name, 'QoS policy')
        if not policy:
            return {
                'success': False,
                'message': f'QoS policy "{policy_name}" not found or not accessible in current project',
            }
        update_params = {}
        new_name = kwargs.get('new_name') or kwargs.get('name')
        if new_name:
            update_params['name'] = new_name
        if 'description' in kwargs:
            update_params['description'] = kwargs['description']
        if 'shared' in kwargs:
            update_params['shared'] = kwargs['shared']
        if not update_params:
            return {
                'success': False,
                'message': 'No update parameters provided (new_name, description, shared)',
            }
        policy = conn.network.update_qos_policy(policy, **update_params)
        return {
            'success': True,
            'policy': {'id': policy.id, 'name': policy.name},
            'message': f'QoS policy {policy_name} updated',
        }

    if action.lower() == 'delete':
        if not policy_name:
            return {'success': False, 'message': 'policy_name is required for delete action'}
        policy = find_resource_by_name_or_id(
            conn.network.qos_policies(), policy_name, 'QoS policy')
        if not policy:
            return {
                'success': False,
                'message': f'QoS policy "{policy_name}" not found or not accessible in current project',
            }
        conn.network.delete_qos_policy(policy)
        return {'success': True, 'message': f'QoS policy {policy_name} deleted'}

    # ---- QoS rules ----
    if action.lower() in ('create_rule', 'delete_rule', 'list_rules'):
        return _handle_qos_rule_action(conn, action, policy_name, **kwargs)

    return {
        'success': False,
        'message': f'Unknown action "{action}". Supported: list, show, create, set, '
                   f'delete, create_rule, delete_rule, list_rules',
    }


def _collect_qos_rules(conn, policy, rule_type: str) -> list:
    """Fetch the concrete rule objects for one entry of a policy's rule list."""
    collectors = {
        'bandwidth_limit': conn.network.qos_bandwidth_limit_rules,
        'dscp_marking': conn.network.qos_dscp_marking_rules,
        'minimum_bandwidth': conn.network.qos_minimum_bandwidth_rules,
        'minimum_packet_rate': conn.network.qos_minimum_packet_rate_rules,
        'packet_rate_limit': conn.network.qos_packet_rate_limit_rules,
    }
    collect = collectors.get(rule_type)
    if collect is None:
        return []
    out = []
    for rule in collect(policy):
        entry = {
            'id': rule.id,
            'name': getattr(rule, 'name', None),
            'type': rule_type,
        }
        for attr in ('max_kbps', 'max_burst_kbps', 'dscp_mark', 'min_kpps',
                     'direction'):
            if hasattr(rule, attr):
                entry[attr] = getattr(rule, attr)
        out.append(entry)
    return out


def _handle_qos_rule_action(conn, action: str, policy_name, **kwargs):
    """Create / list / delete the individual rule types under a QoS policy."""
    rule_type = kwargs.get('rule_type')
    if not rule_type:
        return {
            'success': False,
            'message': 'rule_type is required for this action. One of: bandwidth_limit, '
                       'dscp_marking, minimum_bandwidth, minimum_packet_rate, '
                       'packet_rate_limit',
        }
    if not policy_name:
        return {'success': False, 'message': 'policy_name is required for this action'}

    policy = find_resource_by_name_or_id(
        conn.network.qos_policies(), policy_name, 'QoS policy')
    if not policy:
        return {
            'success': False,
            'message': f'QoS policy "{policy_name}" not found or not accessible in current project',
        }

    if action.lower() == 'list_rules':
        return {
            'success': True,
            'rules': _collect_qos_rules(conn, policy, rule_type),
            'message': f'Rules of type {rule_type} listed for policy {policy_name}',
        }

    if action.lower() == 'create_rule':
        create_map = {
            'bandwidth_limit': 'create_qos_bandwidth_limit_rule',
            'dscp_marking': 'create_qos_dscp_marking_rule',
            'minimum_bandwidth': 'create_qos_minimum_bandwidth_rule',
            'minimum_packet_rate': 'create_qos_minimum_packet_rate_rule',
            'packet_rate_limit': 'create_qos_packet_rate_limit_rule',
        }
        method = create_map.get(rule_type)
        if not method:
            return {'success': False, 'message': f'Unknown rule_type "{rule_type}"'}
        rule_params = {
            k: v for k, v in kwargs.items()
            if k in ('name', 'direction', 'max_kbps', 'max_burst_kbps',
                     'dscp_mark', 'min_kpps')
        }
        if not rule_params.get('name'):
            return {'success': False, 'message': 'name is required for create_rule'}
        rule = getattr(conn.network, method)(policy, **rule_params)
        return {
            'success': True,
            'rule': {
                'id': rule.id,
                'name': getattr(rule, 'name', None),
                'type': rule_type,
            },
            'message': f'{rule_type} rule {rule_params["name"]} created on policy {policy_name}',
        }

    if action.lower() == 'delete_rule':
        rule_name = kwargs.get('rule_name') or kwargs.get('name')
        if not rule_name:
            return {'success': False, 'message': 'rule_name is required for delete_rule'}
        find_map = {
            'bandwidth_limit': 'find_qos_bandwidth_limit_rule',
            'dscp_marking': 'find_qos_dscp_marking_rule',
            'minimum_bandwidth': 'find_qos_minimum_bandwidth_rule',
            'minimum_packet_rate': 'find_qos_minimum_packet_rate_rule',
            'packet_rate_limit': 'find_qos_packet_rate_limit_rule',
        }
        delete_map = {
            'bandwidth_limit': 'delete_qos_bandwidth_limit_rule',
            'dscp_marking': 'delete_qos_dscp_marking_rule',
            'minimum_bandwidth': 'delete_qos_minimum_bandwidth_rule',
            'minimum_packet_rate': 'delete_qos_minimum_packet_rate_rule',
            'packet_rate_limit': 'delete_qos_packet_rate_limit_rule',
        }
        rule = getattr(conn.network, find_map[rule_type])(
            rule_name, ignore_missing=False, qos_policy=policy)
        if not rule:
            return {
                'success': False,
                'message': f'{rule_type} rule "{rule_name}" not found on policy {policy_name}',
            }
        getattr(conn.network, delete_map[rule_type])(rule, policy)
        return {
            'success': True,
            'message': f'{rule_type} rule {rule_name} deleted from policy {policy_name}',
        }

    return {'success': False, 'message': f'Unknown action "{action}"'}


def set_network_agents(action: str, agent_id: str = None, **kwargs) -> Dict[str, Any]:
    """Manage Neutron agents and their network/router bindings.

    Replaces a stub that returned `{'success': False}` for every action.
    """
    from ..connection import (
        find_resource_by_name_or_id,
        get_openstack_connection,
    )
    conn = get_openstack_connection()

    if action.lower() == 'list':
        agents = []
        for agent in conn.network.agents():
            agents.append({
                'id': agent.id,
                'name': getattr(agent, 'name', None),
                # Neutron's "agent_type" body field is exposed as .agent_type;
                # 'binary' is the legacy alias and is absent in 4.20.0.
                'agent_type': getattr(agent, 'agent_type', None),
                'host': getattr(agent, 'host', None),
                'admin_state_up': getattr(agent, 'is_admin_state_up', None),
                'alive': getattr(agent, 'is_alive', None),
                # The wire field is `resources`; the SDK attribute is
                # .resources_synced. There is no .resources attribute.
                'resources_synced': getattr(agent, 'resources_synced', None),
            })
        return {
            'success': True,
            'agents': agents,
            'message': f'Found {len(agents)} agent(s)',
        }

    if action.lower() == 'show':
        if not agent_id:
            return {'success': False, 'message': 'agent_id is required for show action'}
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {
                'success': False,
                'message': f'Agent "{agent_id}" not found',
            }
        return {
            'success': True,
            'agent': {
                'id': agent.id,
                'name': getattr(agent, 'name', None),
                'agent_type': getattr(agent, 'agent_type', None),
                'host': getattr(agent, 'host', None),
                'admin_state_up': getattr(agent, 'is_admin_state_up', None),
                'alive': getattr(agent, 'is_alive', None),
                'resources_synced': getattr(agent, 'resources_synced', None),
            },
            'message': f'Agent {agent_id} retrieved',
        }

    if action.lower() == 'set':
        if not agent_id:
            return {'success': False, 'message': 'agent_id is required for set action'}
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {
                'success': False,
                'message': f'Agent "{agent_id}" not found',
            }
        update_params = {}
        # The wire field is `admin_state_up`; the SDK attribute is
        # .is_admin_state_up. Passing `admin` here would be silently dropped.
        if 'admin_state_up' in kwargs:
            update_params['admin_state_up'] = kwargs['admin_state_up']
        if 'description' in kwargs:
            update_params['description'] = kwargs['description']
        if not update_params:
            return {
                'success': False,
                'message': 'No update parameters provided (admin_state_up, description)',
            }
        agent = conn.network.update_agent(agent, **update_params)
        return {
            'success': True,
            'agent': {
                'id': agent.id,
                'name': getattr(agent, 'name', None),
                'admin_state_up': getattr(agent, 'is_admin_state_up', None),
            },
            'message': f'Agent {agent_id} updated',
        }

    if action.lower() == 'delete':
        if not agent_id:
            return {'success': False, 'message': 'agent_id is required for delete action'}
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {
                'success': False,
                'message': f'Agent "{agent_id}" not found',
            }
        conn.network.delete_agent(agent)
        return {'success': True, 'message': f'Agent {agent_id} deleted'}

    if action.lower() in ('list_dhcp_networks', 'list_agent_networks'):
        if not agent_id:
            return {'success': False, 'message': 'agent_id is required for this action'}
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {'success': False, 'message': f'Agent "{agent_id}" not found'}
        networks = []
        for entry in conn.network.dhcp_agent_hosting_networks(agent):
            net = getattr(entry, 'network', None)
            if net is None and isinstance(entry, dict):
                net = entry.get('network')
            networks.append({
                'id': getattr(net, 'id', None) if net is not None else None,
                'name': getattr(net, 'name', None) if net is not None else None,
            })
        return {
            'success': True,
            'networks': networks,
            'message': f'Networks hosted by DHCP agent {agent_id}',
        }

    # ---- network / router bindings ----
    if action.lower() in ('add_dhcp_to_network', 'remove_dhcp_from_network'):
        network_ref = kwargs.get('network_id') or kwargs.get('network_name') or kwargs.get('network')
        if not agent_id or not network_ref:
            return {
                'success': False,
                'message': 'agent_id and network_id are required for this action',
            }
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {'success': False, 'message': f'Agent "{agent_id}" not found'}
        network = find_resource_by_name_or_id(
            conn.network.networks(), network_ref, 'network')
        if not network:
            return {
                'success': False,
                'message': f'Network "{network_ref}" not found or not accessible in current project',
            }
        if action.lower() == 'add_dhcp_to_network':
            conn.network.add_dhcp_agent_to_network(agent, network)
            verb = 'added to'
        else:
            conn.network.remove_dhcp_agent_from_network(agent, network)
            verb = 'removed from'
        return {
            'success': True,
            'message': f'DHCP agent {agent_id} {verb} network {network_ref}',
        }

    if action.lower() in ('add_router_to_agent', 'remove_router_from_agent',
                           'list_agent_routers'):
        router_ref = kwargs.get('router_id') or kwargs.get('router_name') or kwargs.get('router')
        if not agent_id:
            return {'success': False, 'message': 'agent_id is required for this action'}
        agent = _find_agent(conn, agent_id)
        if not agent:
            return {'success': False, 'message': f'Agent "{agent_id}" not found'}

        if action.lower() == 'list_agent_routers':
            routers = []
            for entry in conn.network.agent_hosted_routers(agent):
                router_info = getattr(entry, 'router', None)
                routers.append({
                    'id': getattr(router_info, 'id', None),
                    'name': getattr(router_info, 'name', None),
                    'ha_chassis_priority': getattr(entry, 'ha_chassis_priority', None),
                })
            return {
                'success': True,
                'routers': routers,
                'message': f'Routers hosted by agent {agent_id}',
            }

        if not router_ref:
            return {
                'success': False,
                'message': 'router_id is required for this action',
            }
        router = find_resource_by_name_or_id(
            conn.network.routers(), router_ref, 'Router')
        if not router:
            return {
                'success': False,
                'message': f'Router "{router_ref}" not found or not accessible in current project',
            }
        if action.lower() == 'add_router_to_agent':
            conn.network.add_router_to_agent(agent, router)
            verb = 'added to'
        else:
            conn.network.remove_router_from_agent(agent, router)
            verb = 'removed from'
        return {
            'success': True,
            'message': f'L3 agent {agent_id} {verb} router {router_ref}',
        }

    return {
        'success': False,
        'message': f'Unknown action "{action}". Supported: list, show, set, delete, '
                   f'list_dhcp_networks, add_dhcp_to_network, remove_dhcp_from_network, '
                   f'add_router_to_agent, remove_router_from_agent, list_agent_routers',
    }


def _find_agent(conn, agent_ref: str):
    """Resolve an agent by ID or by host. Agent has no usable name field."""
    for agent in conn.network.agents():
        if agent.id == agent_ref:
            return agent
    for agent in conn.network.agents():
        if getattr(agent, 'host', None) == agent_ref:
            return agent
    return None


def set_security_groups(action: str, security_group_name: str = None, **kwargs) -> Dict[str, Any]:
    """Manage security groups and their rules.

    Previously only read-only listing existed (get_security_groups), so rules
    could never be created or removed through this server.

    Note: Neutron security group rules are immutable (the SDK resource sets
    allow_commit = False and the proxy has no update_security_group_rule), so
    there is deliberately no `update_rule` action. Changing a rule means
    delete_rule followed by create_rule.
    """
    from ..connection import (
        find_resource_by_name_or_id,
        get_openstack_connection,
    )
    conn = get_openstack_connection()

    if action.lower() == 'list':
        groups = []
        for group in conn.network.security_groups():
            groups.append({
                'id': group.id,
                'name': group.name,
                'description': getattr(group, 'description', None),
                'stateful': getattr(group, 'stateful', None),
                'shared': getattr(group, 'is_shared', False),
                'project_id': getattr(group, 'project_id', None),
                'rule_count': len(getattr(group, 'security_group_rules', []) or []),
            })
        return {
            'success': True,
            'security_groups': groups,
            'message': f'Found {len(groups)} security group(s)',
        }

    if action.lower() == 'show':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for show action'}
        group = find_resource_by_name_or_id(
            conn.network.security_groups(), security_group_name, 'Security group')
        if not group:
            return {
                'success': False,
                'message': f'Security group "{security_group_name}" not found or not accessible in current project',
            }
        rules = []
        for rule in (getattr(group, 'security_group_rules', None) or []):
            rules.append(_format_sg_rule(rule))
        return {
            'success': True,
            'security_group': {
                'id': group.id,
                'name': group.name,
                'description': getattr(group, 'description', None),
                'stateful': getattr(group, 'stateful', None),
                'shared': getattr(group, 'is_shared', False),
                'project_id': getattr(group, 'project_id', None),
                'rules': rules,
            },
            'message': f'Security group {group.name} retrieved',
        }

    if action.lower() == 'list_rules':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for list_rules'}
        group = find_resource_by_name_or_id(
            conn.network.security_groups(), security_group_name, 'Security group')
        if not group:
            return {
                'success': False,
                'message': f'Security group "{security_group_name}" not found or not accessible in current project',
            }
        rules = [_format_sg_rule(r) for r in (conn.network.security_group_rules(security_group_id=group.id))]
        return {
            'success': True,
            'rules': rules,
            'message': f'Found {len(rules)} rule(s) in security group {group.name}',
        }

    if action.lower() == 'create':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for create action'}
        create_params = {'name': security_group_name}
        if 'description' in kwargs:
            create_params['description'] = kwargs['description']
        if 'stateful' in kwargs:
            create_params['stateful'] = kwargs['stateful']
        group = conn.network.create_security_group(**create_params)
        return {
            'success': True,
            'security_group': {'id': group.id, 'name': group.name},
            'message': f'Security group {group.name} created',
        }

    if action.lower() == 'set':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for set action'}
        group = find_resource_by_name_or_id(
            conn.network.security_groups(), security_group_name, 'Security group')
        if not group:
            return {
                'success': False,
                'message': f'Security group "{security_group_name}" not found or not accessible in current project',
            }
        update_params = {}
        new_name = kwargs.get('new_name') or kwargs.get('name')
        if new_name:
            update_params['name'] = new_name
        if 'description' in kwargs:
            update_params['description'] = kwargs['description']
        if not update_params:
            return {
                'success': False,
                'message': 'No update parameters provided (new_name, description)',
            }
        group = conn.network.update_security_group(group, **update_params)
        return {
            'success': True,
            'security_group': {'id': group.id, 'name': group.name},
            'message': f'Security group {security_group_name} updated',
        }

    if action.lower() == 'delete':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for delete action'}
        group = find_resource_by_name_or_id(
            conn.network.security_groups(), security_group_name, 'Security group')
        if not group:
            return {
                'success': False,
                'message': f'Security group "{security_group_name}" not found or not accessible in current project',
            }
        conn.network.delete_security_group(group)
        return {'success': True, 'message': f'Security group {security_group_name} deleted'}

    if action.lower() == 'create_rule':
        if not security_group_name:
            return {'success': False, 'message': 'security_group_name is required for create_rule'}
        group = find_resource_by_name_or_id(
            conn.network.security_groups(), security_group_name, 'Security group')
        if not group:
            return {
                'success': False,
                'message': f'Security group "{security_group_name}" not found or not accessible in current project',
            }
        direction = kwargs.get('direction')
        if not direction:
            return {
                'success': False,
                'message': 'direction is required for create_rule (ingress or egress)',
            }
        if direction not in ('ingress', 'egress'):
            # Neutron would reject this, but with an opaque 400. Catch it here
            # so the caller learns the allowed values.
            return {
                'success': False,
                'message': f'Invalid direction "{direction}"; must be ingress or egress',
            }
        rule_params = {
            'security_group_id': group.id,
            'direction': direction,
        }
        optional = ('description', 'ether_type', 'port_range_min',
                    'port_range_max', 'protocol', 'remote_ip_prefix',
                    'remote_group_id')
        for key in optional:
            if kwargs.get(key) is not None:
                rule_params[key] = kwargs[key]
        if not rule_params.get('protocol'):
            return {'success': False, 'message': 'protocol is required for create_rule'}
        if not (rule_params.get('port_range_min') is not None
                and rule_params.get('port_range_max') is not None):
            return {
                'success': False,
                'message': 'port_range_min and port_range_max are both required for create_rule',
            }
        if rule_params['port_range_min'] > rule_params['port_range_max']:
            return {
                'success': False,
                'message': f'Invalid port range: port_range_min '
                           f'({rule_params["port_range_min"]}) must not exceed '
                           f'port_range_max ({rule_params["port_range_max"]})',
            }
        rule = conn.network.create_security_group_rule(**rule_params)
        return {
            'success': True,
            'rule': _format_sg_rule(rule),
            'message': f'{rule_params["direction"]} rule created in security group {group.name}',
        }

    if action.lower() == 'delete_rule':
        rule_ref = kwargs.get('rule_id') or kwargs.get('rule_name')
        if not rule_ref:
            return {'success': False, 'message': 'rule_id is required for delete_rule'}
        rule = find_resource_by_name_or_id(
            conn.network.security_group_rules(), rule_ref, 'Security group rule')
        if not rule:
            return {
                'success': False,
                'message': f'Security group rule "{rule_ref}" not found or not accessible in current project',
            }
        conn.network.delete_security_group_rule(rule)
        return {
            'success': True,
            'message': f'Security group rule {rule_ref} deleted',
        }

    return {
        'success': False,
        'message': f'Unknown action "{action}". Supported: list, show, list_rules, '
                   f'create, set, delete, create_rule, delete_rule',
    }


def _format_sg_rule(rule) -> Dict[str, Any]:
    """Render a SecurityGroupRule, tolerating the list-summary dict form."""
    if isinstance(rule, dict):
        return {
            'id': rule.get('id'),
            'direction': rule.get('direction'),
            'ether_type': rule.get('ether_type'),
            'protocol': rule.get('protocol'),
            'port_range_min': rule.get('port_range_min'),
            'port_range_max': rule.get('port_range_max'),
            'remote_ip_prefix': rule.get('remote_ip_prefix'),
            'description': rule.get('description'),
        }
    return {
        'id': getattr(rule, 'id', None),
        'direction': getattr(rule, 'direction', None),
        'ether_type': getattr(rule, 'ether_type', None),
        'protocol': getattr(rule, 'protocol', None),
        'port_range_min': getattr(rule, 'port_range_min', None),
        'port_range_max': getattr(rule, 'port_range_max', None),
        'remote_ip_prefix': getattr(rule, 'remote_ip_prefix', None),
        'description': getattr(rule, 'description', None),
    }
