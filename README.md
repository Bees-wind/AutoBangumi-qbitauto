
# AutoBangumi-qbitauto

本项目基于EstrellaXD/Auto_Bangumi - release 3.1.18开发，用于实现在windows平台本地部署时的qbittorrent下载器自动唤起。

AutoBangumi项目地址：https://github.com/EstrellaXD/Auto_Bangumi

Release：https://github.com/EstrellaXD/Auto_Bangumi/releases/tag/3.1.18

## 项目特性

- 启动AutoBangumi时会自动唤起qbittorrent
- 添加了托盘图标，右键托盘图标有以下三个选项：
  - 打开webui，
  - 选择退出时是否同时关闭qbittorrent
  - 退出AutoBangumi

## 使用说明

### 1.下载Auto_Bangumi - release 3.1.18 - app-v3.1.18.zip并解压

https://github.com/EstrellaXD/Auto_Bangumi/releases/download/3.1.18/app-v3.1.18.zip

安装原项目依赖

### 2.下载本项目

```
git clone https://github.com/Bees-wind/AutoBangumi-qbitauto.git
```

### 3.替换文件

替换src/main.py

将app.ico和app.png移动至/src

将qbitpath.json移动至/src/config

修改qbitpath.json，path改成qbittorrent.exe的地址：

```json
{
    "path": "\\path\\to\\qbittorrent.exe",
    "exit_close_qbit": true
}
```

## 4.依赖安装

安装本项目依赖

```
pip install -r requirements_2.txt
```

## 5.启动

```
python main.py
```

## 6.（可选）打包成.exe

```
pip install pyinstaller
pyinstaller build.spec
```
打包的exe可以在/dist下找到

## 声明

本项目包含由GPT-5 生成的代码。
