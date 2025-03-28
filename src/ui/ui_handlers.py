#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import glob
import logging
import os
import traceback

import gradio as gr

from src.globals import (
    _global_agent,
    _global_agent_state,
    _global_browser,
    _global_browser_context,
    _last_known_takeover_time,
)
from src.utils.env_utils import resolve_sensitive_env_variables
from src.utils.utils import MissingAPIKeyError, capture_screenshot, get_latest_files

logger = logging.getLogger(__name__)

async def stop_agent():
    """Request the agent to stop and update UI with enhanced feedback"""
    global _global_agent

    try:
        if _global_agent is not None:
            # Request stop
            _global_agent.stop()
        # Update UI immediately
        message = "Stop requested - the agent will halt at the next safe point"
        logger.info(f"🛑 {message}")

        # Return UI updates
        return (
            gr.update(value="Stopping...", interactive=False),  # stop_button
            gr.update(interactive=False),  # run_button
        )
    except Exception as e:
        error_msg = f"Error during stop: {str(e)}"
        logger.error(error_msg)
        return (
            gr.update(value="Stop", interactive=True),
            gr.update(interactive=True)
        )


async def stop_research_agent():
    """Request the agent to stop and update UI with enhanced feedback"""
    global _global_agent_state

    try:
        # Request stop
        _global_agent_state.request_stop()

        # Update UI immediately
        message = "Stop requested - the agent will halt at the next safe point"
        logger.info(f"🛑 {message}")

        # Return UI updates
        return (  # errors_output
            gr.update(value="Stopping...", interactive=False),  # stop_button
            gr.update(interactive=False),  # run_button
        )
    except Exception as e:
        error_msg = f"Error during stop: {str(e)}"
        logger.error(error_msg)
        return (
            gr.update(value="Stop", interactive=True),
            gr.update(interactive=True)
        )


async def close_global_browser():
    global _global_browser, _global_browser_context

    if _global_browser_context:
        await _global_browser_context.close()
        _global_browser_context = None

    if _global_browser:
        await _global_browser.close()
        _global_browser = None


# 检查用户接管状态的函数
def check_takeover_requests():
    global _global_agent_state, _last_known_takeover_time
    
    if not _global_agent_state:
        return (
            gr.update(),  # take_control_button
            gr.update(),  # finish_control_button
            gr.update(),  # user_control_status
            gr.update()   # vnc_modal
        )
    
    # 检查当前状态
    is_active = _global_agent_state.is_user_control_active()
    last_time = _global_agent_state.get_last_takeover_time()
    
    # 检测新的接管请求（状态为活跃且时间戳更新了）
    new_request = is_active and last_time > _last_known_takeover_time
    
    if new_request:
        # 更新已知的最后接管时间
        _last_known_takeover_time = last_time
        
        # 创建VNC链接
        vnc_url = "http://127.0.0.1:8080/index.html"
        
        # 创建提示弹窗
        takeover_html = f"""
        <div class="vnc-popup" id="vnc-popup">
            <div class="vnc-content">
                <div class="vnc-header">
                    <h3 style="margin:0; color:#333;">⚠️ LLM请求用户接管浏览器</h3>
                    <p style="margin:10px 0 0; color:#666;">AI已请求您临时接管浏览器控制权，可能需要您完成登录或其他敏感操作</p>
                </div>
                <button class="close-button" onclick="document.getElementById('vnc-popup').style.display='none';">关闭窗口</button>
                <iframe class="vnc-iframe" src="{vnc_url}"></iframe>
            </div>
        </div>
        """
        
        logger.info("检测到LLM触发的用户接管请求，显示接管提示")
        
        return (
            gr.update(interactive=False),  # take_control_button
            gr.update(interactive=True),   # finish_control_button
            "当前状态：LLM请求用户接管 - 请在弹出窗口中完成所需操作后点击'完成操作'按钮",  # user_control_status
            takeover_html  # vnc_modal
        )
    elif is_active:
        # 接管状态继续，但不是新请求
        return (
            gr.update(interactive=False),  # take_control_button
            gr.update(interactive=True),   # finish_control_button
            "当前状态：用户接管模式中",  # user_control_status
            gr.update()  # vnc_modal 不更新
        )
    else:
        # 非接管状态
        return (
            gr.update(interactive=True),   # take_control_button
            gr.update(interactive=False),  # finish_control_button
            "当前状态：Agent自动操作中",  # user_control_status
            """<div style="display:none"></div>"""  # 隐藏VNC
        )


