"""Tool implementation for set_security_groups."""

import json
from ..functions import set_security_groups as _set_security_groups
from ..mcp_main import (
    _is_modify_operation_allowed,
    conditional_tool,
)

MODIFY_ACTIONS = [
    'create', 'set', 'delete', 'create_rule', 'delete_rule'
]


@conditional_tool
async def set_security_groups(
    action: str,
    security_group_name: str = "",
    direction: str = "ingress",
    ethertype: str = "IPv4",
    protocol: str = "",
    port_range_min: int = 0,
    port_range_max: int = 0,
    remote_ip_prefix: str = "",
    remote_group_id: str = "",
    rule_id: str = "",
    description: str = "",
    new_name: str = ""
) -> str:
    """
    Manage OpenStack security groups and their ingress/egress rules.

    Use this to open or close ports on a security group, which is required
    before any instance can be reached over SSH, HTTP, or any other protocol.

    Args:
        action: Action to perform - list, show, list_rules, create, set,
                delete, create_rule, delete_rule
        security_group_name: Name or ID of the security group
        direction: ingress or egress (for create_rule)
        ethertype: IPv4 or IPv6 (for create_rule, default IPv4)
        protocol: tcp, udp, icmp (for create_rule)
        port_range_min: Lowest port in the range (for create_rule)
        port_range_max: Highest port in the range (for create_rule)
        remote_ip_prefix: CIDR allowed to reach the port, e.g. 0.0.0.0/0
        remote_group_id: Another security group allowed to reach the port
        rule_id: ID or name of the rule to remove (for delete_rule)
        description: Description for the group or the new rule
        new_name: New name (for the set action)

    Note:
        Neutron security group rules are immutable - there is no update_rule
        action. To change a rule, delete_rule it and create_rule the replacement.

    Returns:
        JSON string with security group management results
    """
    if not _is_modify_operation_allowed() and action.lower() in MODIFY_ACTIONS:
        return json.dumps({
            'success': False,
            'message': f'Modify operations are not allowed in current environment for action: {action}',
            'error': 'MODIFY_OPERATIONS_DISABLED'
        })

    try:
        kwargs = {}
        for key, value in (
            ('rule_id', rule_id),
            ('new_name', new_name),
        ):
            if value:
                kwargs[key] = value
        # description is meaningful for create/create_rule and set; forward
        # whenever supplied.
        if description:
            kwargs['description'] = description
        # Rule-specific fields only matter for create_rule; sending them on
        # other actions would be ignored at best.
        if action.lower() == 'create_rule':
            kwargs['direction'] = direction
            kwargs['ether_type'] = ethertype
            for key, value in (
                ('protocol', protocol),
                ('remote_ip_prefix', remote_ip_prefix),
                ('remote_group_id', remote_group_id),
            ):
                if value:
                    kwargs[key] = value
        # Neutron rejects explicit nulls; only send bounds that were set
        if port_range_min:
            kwargs['port_range_min'] = port_range_min
        if port_range_max:
            kwargs['port_range_max'] = port_range_max

        result = _set_security_groups(
            action=action,
            security_group_name=security_group_name if security_group_name else None,
            **kwargs
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            'success': False,
            'message': f'Failed to manage security group: {str(e)}',
            'error': str(e)
        }, indent=2)
