"""Tool implementation for set_network_agents."""

import json
from ..functions import set_network_agents as _set_network_agents
from ..mcp_main import (
    _is_modify_operation_allowed,
    conditional_tool,
)

@conditional_tool
async def set_network_agents(
    action: str,
    agent_id: str = "",
    network_id: str = "",
    router_id: str = "",
    admin_state_up: bool = True,
    description: str = ""
) -> str:
    """
    Manage OpenStack network agents (L2/L3/DHCP) and their service bindings.

    Args:
        action: Action to perform - list, show, set, delete,
                add_dhcp_to_network, remove_dhcp_from_network,
                add_router_to_agent, remove_router_from_agent, list_agent_routers
        agent_id: ID or hostname of the network agent (required for all but list)
        network_id: Name or ID of a network (for the DHCP binding actions)
        router_id: Name or ID of a router (for the L3 agent scheduling actions)
        admin_state_up: Whether the agent should run (for the set action)
        description: Agent description (for the set action)

    Returns:
        JSON string with network agent management operation results
    """

    if not _is_modify_operation_allowed() and action.lower() in [
        'set', 'delete', 'add_dhcp_to_network', 'remove_dhcp_from_network',
        'add_router_to_agent', 'remove_router_from_agent'
    ]:
        return json.dumps({
            'success': False,
            'message': f'Modify operations are not allowed in current environment for action: {action}',
            'error': f'MODIFY_OPERATIONS_DISABLED'
        })
    
    try:
        kwargs = {}
        if network_id.strip():
            kwargs['network_id'] = network_id.strip()
        if router_id.strip():
            kwargs['router_id'] = router_id.strip()
        if action.lower() == 'set':
            kwargs['admin_state_up'] = admin_state_up
            if description.strip():
                kwargs['description'] = description.strip()
        result = _set_network_agents(
            action=action,
            agent_id=agent_id if agent_id else None,
            **kwargs
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            'success': False,
            'message': f'Failed to manage network agent: {str(e)}',
            'error': str(e)
        }, indent=2)
