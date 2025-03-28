#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
集中导入模块 - 整合所有需要的导入，减少导入冲突
"""

# 从 src.agent_runners 导入Agent运行器
from src.agent_runners import run_custom_agent, run_org_agent

# 从 src.globals 导入全局变量
from src.globals import (
    _global_agent,
    _global_agent_state,
    _global_browser,
    _global_browser_context,
    _last_known_takeover_time,
)

# 从 src.ui.themes 导入主题
from src.ui.themes import theme_map

# 从 src.ui.ui_handlers 导入所有UI处理函数
from src.ui.ui_handlers import (
    check_takeover_requests,
    close_global_browser,
    finish_browser_control,
    run_deep_search,
    run_with_stream,
    stop_agent,
    stop_research_agent,
    take_browser_control,
)

# 从 src.utils 导入配置相关
from src.utils.default_config_settings import (
    default_config,
    load_config_from_file,
    save_config_to_file,
    save_current_config,
    update_ui_from_config,
)

# 从 src.utils 导入环境变量工具
from src.utils.env_utils import resolve_sensitive_env_variables

# 从 src.utils 导入工具函数
from src.utils.utils import (
    MissingAPIKeyError,
    capture_screenshot,
    get_latest_files,
    update_model_dropdown,
)
