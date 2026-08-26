# dsh-pet-lulu 🐹 水豚噜噜桌宠

> [English](README.en.md) | **简体中文**

一个为 DeepSeek Harness（dsh）打造的可爱水豚桌面宠物插件，支持**三种渲染模式**：

* **web 宠物（默认）**：浏览器页面里的浮动宠物，可拖动、点击摸头、喂食、
  睡眠，带状态气泡——`python -m dsh_pet` 直接打开浏览器页面；
* **终端宠物（ANSI）**：在终端里用真彩色半块字符（ANSI）渲染动画，
  按键交互（`--renderer ansi`）；
* **窗口宠物（Tk）**：独立 Tkinter 窗口，鼠标交互（`--gui`）。

> 形象素材来自 [czy666chen/lulu](https://github.com/czy666chen/lulu)（MIT）
> 与 [srwang0506/HatchPet-CapybaraLulu](https://github.com/srwang0506/HatchPet-CapybaraLulu)
> （Apache-2.0）。素材来源与许可详见 [`dsh_pet/assets/SOURCES.md`](dsh_pet/assets/SOURCES.md)。

![预览](docs/preview.gif)

---

## 目录

1. [功能](#功能)
2. [安装](#安装)
3. [模式选择](#模式选择)
4. [web 模式（默认）](#web-模式默认)
5. [终端模式（ANSI）](#终端模式ansi)
6. [窗口模式（Tk）](#窗口模式tk)
7. [dsh 集成](#dsh-集成)
8. [配置文件](#配置文件)
9. [键盘 / 鼠标交互汇总](#键盘--鼠标交互汇总)
10. [测试](#测试)
11. [项目结构](#项目结构)
12. [素材来源与许可](#素材来源与许可)
13. [常见问题（FAQ）](#常见问题faq)
14. [验收对照](#验收对照)

---

## 功能

* **动画系统**：待机呼吸/眨眼循环、随机动作（行走、跳跃、打哈欠、环视）；
  帧率可配置（默认 10 FPS），帧循环节流，目标 CPU 占用 <5% 单核。
* **交互**：
  * web 模式：点击摸头、拖动换位置（位置记忆）、悬停面板（喂食/睡眠/隐藏）、
    召唤按钮、键盘 `f/p/s/h/q`；
  * 终端模式：键盘 `f` 喂食、`p` 抚摸、`s` 睡觉/唤醒、`q` 退出；
  * 窗口模式（Tk）：鼠标点击触发随机反应；
  * 一次性动画：按键/点击反应播放一次后自动回到待机。
* **状态气泡**：宠物上方气泡显示 dsh 任务状态（任务名、进度条、GPU 温度）。
  默认内置模拟数据源，预留真实 dsh 数据接口。
* **三种渲染 / 两种形象**：`web`（默认）/ `ansi` / `tk`；
  `pet_type = lulu | capybara` 切换。

## 安装

环境要求：Python 3.8+。精灵表解析需要 [Pillow](https://pypi.org/project/Pillow/)
（可选依赖——没有它时终端宠物会退化为内置 ASCII 像素形象；web 模式需要
Pillow 生成精灵图条）。

```sh
# 推荐：从源码目录安装（含 Pillow）
pip install -e ".[sprites]"

# 或仅装核心（无 Pillow）
pip install -e .
```

不安装也可以直接运行（仓库根目录下）：

```sh
python -m dsh_pet            # 或 bin/dsh-pet（Windows: bin\dsh-pet.cmd）
```

安装 dsh 插件（可选，见 [dsh 集成](#dsh-集成)）：

```sh
dsh plugin --profile pet add <本仓库>/plugins
```

## 模式选择

| 模式 | 命令 | 说明 |
| --- | --- | --- |
| **web（默认）** | `python -m dsh_pet` | 打开浏览器宠物页（`http://127.0.0.1:8765`） |
| 终端 | `python -m dsh_pet --renderer ansi` | 终端 TUI，全屏动画 |
| 窗口 | `python -m dsh_pet --gui` | Tkinter 独立窗口 |

`--renderer` 取值：`auto`（等同 web）/ `ansi` / `tk` / `web`。
配置文件里用 `[renderer] mode = web | ansi | tk | auto` 持久化选择。

## web 模式（默认）

### 启动

```sh
python -m dsh_pet                        # 打开浏览器（默认 8765 端口）
python -m dsh_pet --no-browser           # 只起服务不弹浏览器（供远程/测试）
python -m dsh_pet --port 9000            # 换端口
python -m dsh_pet --pet-type capybara    # 换水豚高清帧形象
python -m dsh_pet --fps 15               # 帧率
python -m dsh_pet --status-source file --status-file /path/status.json
```

### 页面操作

* **点击宠物** → 摸头（气泡反馈，一次性动画）
* **拖动宠物** → 换位置（自动记忆，localStorage）
* **悬停宠物** → 弹出面板：`喂食` / `睡觉` / `隐藏`
* **隐藏后** → 右下角出现「召唤宠物」按钮
* **键盘**：`f` 喂食 · `p` 抚摸 · `s` 睡觉/唤醒 · `h` 隐藏 · `q` 关闭页面
* **状态气泡**：实时显示 dsh 任务名、进度条、GPU 温度（默认 mock 数据）

### HTTP API（供脚本/其他应用调用）

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 宠物页面 |
| `/api/manifest` | GET | 宠物清单（图集几何、各动画轨道） |
| `/api/state` | GET | 实时状态（行为/动画/气泡/可见性/睡眠） |
| `/api/sheet/<clip>.png` | GET | 某个动画片段（clip）的精灵条图片 |
| `/api/interact` | POST | `{"kind":"pet"|"feed"}` 摸头/喂食 |
| `/api/sleep` | POST | 睡觉/唤醒切换 |
| `/api/random` | POST | 触发一次随机动作 |
| `/api/hide` / `/api/summon` | POST | 隐藏 / 召唤 |
| `/api/quit` | POST | 关闭服务并退出 |

## 终端模式（ANSI）

```sh
python -m dsh_pet --renderer ansi                 # 终端 TUI
python -m dsh_pet --renderer ansi --width 60      # 宠物宽度（字符）
python -m dsh_pet --renderer ansi --fps 15        # 帧率
python -m dsh_pet --renderer ansi --no-hint       # 隐藏按键提示行
python -m dsh_pet --renderer ansi --bg-color 1e1e2e
```

* 按键：`f` 喂食 · `p` 抚摸 · `s` 睡觉/唤醒 · `q` / `Ctrl+C` 退出
* 退出自动恢复光标与屏幕（备用屏幕缓冲），处理终端尺寸变化
* Windows 终端自动启用 VT 模式（Windows 10+ / Windows Terminal 无需额外配置）

## 窗口模式（Tk）

```sh
python -m dsh_pet --gui
python -m dsh_pet --gui --scale 4        # 像素放大倍数
python -m dsh_pet --gui --bg-color 1e1e2e
```

* 鼠标点击宠物 → 随机反应；键盘 `f/p/s/q` 同终端模式
* 无显示服务器时自动回退到 ANSI 终端模式

## dsh 集成

`dsh` 是 Node.js（Cordis）实现，本插件通过**子进程**方式拉起 Python
宠物，任务状态经 **JSON 文件**传递，不阻塞 dsh 主任务。

### 安装

```sh
# 1. 创建 pet profile 并安装插件包（把 <path> 换成插件目录）
dsh plugin --profile pet add <path>/plugins

# 2. 将 plugins/pet.profile.yml 的内容放入
#    $DSH_HOME/profiles/pet/cordis.patch.yml（已存在则追加 insert 行）
```

`plugins/pet.profile.yml` 内容示例：

```yaml
- insert:
    - id: dsh-pet
      name: '@dsh-pet/plugin'
      config:
        pythonBin: python            # python 解释器
        packageDir: 'D:\...\dsh-pet-lulu'   # 未 pip 安装时的仓库路径（或设 DSH_PET_HOME 环境变量）
```

### 运行

```sh
dsh --profile pet pet                              # 默认：web 宠物（打开浏览器）
dsh --profile pet pet --mode terminal              # 终端 TUI
dsh --profile pet pet --mode tk                    # Tk 窗口
dsh --profile pet pet --pet-type capybara \
    --status-source file --status-file .dsh_pet_status.json
dsh --profile pet pet --help                       # 全部选项
```

`pet` 子命令支持与 Python CLI 相同的选项：`--mode`、`--pet-type`、
`--renderer`、`--gui`、`--fps`、`--width`、`--bg-color`、`--port`、
`--no-browser`、`--status-source`、`--status-file`、`--config`、`--no-hint`。

### 任务状态传递

* `--status-source file` 时，插件持续把演示任务进度写入状态文件，宠物气泡
  实时显示——「dsh 任务进度」真实来自 dsh 侧；
* 其他 dsh 插件可通过插件提供的 `petStatus.update({task_name, phase,
  progress, gpu_temp, message})` 服务推送真实状态到状态文件；
* 状态文件格式：

```json
{"task_name": "...", "phase": "running", "progress": 42.0,
 "gpu_temp": 61.0, "message": "..."}
```

### 字面 `dsh pet`

启动器只内置了 `web` 别名，字面 `dsh pet` 需要一条 shell 别名：

```powershell
# PowerShell
function dsh-pet { dsh --profile pet pet @args }
```

```sh
# bash / zsh
alias dsh-pet='dsh --profile pet pet'
```

## 配置文件

复制 [`.dsh_pet_config.example`](.dsh_pet_config.example) 为
`.dsh_pet_config`（当前目录或 `~`），或 `-c <path>` 指定。所有键均可选：

| 节 | 键 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `[general]` | `pet_type` | `lulu` | 形象：`lulu` / `capybara` |
| | `log_level` | `info` | `debug` / `info` / `warning` / `error` |
| `[animation]` | `fps` | `10` | 帧率（FPS） |
| | `random_action_interval` | `12.0` | 随机动作间隔（秒） |
| | `random_action_chance` | `0.6` | 随机动作概率（0–1） |
| `[renderer]` | `mode` | `web` | `web`（默认）/ `ansi` / `tk` / `auto` |
| | `ansi_width` | `48` | 终端宠物宽度（字符） |
| | `bg_color` | 空 | 透明像素背景色，如 `1e1e2e`；空=终端默认 |
| | `tk_scale` | `3` | Tk 窗口像素放大倍数 |
| | `web_port` | `8765` | web 模式端口 |
| | `open_browser` | `true` | web 模式自动打开浏览器 |
| `[interaction]` | `feed_key` | `f` | 喂食键 |
| | `pet_key` | `p` | 抚摸键 |
| | `sleep_key` | `s` | 睡觉/唤醒键 |
| | `quit_key` | `q` | 退出键 |
| `[dsh]` | `status_source` | `mock` | `mock` / `file` / `none` |
| | `status_file` | `.dsh_pet_status.json` | 状态 JSON 文件路径 |
| | `status_poll_interval` | `1.0` | 状态轮询间隔（秒） |
| | `bubble_width` | `40` | 气泡最大宽度（字符） |

命令行参数优先级高于配置文件。

## 键盘 / 鼠标交互汇总

| 键 | web 模式 | 终端模式 | Tk 窗口 |
| --- | --- | --- | --- |
| `f` | 喂食 | 喂食 | 喂食 |
| `p` | 抚摸 | 抚摸 | 抚摸 |
| `s` | 睡觉/唤醒 | 睡觉/唤醒 | 睡觉/唤醒 |
| `h` | 隐藏/召唤 | — | — |
| `q` / `Ctrl+C` | 关闭页面 | 退出并恢复终端 | 关闭窗口 |
| 鼠标 | 点击摸头、拖动换位 | — | 点击随机反应 |

所有按键可在配置文件 `[interaction]` 中重定义。

## 测试

```sh
python -m unittest discover -s tests -v     # 全部单元测试（含 web 接口测试）
node plugins/test.js                         # cordis 插件测试
python scripts/render_preview.py            # 生成 docs/preview.gif 预览
python -m dsh_pet --renderer ansi --no-hint # 手动体验终端模式
python -m dsh_pet --no-browser              # 手动体验 web 模式
```

## 项目结构

```plain
dsh_pet/
├── __init__.py            # 包声明
├── main.py                # 入口：参数解析、模式选择、按键读取（POSIX/Windows）
├── pet_core.py            # 状态机 + 动画引擎 + 事件队列
├── renderer.py            # AnsiRenderer（终端半块渲染）/ TkRenderer（窗口）
├── web_renderer.py        # WebRenderer（默认）：HTTP 服务器 + 浏览器宠物页
├── sprite.py              # 素材加载：pet.json + spritesheet.webp → 帧/降采样
├── config.py              # .dsh_pet_config 加载
├── dsh_integration.py     # MockStatusSource / FileStatusSource + 气泡格式化
├── assets/                # 素材与许可（见 SOURCES.md）
│   ├── lulu/              # czy666chen/lulu（MIT）
│   ├── capybara/          # HatchPet-CapybaraLulu（Apache-2.0）
│   └── SOURCES.md
├── bin/dsh-pet            # 包装脚本（POSIX sh + Windows .cmd）
├── plugins/               # cordis 插件（JS）：注册 dsh pet 子命令（默认 web 模式）
├── tests/                 # unittest：动画循环、状态机、按键、配置、渲染、web
├── scripts/               # 预览图/演示脚本
├── .dsh_pet_config.example
├── README.md / README.en.md
└── pyproject.toml
```

## 素材来源与许可

* `lulu`：czy666chen/lulu，**MIT License**
  （`dsh_pet/assets/lulu/licenses/LICENSE.lulu`）。
* `capybara`：srwang0506/HatchPet-CapybaraLulu，**Apache-2.0**
  （`dsh_pet/assets/capybara/licenses/LICENSE` + `NOTICE`）。
* 完整说明、行序布局与下载方式见 [`dsh_pet/assets/SOURCES.md`](dsh_pet/assets/SOURCES.md)。
* 本项目代码以 MIT 许可发布（见根目录 LICENSE）。

## 常见问题（FAQ）

* **页面看不到宠物？** 先按 F5 刷新；如果点过「隐藏」，右下角会出现
  「召唤宠物」按钮，点它。
* **端口被占用？** 换一个：`python -m dsh_pet --port 9000`。
* **没有 Pillow？** `pip install -e ".[sprites]"`；终端宠物会退化为 ASCII
  形象，web 模式会报错提示。
* **`dsh pet` 提示缺 `--profile`？** 启动器只内置 `web` 别名，用
  `dsh --profile pet pet` 或按上文加 shell 别名。
* **宠物不想动/睡觉了？** 按 `s` 唤醒。
* **想重置 web 宠物位置？** 清除浏览器 localStorage 里的
  `dsh-pet-lulu-pos` 键。

## 验收对照

- [x] `python -m dsh_pet`（默认 web）打开宠物页并稳定播放待机动画
- [x] `--renderer ansi` 终端模式保留，`f` / `p` / `s` 按键有对应动画反应
- [x] 连续运行无崩溃、CPU <5% 单核（帧循环节流）
- [x] dsh 集成：插件子进程拉起宠物 + 状态文件传递模拟进度
- [x] web 模式：点击/喂食/睡眠/隐藏/召唤/拖动 + 状态气泡接口全部可用
- [x] 代码结构清晰、注释适当、README 双语完整