# 用户接管浏览器
def take_browser_control():
    global _global_agent_state, _last_known_takeover_time
    
    # 设置状态
    _global_agent_state.set_user_control_active(True)
    # 更新已知的最后接管时间
    _last_known_takeover_time = _global_agent_state.get_last_takeover_time()
    
    # 创建新窗口链接
    vnc_url = "http://127.0.0.1:8080/index.html"
    
    # 显示VNC窗口 - 使用HTML直接嵌入iframe
    vnc_html = f"""
    <div class="vnc-popup" id="vnc-popup">
        <div class="vnc-content">
            <div class="vnc-header">
                <h3 style="margin:0; color:#333;">浏览器接管模式</h3>
                <p style="margin:10px 0 0; color:#666;">请在下方窗口中完成需要的操作，操作完成后点击"完成操作"按钮</p>
            </div>
            <button class="close-button" onclick="document.getElementById('vnc-popup').style.display='none';">关闭窗口</button>
            <iframe class="vnc-iframe" src="{vnc_url}"></iframe>
        </div>
    </div>
    """
    
    return (
        gr.update(interactive=False),  # take_control_button
        gr.update(interactive=True),  # finish_control_button
        "当前状态：用户接管模式 - 请在弹出窗口中完成操作",  # user_control_status
        vnc_html  # vnc_modal
    )


# 用户完成操作
def finish_browser_control():
    logger.info("用户完成操作")
    global _global_agent_state

    # 重置用户接管状态
    _global_agent_state.set_user_control_active(False)
    
    # 隐藏VNC窗口
    vnc_html = """
    <div style="display:none"></div>
    """
    
    # 显示成功提示
    success_message = """
    <div id="success-message" style="padding:10px; background-color:#e6f7e6; border-left:4px solid #4caf50; margin:10px 0; display:flex; align-items:center;">
        <span style="font-size:20px; margin-right:10px;">✅</span>
        <span>操作已完成，控制权已交还给AI助手</span>
    </div>
    <script>
        setTimeout(function() {
            document.getElementById('success-message').style.display = 'none';
        }, 5000);
    </script>
    """
    
    return (
        gr.update(interactive=True),  # take_control_button
        gr.update(interactive=False),  # finish_control_button
        success_message,  # user_control_status - 用HTML替换了纯文本
        vnc_html  # vnc_modal
    )


