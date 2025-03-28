#!/usr/bin/env python
# -*- coding: utf-8 -*-

from src.utils.agent_state import AgentState

# Global variables for persistence
_global_browser = None
_global_browser_context = None
_global_agent = None
_last_known_takeover_time = 0  # 记录前端已知的最后接管时间

# Create the global agent state instance
_global_agent_state = AgentState() 