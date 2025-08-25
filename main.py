import logging
import os
import sys
import threading
import signal
import webbrowser
from typing import Optional
from pathlib import Path

import qbittorrentapi
import psutil
import uvicorn
import pystray
import ctypes
import win32event
import win32api
from PIL import Image, ImageDraw
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from module.api import v1
from module.conf import VERSION, settings, setup_logger

from windows_toasts import WindowsToaster, Toast, ToastDisplayImage

import threading
import time
from typing import Optional

import json
from pathlib import Path

# 全局变量
server: Optional[uvicorn.Server] = None
exit_event = threading.Event()
shutdown_lock = threading.Lock()  # 防止重复关闭
is_shutting_down = False          # 关闭状态标志
tray_icon: Optional[pystray.Icon] = None  # 托盘图标引用
exit_with_qbit = True  # 控制退出时是否关闭qBittorrent

def load_qbit_config():
    """只读取 exit_close_qbit 字段"""
    config_path = Path("./config/qbitpath.json")
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("exit_close_qbit", True)  # 默认True
        return True  # 文件不存在时返回默认值
    except Exception as e:
        logger.warning(f"读取配置失败，使用默认值: {e}")
        return True

def save_qbit_config(exit_close_qbit: bool):
    """只更新 exit_close_qbit 字段"""
    config_path = Path("./config/qbitpath.json")
    try:
        # 先读取现有配置
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # 只更新目标字段
        config["exit_close_qbit"] = exit_close_qbit
        
        # 写入文件
        os.makedirs("./config", exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存配置失败: {e}")

def terminate_qbittorrent():
    # 读取配置文件
    with open('./config/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    dl_conf = config["downloader"]

    # 构造 host URL
    # 如果 ssl=true，则用 https://，否则用 http://
    protocol = "https" if dl_conf.get("ssl") else "http"
    host = f"{protocol}://{dl_conf['host']}"

    try:            
        # 创建客户端
        client = qbittorrentapi.Client(
            host=host,
            username=dl_conf.get("username", ""),
            password=dl_conf.get("password", "")
        )

        # 登录并关闭
        client.auth_log_in()
        client.app_shutdown()
        logger.info("已发送正常关闭指令给 qBittorrent。")
    except Exception as e:
        logger.error(e)
        logger.error("qBittorrent退出异常")
        return 3

    time.sleep(5)
    if not is_qbittorrent_running():
        logger.error("qBittorrent退出正常")
        return 0
    else :
        return 1


def create_tray_icon():
    global tray_icon, exit_with_qbit
    
    def create_default_image():
        """创建默认的白色图标作为备用"""
        image = Image.new('RGB', (64, 64), 'white')
        dc = ImageDraw.Draw(image)
        dc.rectangle([0, 0, 63, 63], outline='black')
        dc.text((10, 10), "AB", fill='black')  # AB for AutoBangumi
        return image

    def load_app_icon():
        """尝试加载应用程序图标"""
        try:
            # 使用Path对象处理路径更安全
            icon_path = Path(r"app.png")
            if icon_path.exists():
                image = Image.open(icon_path)
                # 调整大小到适合系统托盘的尺寸
                return image.resize((64, 64), Image.Resampling.LANCZOS)
            return create_default_image()
        except Exception as e:
            logger.warning(f"加载图标失败: {e}, 使用默认图标")
            return create_default_image()

    def on_open_web(icon, item):
        webbrowser.open(f"http://localhost:{settings.program.webui_port}")

    def on_quit(icon, item):
        initiate_shutdown()
        
    def on_toggle_qbit(icon, item):
        """切换退出时关闭qBittorrent的选项"""
        global exit_with_qbit
        exit_with_qbit = not exit_with_qbit

    # 创建菜单项
    menu_items = [
        pystray.MenuItem('打开控制面板', on_open_web),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            '退出时关闭 qBittorrent',
            on_toggle_qbit,
            checked=lambda item: exit_with_qbit,
            radio=False
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('退出 AutoBangumi', on_quit)
    ]
    
    # 加载图标
    icon_image = load_app_icon()
    
    tray_icon = pystray.Icon(
        "AutoBangumi", 
        icon=icon_image, 
        menu=pystray.Menu(*menu_items),
        title=f"AutoBangumi (端口: {settings.program.webui_port})"
    )
    
    return tray_icon

def initiate_shutdown():
    global is_shutting_down, tray_icon, exit_with_qbit
    
    with shutdown_lock:
        if is_shutting_down:  # 防止重复触发
            return
        is_shutting_down = True
    
    logger.info("收到退出请求，开始关闭流程...")
    
    def show_exit_notification(qbit_state):
        """显示退出通知"""
        try:
            toaster = WindowsToaster("AutoBangumi")
            toast = Toast()
            
            if qbit_state == 0:
                toast.text_fields = [
                    "♻️ AutoBangumi 已退出",
                    "qBittorrent 已关闭"
                ]
            else:
                if  qbit_state == 3:
                    toast.text_fields = [
                        "⏏️ AutoBangumi 已退出",
                        "❌ qBittorrent 退出异常"
                    ]
                else :
                    toast.text_fields = [
                        "⏏️ AutoBangumi 已退出",
                        "qBittorrent 仍保持运行"
                    ]
            
            # 添加图标（如果存在）
            icon_path = "app.ico" if os.path.exists("app.ico") else None
            if icon_path:
                try:
                    display_image = ToastDisplayImage.fromPath(icon_path)
                    toast.AddImage(display_image)
                except Exception as e:
                    logger.warning(f"加载退出通知图标失败: {e}")
            
            # 显示3秒后自动消失
            toast.expiration = 3000  
            toaster.show_toast(toast)
        except Exception as e:
            logger.error(f"显示退出通知失败: {e}")

    # 根据复选框状态决定是否关闭qBittorrent
    qbit_state = 1
    save_qbit_config(exit_with_qbit) 
    if is_qbittorrent_running():
        toaster = WindowsToaster("AutoBangumi")
        toast = Toast()
        toast.text_fields = [
            "等待qbittorrent退出"
        ]
        toast.expiration = 5000 
        toaster.show_toast(toast)

        if exit_with_qbit:
            logger.info("正在关闭qBittorrent...")
            qbit_state = terminate_qbittorrent()
    else :
        qbit_state = 0
    # 显示退出通知
    show_exit_notification(qbit_state)
    
    # 触发服务器关闭
    exit_event.set()
    if server:
        server.should_exit = True

    time.sleep(1)
    
    # 关闭托盘图标
    if tray_icon:
        logger.info("关闭托盘图标...")
        tray_icon.stop()
    
    # 强制退出程序
    logger.info("强制退出程序...")
    os._exit(0)

def signal_handler(sig, frame):
    logger.info(f"接收到信号 {sig}，正在优雅退出...")
    initiate_shutdown()

def run_server():
    global server, is_shutting_down

    if os.getenv("IPV6"):
        host = "::"
    else:
        host = os.getenv("HOST", "0.0.0.0")
    
    config = uvicorn.Config(
        app,
        host=host,
        port=settings.program.webui_port,
        log_config=uvicorn_logging_config,
        lifespan="on",  # 确保生命周期事件可用
    )
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except Exception as e:
        logger.error(f"服务器错误: {e}")
    finally:
        logger.info("服务器已完全停止")
        initiate_shutdown()

# 原有的 FastAPI 应用代码保持不变
setup_logger(reset=True)
logger = logging.getLogger(__name__)
uvicorn_logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": logger.handlers,
    "loggers": {
        "uvicorn": {
            "level": logger.level,
        },
        "uvicorn.access": {
            "level": "WARNING",
        },
    },
}

def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(v1, prefix="/api")
    return app

app = create_app()

@app.get("/posters/{path:path}", tags=["posters"])
def posters(path: str):
    return FileResponse(f"data/posters/{path}")

if VERSION != "DEV_VERSION":
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
    app.mount("/images", StaticFiles(directory="dist/images"), name="images")
    templates = Jinja2Templates(directory="dist")

    @app.get("/{path:path}")
    def html(request: Request, path: str):
        files = os.listdir("dist")
        if path in files:
            return FileResponse(f"dist/{path}")
        else:
            context = {"request": request}
            return templates.TemplateResponse("index.html", context)
else:
    @app.get("/", status_code=302, tags=["html"])
    def index():
        return RedirectResponse("/docs")
    
def is_qbittorrent_running():
    """检查 qBittorrent 是否正在运行"""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == 'qbittorrent.exe':
            return True
    return False

# 新增函数：处理 qBittorrent 路径配置
def get_qbit_path():
    """从配置文件获取 qBittorrent 路径"""
    config_path = Path("./config/qbitpath.json")
    default_path = r"C:\Program Files\qBittorrent\qbittorrent.exe"
    
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                path = data.get('path', '').strip()
                if path and Path(path).exists():
                    return path
        return default_path if Path(default_path).exists() else None
    except Exception as e:
        logger.warning(f"读取qBittorrent路径配置失败: {e}")
        return None

def start_qbittorrent():
    """尝试启动 qBittorrent"""
    qbit_path = get_qbit_path()
    if not qbit_path:
        return False
    
    try:
        os.startfile(qbit_path)
        logger.info(f"已尝试启动 qBittorrent: {qbit_path}")
        return True
    except Exception as e:
        logger.error(f"启动 qBittorrent 失败: {e}")
        return False

# 修改通知函数
def show_autobangumi_notification():
    icon_ab = "app.ico" if os.path.exists("app.ico") else None
    AUTOBANGUMI_PORT = settings.program.webui_port
    AUTOBANGUMI_URL = f"http://localhost:{AUTOBANGUMI_PORT}"

    toaster = WindowsToaster("AutoBangumi")
    toast = Toast()

    def add_icon(toast_obj, icon_path):
        if icon_path and os.path.exists(icon_path):
            try:
                display_image = ToastDisplayImage.fromPath(icon_path)
                toast_obj.AddImage(display_image)
            except Exception as e:
                logger.warning(f"加载图标失败: {e}")

    # 初始通知
    if is_qbittorrent_running():
        toast.text_fields = [
            "✅ AutoBangumi 已就绪",
            f"点击打开控制面板 (端口: {AUTOBANGUMI_PORT})"
        ]
        toast.on_activated = lambda _: webbrowser.open(AUTOBANGUMI_URL)
    else:
        toast.text_fields = [
            "🔄 正在尝试启动 qBittorrent"
        ]
        start_qbittorrent()
        toast.expiration = 1000  
        toaster.show_toast(toast)  # 先显示"正在启动"通知
        
        # 同步延迟检测（替代多线程）
        time.sleep(1)
        if is_qbittorrent_running():
            toast.text_fields = [
                "✅ qBittorrent 已启动",
                "✅ AutoBangumi 已就绪",
                f"点击打开控制面板 (端口: {AUTOBANGUMI_PORT})"
            ]
            toast.on_activated = lambda _: webbrowser.open(AUTOBANGUMI_URL)
        else:
            toast.text_fields = [
                "❌ qBittorrent 启动失败",
                "请检查配置或手动启动"
            ]
    toast.expiration = 3000
    add_icon(toast, icon_ab)
    toaster.show_toast(toast)  # 最终显示状态通知

if __name__ == "__main__":

    exit_with_qbit = load_qbit_config()  # 程序启动时加载
    
    # 显示启动通知
    try:
        show_autobangumi_notification()
    except Exception as e:
        logger.warning(f"无法显示启动通知: {e}")
        
    mutex = win32event.CreateMutex(None, False, "AutoBangumi_Mutex_1234")  # 唯一名称
    if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("程序已在运行，请勿重复启动！")
        sys.exit(0)
        # 隐藏控制台窗口（任务栏不显示）

    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)  # 0 = SW_HIDE
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill命令
    
    # 启动系统托盘图标
    tray_icon = create_tray_icon()
    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()
    
    # 启动服务器
    run_server()
    
    # 等待退出事件
    exit_event.wait()
    logger.info("应用程序退出完成")
