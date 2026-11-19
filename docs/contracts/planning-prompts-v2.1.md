# 规划软件提示 V2.1 实施基线

日期：2026-11-19。契约 2.1.0，protocol_version="2.1"，规则 rcviplan-prompts/2.1.0。
本设计取代旧 2.0.0 的实施范围；旧文件保留用于历史追溯，不与本版混用。

## 已确认范围

覆盖已有血管分割、三点取点/删点、假体设置/定位、移动/回位；分割不阻断后续操作。
沿用单条纯文本与控件高亮，不增加建议导航按钮或独立告警区。
每次启动默认开启；用户关闭后隐藏面板并清除高亮，切页、状态变化、晚到响应都不能重新打开。
工具栏“帮助”重新开启并请求当前状态。开关仅保存在当前进程，不持久化。
本版不新增独立保存、保存版本、定位失效重算、测量、报告、知识库或大模型。

## 状态和通信

Qt 主动 POST /api/v2/agent/guide，默认本机 http://127.0.0.1:8000；RCVIPLAN_GUIDANCE_URL 可改本机地址。
RCVIPLAN_GUIDANCE_PROTOCOL 默认 v2，显式 v1 可回退；不自动降级。V1 HTTP 业务行为不变。
request_id 为小写 UUID v4，state_revision 为 0–9007199254740991 的整数；两者响应原样回传。
相同快照可重新请求，request_id 更新；快照变化递增 state_revision。页面重新进入另由 Qt context_id 和网络 generation 防旧响应。
请求不传病例 ID、路径、影像、坐标或参数值。

state 必填且拒绝额外字段：

| 字段 | 取值及来源 |
|---|---|
| current_page | render/vessel_extract/annulus_pick/navigation/reserved_4/reserved_5，现有页面映射 |
| ct_loaded | bool，IsImageLoaded |
| picked_point_count | 0–3，主线程取点容器计数 |
| segmentation_status | not_started/running/succeeded/failed，由实际分割开始和终态信号记录 |
| segmentation_result_available | bool，现有 IsSegmentValid；与最近尝试失败可同时为真 |
| prosthesis_status | absent/unknown/available，见下文 |
| move_enabled | bool，已执行移动模式设置且当前三点及模型可操作 |
| returned | bool，当前最近一次有效回位操作完成；后续移动、参数或点位变化清除 |

available 仅表示有限矩阵已应用并完成现有切片更新，不表示临床定位正确或完整规划完成。
模型创建/参数更新开始、已有模型时点位变化置 unknown；无可靠终态时保持 unknown，不从指针推断成功。
unknown 只提示检查当前模型/点位/参数，不要求新建业务状态机或自动重新定位。
CT 未加载时只允许空业务状态；分割 succeeded 必须有可用结果；move_enabled/returned 为 true 必须 available 且三点齐全。

## 页面规则（按页面内顺序匹配）

| 条件 | 提示方向 | target_id |
|---|---|---|
| CT 未加载 | 从主程序打开有效病例 | null |
| 分割页：running | 等待，也可继续取点 | null |
| 分割页：failed | 查看错误后重试，也可继续取点；有旧结果则补充说明 | segment.auto_segment |
| 分割页：有可用结果 | 查看结果，继续取点 | nav.next |
| 分割页：其余 | 可先进行分割，也可继续取点 | segment.auto_segment |
| 取点页：不足三点 | 已取 n 点，还差 3−n 点 | annulus.pick |
| 取点页：三点 | 检查点位，进入假体设置；可删除重取 | nav.next |
| 假体页：不足三点 | 返回完成取点 | nav.back |
| 假体页：absent | 打开设置、配置并应用 | navigation.sent_setting |
| 假体页：unknown | 检查模型、点位和参数，尚不能确认可操作 | null |
| 假体页：returned | 已执行回位，可继续检查或调整 | null |
| 假体页：move_enabled | 可移动，需要恢复时回位 | navigation.sent_return |
| 假体页：其余 available | 检查位置，按需移动 | navigation.sent_move |
| render | 进入分割页面开始规划 | nav.next |
| 预留页 | 暂无操作提示 | null |

完整文案由 app/services/guidance_v2.py 与 tests/test_guide_v2.py 验证。
响应只含 protocol_version/request_id/state_revision/rule_version/reason_code/message/target_id；target_id 显式 null 或白名单标识。
分割状态不覆盖其他页面的提示。目标隐藏、禁用或缺失时显示文字，补充控件不可用说明，不高亮。

## 时序与异常

切页、取点/删点、分割开始/结束、模型更新开始/矩阵应用、移动模式、回位完成触发请求。
同一事件循环合并请求；先废弃在途请求并清除旧高亮。相同文字和目标不重设文本，响应后恢复有效高亮。
关闭先禁用控制器、清除界面并取消请求；任何来源（含模拟调用）在禁用时都不展示。
无后台轮询、无自动重试；服务失败显示错误文字，帮助或下一次相关状态变化可重试。
总超时 3000 ms，请求最大 16384 字节、响应最大 65536 字节，所有 UI 在主线程更新。
V2 错误结构沿用 error.code/message/details（protocol_version 改为 2.1）；输入错误不回显输入，独立于 V1。

## 验收

后端：所有规则分支、跨字段约束、取点 0→1→2→3→2→3、移动/回位序列、非法输入、体积、媒体类型、重复 JSON 键、异常、V1 回归。
Qt：启动自动提示；分割运行/失败后可取点；同页增删点更新；模型更新期间不误报可操作；移动和回位提示；快速切页丢弃旧响应；关闭后切页/完成任务仍隐藏；帮助重开；重启默认开启；隐藏/禁用目标；断网恢复。
必须在 Windows 工作机完成 Debug/Release 构建和真实页面验证，不能用静态检查替代。

## 状态核查限制

既有假体构建实现仍含工作线程访问模型/界面的历史逻辑，本版只接入主线程收到的完成事件，未宣称完成线程模型重构。
对无法可靠确认的模型状态返回 unknown。工作机须重点验证模型更新、切页、关闭与提示的交互。
