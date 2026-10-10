# TAVR Agent Backend

面向 Qt/C++ 桌面软件的操作引导后端。V1 根据软件状态返回下一步提示，使用确定性规则，不依赖大模型、数据库或外部服务。

这只是用于学习的软件操作引导规则，不代表完整或经过临床验证的 TAVR 工作流程。

## 环境与启动

需要 Python 3.12 或更高版本；建议使用 Python 3.12。当前工作目录本身就是项目根目录，不需要再创建一层 `tavr-agent-backend/`。包名称为 `tavr-agent-backend`，磁盘目录可以保持 `RCVI-Agent-Backend`。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
fastapi dev app/main.py --host 127.0.0.1 --port 8000
```

Windows 激活命令为 `.venv\Scripts\activate`（cmd）或 `.venv\Scripts\Activate.ps1`（PowerShell）。只运行服务时，可安装 `requirements.txt`。

- Swagger 文档：<http://127.0.0.1:8000/docs>
- OpenAPI：<http://127.0.0.1:8000/openapi.json>
- 健康检查：<http://127.0.0.1:8000/health>

## 调用示例

```bash
curl --fail-with-body http://127.0.0.1:8000/agent/guide \
  -H 'Content-Type: application/json' \
  -d '{"state":{"current_page":"ct_viewer","ct_loaded":true,"annulus_plane_confirmed":false,"measurement_completed":false}}'
```

```json
{"message":"请进入瓣环定位模块。","next_action":"open_annulus_plane"}
```

`state` 必须存在，但其内部字段可省略，默认视为尚未完成。布尔值必须是 JSON `true` / `false`，不能传字符串或数字。未知字段返回 422。Qt 应根据 `next_action` 分发页面跳转，不应解析中文提示作为控制逻辑。

## 验证

```bash
python -m pytest
```

测试覆盖全部 8 种布尔状态组合、默认值、非法输入、请求之间的状态隔离，以及文档和接口契约。

## 文档

- [详细设计](docs/design.md)：范围、架构、契约、决策表、Qt 对接、错误处理、部署与迭代计划。
- [Qt 接入示例](docs/qt-integration.md)：Qt 6 请求代码、动作白名单、超时和过期响应处理。

依赖文件指定兼容范围，未锁定全部传递依赖。交付部署前，应在目标环境验证并冻结完整依赖版本；这份初始化项目尚未包含生产发布流水线。