async def run_browser_agent(
        agent_type,
        llm_provider,
        llm_model_name,
        llm_num_ctx,
        llm_temperature,
        llm_base_url,
        llm_api_key,
        use_own_browser,
        keep_browser_open,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        save_agent_history_path,
        save_trace_path,
        enable_recording,
        task,
        add_infos,
        max_steps,
        use_vision,
        max_actions_per_step,
        tool_calling_method,
        chrome_cdp,
        max_input_tokens
):
    try:
        # Disable recording if the checkbox is unchecked
        if not enable_recording:
            save_recording_path = None

        # Ensure the recording directory exists if recording is enabled
        if save_recording_path:
            os.makedirs(save_recording_path, exist_ok=True)

        # Get the list of existing videos before the agent runs
        existing_videos = set()
        if save_recording_path:
            existing_videos = set(
                glob.glob(os.path.join(save_recording_path, "*.[mM][pP]4"))
                + glob.glob(os.path.join(save_recording_path, "*.[wW][eE][bB][mM]"))
            )

        task = resolve_sensitive_env_variables(task)

        # Run the agent
        from src.utils import utils
        llm = utils.get_llm_model(
            provider=llm_provider,
            model_name=llm_model_name,
            num_ctx=llm_num_ctx,
            temperature=llm_temperature,
            base_url=llm_base_url,
            api_key=llm_api_key,
        )
        
        from src.agent_runners import run_custom_agent, run_org_agent
        
        if agent_type == "org":
            final_result, errors, model_actions, model_thoughts, trace_file, history_file = await run_org_agent(
                llm=llm,
                use_own_browser=use_own_browser,
                keep_browser_open=keep_browser_open,
                headless=headless,
                disable_security=disable_security,
                window_w=window_w,
                window_h=window_h,
                save_recording_path=save_recording_path,
                save_agent_history_path=save_agent_history_path,
                save_trace_path=save_trace_path,
                task=task,
                max_steps=max_steps,
                use_vision=use_vision,
                max_actions_per_step=max_actions_per_step,
                tool_calling_method=tool_calling_method,
                chrome_cdp=chrome_cdp,
                max_input_tokens=max_input_tokens
            )
        elif agent_type == "custom":
            final_result, errors, model_actions, model_thoughts, trace_file, history_file = await run_custom_agent(
                llm=llm,
                use_own_browser=use_own_browser,
                keep_browser_open=keep_browser_open,
                headless=headless,
                disable_security=disable_security,
                window_w=window_w,
                window_h=window_h,
                save_recording_path=save_recording_path,
                save_agent_history_path=save_agent_history_path,
                save_trace_path=save_trace_path,
                task=task,
                add_infos=add_infos,
                max_steps=max_steps,
                use_vision=use_vision,
                max_actions_per_step=max_actions_per_step,
                tool_calling_method=tool_calling_method,
                chrome_cdp=chrome_cdp,
                max_input_tokens=max_input_tokens
            )
        else:
            raise ValueError(f"Invalid agent type: {agent_type}")

        gif_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "agent_history.gif")

        return (
            final_result,
            errors,
            model_actions,
            model_thoughts,
            gif_path,
            trace_file,
            history_file,
            gr.update(value="Stop", interactive=True),  # Re-enable stop button
            gr.update(interactive=True)  # Re-enable run button
        )

    except MissingAPIKeyError as e:
        logger.error(str(e))
        raise gr.Error(str(e), print_exception=False)

    except Exception as e:
        traceback.print_exc()
        errors = str(e) + "\n" + traceback.format_exc()
        return (
            '',  # final_result
            errors,  # errors
            '',  # model_actions
            '',  # model_thoughts
            None,  # latest_video
            None,  # history_file
            None,  # trace_file
            gr.update(value="Stop", interactive=True),  # Re-enable stop button
            gr.update(interactive=True)  # Re-enable run button
        )


