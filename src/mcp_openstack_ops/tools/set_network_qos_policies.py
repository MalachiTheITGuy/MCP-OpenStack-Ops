"""Tool implementation for set_network_qos_policies."""

import json
from ..functions import set_network_qos_policies as _set_network_qos_policies
from ..mcp_main import (
    _is_modify_operation_allowed,
    conditional_tool,
)

@conditional_tool
async def set_network_qos_policies(
    action: str,
    policy_name: str = "",
    description: str = "",
    shared: bool = False,
    new_name: str = "",
    rule_type: str = "",
    rule_name: str = "",
    direction: str = "",
    max_kbps: int = 0,
    max_burst_kbps: int = 0,
    dscp_mark: int = 0,
    min_kpps: int = 0
) -> str:
    """
    Manage OpenStack network QoS policies and the rules attached to them.

    Args:
        action: Action to perform - list, show, create, set, delete,
                list_rules, create_rule, delete_rule
        policy_name: Name or ID of the QoS policy
        description: Description for the QoS policy
        shared: Make policy available to other projects (default: False)
        new_name: New name (for the set action)
        rule_type: For the *_rule actions - bandwidth_limit, dscp_marking,
                   minimum_bandwidth, minimum_packet_rate, packet_rate_limit
        rule_name: Name or ID of the rule (delete_rule)
        direction: ingress or egress (create_rule)
        max_kbps: Ceiling in kbps (bandwidth_limit / packet_rate_limit)
        max_burst_kbps: Burst ceiling in kbps (bandwidth_limit)
        dscp_mark: DSCP mark value (dscp_marking)
        min_kpps: Minimum rate in kpps (minimum_packet_rate / minimum_bandwidth)

    Returns:
        JSON string with network QoS policy management operation results
    """

    if not _is_modify_operation_allowed() and action.lower() in [
        'create', 'set', 'delete', 'create_rule', 'delete_rule'
    ]:
        return json.dumps({
            'success': False,
            'message': f'Modify operations are not allowed in current environment for action: {action}',
            'error': f'MODIFY_OPERATIONS_DISABLED'
        })
    
    try:
        kwargs = {}
        if rule_type.strip():
            kwargs['rule_type'] = rule_type.strip()
        if rule_name.strip():
            kwargs['rule_name'] = rule_name.strip()
        if direction.strip():
            kwargs['direction'] = direction.strip()
        # Forward rule parameters only when the caller actually set them, so a
        # 0 never silently overwrites a real limit.
        if max_kbps:
            kwargs['max_kbps'] = max_kbps
        if max_burst_kbps:
            kwargs['max_burst_kbps'] = max_burst_kbps
        if dscp_mark:
            kwargs['dscp_mark'] = dscp_mark
        if min_kpps:
            kwargs['min_kpps'] = min_kpps

        result = _set_network_qos_policies(
            action=action,
            policy_name=policy_name if policy_name else None,
            description=description,
            shared=shared,
            new_name=new_name if new_name else None,
            **kwargs
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            'success': False,
            'message': f'Failed to manage network QoS policy: {str(e)}',
            'error': str(e)
        }, indent=2)
