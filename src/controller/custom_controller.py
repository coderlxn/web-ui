import asyncio
import logging
import pdb
from typing import Optional, Type

import pyperclip
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller, DoneAction
from browser_use.controller.views import (
    ClickElementAction,
    DoneAction,
    ExtractPageContentAction,
    GoToUrlAction,
    InputTextAction,
    OpenTabAction,
    ScrollAction,
    SearchGoogleAction,
    SendKeysAction,
    SwitchTabAction,
)
from main_content_extractor import MainContentExtractor
from pydantic import BaseModel

from src.utils.agent_state import AgentState

logger = logging.getLogger(__name__)

class CustomController(Controller):
    def __init__(self, exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self._register_custom_actions()
        self.agent_state = AgentState()

    def _register_custom_actions(self):
        """Register all custom browser actions"""

        @self.registry.action("Copy text to clipboard")
        def copy_to_clipboard(text: str):
            pyperclip.copy(text)
            return ActionResult(extracted_content=text)

        @self.registry.action("Paste text from clipboard")
        async def paste_from_clipboard(browser: BrowserContext):
            text = pyperclip.paste()
            # send text to browser
            page = await browser.get_current_page()
            await page.keyboard.type(text)

            return ActionResult(extracted_content=text)

        @self.registry.action("take over browser")
        async def take_over_browser():
            """暂停自动操作，让用户接管浏览器控制权"""
            # 设置状态表示用户接管开始
            self.agent_state.set_user_control_active(True)
            
            logger.info("浏览器控制权已交给用户，等待用户操作...")
            
            # 等待用户完成操作
            while self.agent_state.is_user_control_active():
                logger.info(f"用户接管状态: {self.agent_state.is_user_control_active()}")
                await asyncio.sleep(0.5)  # 每0.5秒检查一次状态
            
            # 重置状态
            self.agent_state.set_user_control_active(False)
            
            return ActionResult(
                extracted_content="用户操作已完成，LLM Agent继续执行。"
            )
    
    def is_user_in_control(self):
        """检查当前是否由用户控制浏览器"""
        return self.agent_state.is_user_control_active()
    
    def finish_user_control(self):
        """用户操作完成，标记状态"""
        self.agent_state.set_user_control_active(False)