async def run_with_stream(
        agent_type,
        llm_provider,
        llm_model_name,
        llm_num_ctx,
        llm_temperature,
        llm_base_url,
        llm_api_key,
        use_own_browser,
        keep_browser_open,
        headless,
        disable_security,
        window_w,
        window_h,
        save_recording_path,
        save_agent_history_path,
        save_trace_path,
        enable_recording,
        task,
        add_infos,
        max_steps,
        use_vision,
        max_actions_per_step,
        tool_calling_method,
        chrome_cdp,
        max_input_tokens
):
    global _global_agent

    stream_vw = 80
    stream_vh = int(80 * window_h // window_w)
    if not headless:
        result = await run_browser_agent(
            agent_type=agent_type,
            llm_provider=llm_provider,
            llm_model_name=llm_model_name,
            llm_num_ctx=llm_num_ctx,
            llm_temperature=llm_temperature,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            use_own_browser=use_own_browser,
            keep_browser_open=keep_browser_open,
            headless=headless,
            disable_security=disable_security,
            window_w=window_w,
            window_h=window_h,
            save_recording_path=save_recording_path,
            save_agent_history_path=save_agent_history_path,
            save_trace_path=save_trace_path,
            enable_recording=enable_recording,
            task=task,
            add_infos=add_infos,
            max_steps=max_steps,
            use_vision=use_vision,
            max_actions_per_step=max_actions_per_step,
            tool_calling_method=tool_calling_method,
            chrome_cdp=chrome_cdp,
            max_input_tokens=max_input_tokens
        )
        # Add HTML content at the start of the result array
        yield [gr.update(visible=False)] + list(result)
    else:
        try:
            # Run the browser agent in the background
            agent_task = asyncio.create_task(
                run_browser_agent(
                    agent_type=agent_type,
                    llm_provider=llm_provider,
                    llm_model_name=llm_model_name,
                    llm_num_ctx=llm_num_ctx,
                    llm_temperature=llm_temperature,
                    llm_base_url=llm_base_url,
                    llm_api_key=llm_api_key,
                    use_own_browser=use_own_browser,
                    keep_browser_open=keep_browser_open,
                    headless=headless,
                    disable_security=disable_security,
                    window_w=window_w,
                    window_h=window_h,
                    save_recording_path=save_recording_path,
                    save_agent_history_path=save_agent_history_path,
                    save_trace_path=save_trace_path,
                    enable_recording=enable_recording,
                    task=task,
                    add_infos=add_infos,
                    max_steps=max_steps,
                    use_vision=use_vision,
                    max_actions_per_step=max_actions_per_step,
                    tool_calling_method=tool_calling_method,
                    chrome_cdp=chrome_cdp,
                    max_input_tokens=max_input_tokens
                )
            )

            # Initialize values for streaming
            html_content = f"<h1 style='width:{stream_vw}vw; height:{stream_vh}vh'>Using browser...</h1>"
            final_result = errors = model_actions = model_thoughts = ""
            recording_gif = trace = history_file = None

            # Periodically update the stream while the agent task is running
            while not agent_task.done():
                try:
                    encoded_screenshot = await capture_screenshot(_global_browser_context)
                    if encoded_screenshot is not None:
                        html_content = f'<img src="data:image/jpeg;base64,{encoded_screenshot}" style="width:{stream_vw}vw; height:{stream_vh}vh ; border:1px solid #ccc;">'
                    else:
                        html_content = f"<h1 style='width:{stream_vw}vw; height:{stream_vh}vh'>Waiting for browser session...</h1>"
                except Exception as e:
                    html_content = f"<h1 style='width:{stream_vw}vw; height:{stream_vh}vh'>Waiting for browser session...</h1>"

                if _global_agent and _global_agent.state.stopped:
                    yield [
                        gr.HTML(value=html_content, visible=True),
                        final_result,
                        errors,
                        model_actions,
                        model_thoughts,
                        recording_gif,
                        trace,
                        history_file,
                        gr.update(value="Stopping...", interactive=False),  # stop_button
                        gr.update(interactive=False),  # run_button
                    ]
                    break
                else:
                    yield [
                        gr.HTML(value=html_content, visible=True),
                        final_result,
                        errors,
                        model_actions,
                        model_thoughts,
                        recording_gif,
                        trace,
                        history_file,
                        gr.update(),  # Re-enable stop button
                        gr.update()  # Re-enable run button
                    ]
                await asyncio.sleep(0.1)

            # Once the agent task completes, get the results
            try:
                result = await agent_task
                final_result, errors, model_actions, model_thoughts, recording_gif, trace, history_file, stop_button, run_button = result
            except gr.Error:
                final_result = ""
                model_actions = ""
                model_thoughts = ""
                recording_gif = trace = history_file = None

            except Exception as e:
                errors = f"Agent error: {str(e)}"

            yield [
                gr.HTML(value=html_content, visible=True),
                final_result,
                errors,
                model_actions,
                model_thoughts,
                recording_gif,
                trace,
                history_file,
                stop_button,
                run_button
            ]

        except Exception as e:
            traceback.print_exc()
            yield [
                gr.HTML(
                    value=f"<h1 style='width:{stream_vw}vw; height:{stream_vh}vh'>Waiting for browser session...</h1>",
                    visible=True),
                "",
                f"Error: {str(e)}\n{traceback.format_exc()}",
                "",
                "",
                None,
                None,
                None,
                gr.update(value="Stop", interactive=True),  # Re-enable stop button
                gr.update(interactive=True)  # Re-enable run button
            ]


async def run_deep_search(research_task, max_search_iteration_input, max_query_per_iter_input, llm_provider,
                          llm_model_name, llm_num_ctx, llm_temperature, llm_base_url, llm_api_key, use_vision,
                          use_own_browser, headless, chrome_cdp):
    from src.utils import utils
    from src.utils.deep_research import deep_research
    global _global_agent_state

    # Clear any previous stop request
    _global_agent_state.clear_stop()

    llm = utils.get_llm_model(
        provider=llm_provider,
        model_name=llm_model_name,
        num_ctx=llm_num_ctx,
        temperature=llm_temperature,
        base_url=llm_base_url,
        api_key=llm_api_key,
    )
    markdown_content, file_path = await deep_research(research_task, llm, _global_agent_state,
                                                      max_search_iterations=max_search_iteration_input,
                                                      max_query_num=max_query_per_iter_input,
                                                      use_vision=use_vision,
                                                      headless=headless,
                                                      use_own_browser=use_own_browser,
                                                      chrome_cdp=chrome_cdp
                                                      )

    return markdown_content, file_path, gr.update(value="Stop", interactive=True), gr.update(interactive=True) 