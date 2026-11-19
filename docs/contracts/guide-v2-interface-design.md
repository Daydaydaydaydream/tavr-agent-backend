> 2026-11-19 更新：本页保留历史设计/验收记录。当前实施以 [V2.1 收窄版](planning-prompts-v2.1.md) 为准；旧保存、导航交互及提示关闭语义不作为本轮要求。

# RCVIPlan ↔ Backend V2 接口设计

版本：**2.0.0 设计基线**。规则版本：`rcviplan-guidance/1.0.0`。日期：2026-10-14。

状态：接口设计已完成，可作为 Q1 / B1 实施依据；尚未实现 V2 业务代码，尚未进行 V2 运行联调。本设计基于 RCVIPlan `b6949dc`、Backend `2d941e9` 源码及用户已完成的 V1 联调。设计决策由本次接口设计确定，不表示用户逐条确认过业务细节。

## 1. 项目路线与本次交付

1. 阶段 A：V1 后端、Qt HTTP 接入与本机联调——已完成。
2. 阶段 B / D0：状态语义、HTTP 契约、Qt 内部接口、规则与样例——本次完成设计。
3. 阶段 B / Q1–Q3、B1–B2：按本设计实现状态、保存一致性、V2 请求与规则——尚未开始。
4. 阶段 B / Q4、B3：目标环境构建、联合验收及兼容发布——实施后执行。
5. 阶段 C：知识或大模型——另行完成接口与评估设计后实施，不纳入本版。

| 交付物 | 用途 |
| --- | --- |
| 本文 | 规范性语义、跨字段约束、时序、内部接口及设计决策 |
| [OpenAPI YAML](guide-v2.openapi.yaml) / [JSON 等价文件](guide-v2.openapi.json) | 开发前定义的 HTTP 结构、枚举和范围；两份内容必须完全等价 |
| [规则表](guide-v2.decision-table.json) | 规则顺序、原因代码、提示模板和候选动作 |
| [共享样例](../../tests/fixtures/guide_v2/README.md) | HTTP 正反例、传输错误、Qt 事件序列 |
| [契约检查程序](validate_contract.py) | 校验结构、状态约束、决策样例及版本一致性；不调用业务接口 |
| [检查记录](validation-report.md) | 本次实际执行的设计验证及未执行范围 |

本文和机器可读契约共同约束实现。JSON Schema 不能表达的版本比较、请求响应关联、规则优先级和线程行为以本文为准。若文档与文件出现矛盾，先修正设计并重新验证，不能由任一端自行选择解释。

## 2. 已确定的设计决策

| 问题 | 本版决策 | 依据及边界 |
| --- | --- | --- |
| 分割是否阻断取点/定位 | 不新增硬前置；运行/失败放入独立 `alerts` | 现有 Qt 操作没有统一的强制分割前置；主建议仍随取点、定位、保存推进 |
| 如何呈现分割失败 | 单独提示，提供分割页入口；已有可用结果与最近尝试失败分开表达 | 避免一次分割失败永久遮住保存建议 |
| 保存范围 | 仅现有 `sent_plan.json` 的 `points` 与 `rotation_matrix` | 当前写入端未保存假体规格，仓库中也未找到读取端；不擅自改变文件格式 |
| 保存提示 | “当前取点与定位矩阵已保存（不含假体规格）。” | 不暗示假体尺寸、类型、测量或完整流程已保存 |
| 独立保存入口 | 新增“保存定位结果”按钮，与关闭保存复用同一方法 | 可以在不退出窗口的情况下验证保存 |
| 点位改变 | 旧定位失效；补回 3 点不恢复旧定位，须用户明确重新定位 | 防止三点数量相同却复用过期矩阵 |
| 假体计算 | 增加 running / failed 状态和错误码 | 当前 InitSentModel / UpdateSentModel 是异步的；对象指针不代表已完成 |
| 参数或材质变化 | 触发必要的模型重建状态；仅当取点或最终矩阵改变时增加持久化版本 | 规格参数不在本版保存范围，界面持续说明这一点 |
| 任务期间关闭 | 有分割或假体构建任务运行时拒绝正常关闭并提示等待 | 本版不增加任务取消；析构前必须等任务完成，不得后台访问已销毁对象 |
| 协议与状态所有权 | Qt 是状态权威，Backend 无状态、纯规则，不反向执行操作 | 全量快照即可恢复引导；不需要病例 ID、数据库或事件补发 |

此前设计稿中的“分割失败作为主规则”“假体只有 absent / needs_reposition / ready”“整个规划已保存”由本版替代。以上范围内无留给实现者决定的阻断性待定项。完整假体文件格式、正式瓣环确认、测量、报告、进程内切换病例、远程部署移出本版。

## 3. HTTP 基础约定

- 方法与路径：`POST /api/v2/agent/guide`；开发基础地址 `http://127.0.0.1:8000`。
- 请求和响应编码为 UTF-8 JSON；请求接受 `application/json` 及其 `charset=utf-8` 参数，媒体类型大小写不敏感。不接受其他媒体类型或 Content-Encoding 压缩。
- 无鉴权、无会话，继续限定本机回环场景；不表示已经具备远程发布能力。
- 请求体最大 **16384 字节**，按实际读取字节累计，不能只检查 Content-Length；超限 413。响应不得超过 **65536 字节**，Qt 保留同等限制。
- Qt 总超时 **3000 毫秒**；同一客户端最多一个活动请求，后发请求废弃旧请求，不自动重试。
- 校验顺序：媒体类型/编码 → 实际字节上限 → 严格 JSON 解析 → 字段结构 → 跨字段约束 → 规则 → 动作过滤 → 响应。
- JSON 重复键、NaN、Infinity、语法错误归为 INVALID_JSON；合法 JSON 的根不是对象归为 INVALID_REQUEST。
- JSON 整数按数值定义：数值必须有限、无小数部分且在范围内，`1.0` 与 `1` 等价；字符串 `"1"`、布尔值 `true` 不等价。Qt 输出规范整数，后端不得依靠宽松类型转换。
- HTTP 200 只表示本次引导成功，不表示操作执行、保存成功或持续在线。

### 3.1 版本

| 标识 | 值 | 作用 |
| --- | --- | --- |
| URL 版本 | `/api/v2` | 新协议边界，与 V1 并存 |
| `protocol_version` | 字符串 `2` | 请求与响应固定标识 |
| OpenAPI `info.version` | `2.0.0` | 本次完整契约版本 |
| `rule_version` | `rcviplan-guidance/1.0.0` | 决策与文案的确定性版本 |

V1 `/agent/guide`、`/health` 保持原行为和错误格式。Qt 用新增配置 `RCVIPLAN_GUIDANCE_PROTOCOL=v1|v2` 显式选择，未设置默认 v1；非法值报配置错误。已有 `RCVIPLAN_GUIDANCE_URL` 保持基础地址约定。协议在构造客户端时读取，修改后重启；开发测试若支持运行时切换，必须先取消在途请求并清空动作。

V2 404 不自动降级。新字段和枚举会被严格客户端拒绝，增加字段/动作/原因代码也必须先升级契约、协调两端发布；不得仅更新规则版本后静默投放。文案修订和既有枚举内的规则变更也需更新规则版本与样例。

## 4. 请求数据字典

全部字段必填；所有对象拒绝额外字段。无默认补全。

| 字段 | 类型 / 范围 | 语义 |
| --- | --- | --- |
| protocol_version | string，固定 `2` | 协议版本 |
| request_id | 小写、无花括号 UUID v4 | Qt 每次请求新建；不含患者标识 |
| state_revision | integer，0–9007199254740991 | 对外快照版本；页面、状态或能力列表变化时递增 |
| supported_actions | 0–4 个不重复 Action | 当前客户端实际交付的入口；不是“当前允许执行”的授权列表 |
| state.current_page | string，1–128，至少一个非空白字符 | Qt 页面 objectName；不用于绕过业务状态 |
| state.ct_status | not_started / running / succeeded / failed | CT 加载状态；当前同步加载首次查询终态即可 |
| state.segmentation_status | 同上四态 | 最近一次分割任务状态 |
| state.segmentation_result_available | boolean | 当前病例存在通过校验的结果；失败后可为 true |
| state.segmentation_error_code | 分割错误枚举或 null | 只有 failed 时非 null |
| state.picked_point_count | integer，0–3 | 实际成功登记的点数 |
| state.prosthesis_status | absent / needs_reposition / running / failed / ready | 不存在、失效、计算中、失败、当前结果有效 |
| state.prosthesis_error_code | 假体错误枚举或 null | 只有 failed 时非 null |
| state.plan_revision | 安全非负整数 | 本进程 points 或最终 rotation_matrix 的内容版本 |
| state.saved_plan_revision | 安全非负整数或 null | 本进程最近成功提交的内容版本；文件存在不能代替此状态 |
| state.save_status | not_started / running / succeeded / failed | 最近一次保存尝试；编辑使前置条件失效时重置 |
| state.save_error_code | 保存错误枚举或 null | 只有 failed 时非 null |

传输范围不包括 CT、患者数据、病例 ID、点坐标、矩阵、路径和原始错误日志。初值：revision=0，saved_plan_revision=null，点数=0，假体 absent，其余操作 not_started、错误 null、结果不可用；current_page 取真实页面。

### 4.1 状态错误码

| 模块 | 错误码 | 来源 |
| --- | --- | --- |
| 分割 | SEG_CONFIG_INVALID | 配置不存在、不完整或不可解析 |
| 分割 | SEG_INPUT_INVALID | 病例/影像无效、输入转换失败 |
| 分割 | SEG_ENGINE_FAILED | 外部引擎执行失败 |
| 分割 | SEG_RESULT_INVALID | 输出缺失、空网格或校验失败 |
| 分割 | SEG_PERSIST_FAILED | 结果缓存写入失败；已验证内存结果可保留 |
| 分割 | SEG_INTERNAL_ERROR | 已捕获的其他异常 |
| 假体 | PRO_INPUT_INVALID | 点坐标/参数无效、三点退化或共线 |
| 假体 | PRO_BUILD_FAILED | 假体网格生成或校验失败 |
| 假体 | PRO_PLACEMENT_FAILED | 有效输入下矩阵生成/应用失败 |
| 假体 | PRO_INTERNAL_ERROR | 已捕获的其他异常 |
| 保存 | SAVE_PRECONDITION_FAILED | 点数、定位或输出内容不满足要求 |
| 保存 | SAVE_WRITE_FAILED | 打开、写入或原子提交失败 |
| 保存 | SAVE_INTERNAL_ERROR | 已捕获的其他异常 |

CT 失败原因保留于 Qt 本地，本版 HTTP 只传 failed。用户仍可在 Qt 查看具体错误。错误码和可读日志必须分离。

### 4.2 跨字段约束（按 I01–I09 顺序验证）

| 编号 | 约束 | 错误字段 |
| --- | --- | --- |
| I01 | CT 非 succeeded：点数=0、假体 absent、分割 not_started/无结果、保存 not_started、plan_revision=0、saved_plan_revision=null | state.ct_status |
| I02 | 分割 failed 必须有分割错误，其他状态错误为 null | state.segmentation_error_code |
| I03 | 分割 succeeded 必须 result_available=true；not_started 必须 false | state.segmentation_result_available |
| I04 | 假体 ready/running/failed 要求 CT 成功且 3 点；needs_reposition 要求 CT 成功但允许不足 3 点 | state.prosthesis_status |
| I05 | 假体 failed 必须有假体错误，其他状态错误为 null | state.prosthesis_error_code |
| I06 | 保存 running/succeeded 要求 CT 成功、3 点、假体 ready | state.save_status |
| I07 | 保存 succeeded 必须 saved_plan_revision 非 null | state.saved_plan_revision |
| I08 | 保存 failed 必须有保存错误，其他状态错误为 null | state.save_error_code |
| I09 | 保存版本非 null 时必须 ≤ 当前内容版本 | state.saved_plan_revision |

字段结构校验优先于上述约束，失败返回 422；后端不“修复”状态。保存失败可以发生在前置条件不足时，此时主建议仍优先指导补齐点位。保存版本相等本身不代表当前几何有效，必须经过主规则前置条件后才能返回 PLAN_SAVED。

## 5. 成功响应与规则

### 5.1 响应字段

| 字段 | 约束 |
| --- | --- |
| protocol_version | 固定 `2` |
| request_id / state_revision | 逐字/逐值回传请求；不得重新生成 |
| rule_version | string，1–64；本版固定规则版本 |
| reason_code | 下表中主规则枚举之一 |
| message | string，1–1024；按规则表生成纯文本 |
| next_action | Action 或显式 null；不能省略 |
| severity | info / warning / error |
| alerts | 必填数组，0–1 项；分割提示独立于主规则 |

每个 alert 固定包含 reason_code、message、next_action、severity，拒绝额外字段；其 reason_code 只能是 SEGMENTATION_RUNNING / SEGMENTATION_FAILED。主面板和告警分别展示，独立按钮都要经过同一动作校验。

### 5.2 主规则（从上到下首次命中）

| 顺序 | 条件 | reason_code | severity | 候选动作 |
| --- | --- | --- | --- | --- |
| 1 | CT not_started | CT_NOT_READY | info | null |
| 2 | CT running | CT_LOADING | info | null |
| 3 | CT failed | CT_LOAD_FAILED | error | null |
| 4 | 保存 running | PLAN_SAVING | info | null |
| 5 | 点数 < 3 | POINTS_INCOMPLETE | info | open_point_picking |
| 6 | 假体 running | PROSTHESIS_BUILDING | info | null |
| 7 | 假体 failed | PROSTHESIS_FAILED | error | open_prosthesis_settings |
| 8 | 假体 absent | PROSTHESIS_NOT_CREATED | info | open_prosthesis_settings |
| 9 | 假体 needs_reposition | PROSTHESIS_NEEDS_REPOSITION | warning | open_prosthesis_settings |
| 10 | 保存 failed | PLAN_SAVE_FAILED | error | focus_save_plan |
| 11 | 保存版本 null 或与当前不同 | PLAN_UNSAVED | info | focus_save_plan |
| 12 | 其余合法状态 | PLAN_SAVED | info | null |

分割 running 时增加 info 告警；failed 时增加 warning 告警，并按 result_available 区分“已有结果仍可用”和“没有可用结果”。分割成功/未开始时 alerts=[]。分割告警不修改主规则结果，不禁用其他原有操作。

文案精确模板及两个失败分支见 [规则表](guide-v2.decision-table.json)。POINTS_INCOMPLETE 用当前点数 n 和 3−n 格式化。候选动作不在本次 supported_actions 时替换为 null，主结果和告警分别过滤；提示保留，按钮隐藏/禁用。用户可按提示使用普通业务入口。

### 5.3 请求与响应示例

完整可复制示例见 `http-cases.json` 中 `seg_failed_saved`：它同时返回 PLAN_SAVED 和 SEGMENTATION_FAILED 告警，说明“定位结果已保存”和“本次分割失败”可以同时为真。`save_and_seg_running` 则返回 PLAN_SAVING 与 SEGMENTATION_RUNNING，彼此不覆盖。

请求：

```json
{
  "protocol_version": "2",
  "request_id": "c62ef01e-8c51-44b9-a88a-e70c743bb80f",
  "state_revision": 12,
  "state": {
    "current_page": "page_selectPoint",
    "ct_status": "succeeded",
    "segmentation_status": "failed",
    "segmentation_result_available": true,
    "segmentation_error_code": "SEG_PERSIST_FAILED",
    "picked_point_count": 3,
    "prosthesis_status": "ready",
    "prosthesis_error_code": null,
    "plan_revision": 4,
    "saved_plan_revision": 4,
    "save_status": "succeeded",
    "save_error_code": null
  },
  "supported_actions": [
    "open_segmentation",
    "open_point_picking",
    "open_prosthesis_settings",
    "focus_save_plan"
  ]
}
```

响应（HTTP 200）：

```json
{
  "protocol_version": "2",
  "request_id": "c62ef01e-8c51-44b9-a88a-e70c743bb80f",
  "state_revision": 12,
  "rule_version": "rcviplan-guidance/1.0.0",
  "reason_code": "PLAN_SAVED",
  "severity": "info",
  "next_action": null,
  "message": "当前取点与定位矩阵已保存（不含假体规格）。",
  "alerts": [
    {
      "reason_code": "SEGMENTATION_FAILED",
      "severity": "warning",
      "next_action": "open_segmentation",
      "message": "本次分割失败；已有分割结果仍可用。可前往分割页面查看并重试。"
    }
  ]
}
```

## 6. Qt 动作映射与执行边界

| Action | 确定的 Qt 入口 | 动作行为 | 执行前置 |
| --- | --- | --- | --- |
| open_segmentation | `page_segment` / `pb_autoSeg` | 只切页并聚焦，不触发 clicked | CT 成功，分割当前不 running |
| open_point_picking | `page_selectPoint` / `pb_pointPick` | 只切页并聚焦 | CT 成功 |
| open_prosthesis_settings | `page_navigation` / `pb_sentSetting`，`ShowSentSettingView()` | 切页并打开已有设置窗，不调用 HandleImport | CT 成功，3 点，假体不 running |
| focus_save_plan | `page_navigation` / **新增** `pb_savePlan` | 切页并聚焦“保存定位结果”，不保存 | CT 成功，3 点，假体 ready，保存不 running |

前三个页面及现有控件已经源码核实，导航封装仍需实施；pb_savePlan 尚不存在，是 Q3 明确交付项。客户端只有在对应处理器和控件交付后才能声明动作支持。协议定义动作全集不代表现有 V1 客户端已经支持。

同页只聚焦，不反复切页；已有设置窗显示时 raise/activate。一次用户点击不得模拟分割、取点、参数导入、重新定位或保存按钮点击。若引导发布后状态改变，先清空旧按钮、废弃请求，再刷新；点击时状态校验失败也不执行。

设置窗“导入/应用”明确作为用户业务操作：创建或重建假体并按当前三点定位。重试/重新定位也由该显式操作触发。仅打开设置窗不得计算。无效参数或退化点应产生结构化失败，不允许对空矩阵应用变换。

## 7. HTTP 错误契约

所有本版错误体使用以下结构，error.details 不含输入值或堆栈：

```json
{
  "protocol_version": "2",
  "request_id": null,
  "error": {
    "code": "INVALID_JSON",
    "message": "请求不是有效的 JSON 对象。",
    "details": [{"code": "INVALID_JSON", "field": "$"}]
  }
}
```

| HTTP | error.code | detail.code / field |
| --- | --- | --- |
| 413 | REQUEST_TOO_LARGE | details=[]，request_id=null |
| 415 | UNSUPPORTED_MEDIA_TYPE | details=[]，request_id=null；也用于不支持的 Content-Encoding |
| 422 | INVALID_JSON | INVALID_JSON / `$`，request_id=null |
| 422 | INVALID_REQUEST | 字段检查代码及规范字段路径；根类型错误 field=`$` |
| 422 | INCONSISTENT_STATE | INCONSISTENT_STATE / I01–I09 对应字段 |
| 500 | INTERNAL_ERROR | details=[]；验证后异常可回传已解析合法 request_id |

字段检查代码：MISSING_FIELD、UNKNOWN_FIELD、INVALID_TYPE、OUT_OF_RANGE、INVALID_ENUM、INVALID_FORMAT、DUPLICATE_ITEM。未知键的路径归一化为所属已知父对象，不回显任意输入键；数组错误路径固定为 supported_actions。长度超界归 OUT_OF_RANGE，UUID/空白页面格式错误归 INVALID_FORMAT。

结构校验阶段可返回多个 detail：按 field 字典序、再按 code 字典序稳定排序，去重后最多 32 项；只有结构完全通过才校验跨字段约束，按 I01–I09 顺序返回第一项。错误 message 为 1–1024 字符；field 为 1–128。错误体不带 next_action。原始 JSON 可解析为对象且 request_id 合法时才回传该 ID；请求解析前拒绝或 ID 非法时为 null。

404 / 405 的框架错误体不作本契约保证，Qt 仅按状态识别错误；路径级 V2 异常处理不得改变 V1。网络断开/超时没有 HTTP 错误体，按本地请求上下文处理。无自动重试，用户可刷新；422 需修正请求/状态，不能重复提交相同错误。

## 8. Qt 内部数据与接口

以下是待实施的 C++ 接口设计，不是当前已存在的声明。Qt 5、C++20；用值类型和 std::optional，不跨线程共享可变 UI / VTK actor。

### 8.1 数据类型

| 类型 | 完整字段定义 |
| --- | --- |
| OperationStatus | enum：NotStarted、Running、Succeeded、Failed；转换到 HTTP 的四个小写值 |
| SegmentationSnapshot | OperationStatus status；bool resultAvailable；optional<SegmentationErrorCode> errorCode；quint64 taskGeneration（仅本地） |
| CtSnapshot | OperationStatus status；QString localError（仅本地） |
| ProsthesisStatus | enum：Absent、NeedsReposition、Running、Failed、Ready |
| WorkflowSnapshot | quint64 stateRevision；QString currentPage；CtStatus ctStatus；SegmentationSnapshot segmentation；int pickedPointCount；ProsthesisStatus prosthesisStatus；optional<ProsthesisErrorCode> prosthesisError；quint64 planRevision；optional<quint64> savedPlanRevision；OperationStatus saveStatus；optional<SaveErrorCode> saveError；QVector<Action> supportedActions |
| RequestContext | QUuid requestId；quint64 stateRevision；quint64 generation（仅本地）；Protocol protocol |
| GuidanceNotice | ReasonCode reason；QString message；optional<Action> action；Severity severity |
| GuideResponseV2 | RequestContext 对应的 requestId/stateRevision；QString ruleVersion；GuidanceNotice primary；QVector<GuidanceNotice> alerts；protocol 固定 V2 |
| OperationResult | bool success；optional<LocalOperationError> errorCode；QString localMessage；失败保证不提交部分修改 |
| SaveResult | bool success；optional<SaveErrorCode> errorCode；QString localMessage；optional<quint64> committedRevision |
| PlanPayload | array<array<double,3>,3> points；array<array<double,4>,4> rotationMatrix（仅本地，按值捕获） |
| TransportError | TransportErrorKind kind；int httpStatus（无 HTTP 为 0）；QString localMessage；optional<ApiError> apiError |
| ApiError | QString code；QString message；QVector<ErrorDetail> details（每项 code/field） |

Action / ReasonCode / Severity / 模块错误码枚举逐项来自 OpenAPI，不允许自行扩展。LocalOperationError={NoImage,PointLimit,NoPoint,InvalidPoint,InvalidParameters,DegeneratePlane,BuildFailed,PlacementFailed,Busy,InternalError}，仅用于 Qt 本地业务结果。TransportErrorKind={Configuration,Network,Timeout,ResponseTooLarge,Http,InvalidJson,Protocol}。

### 8.2 方法、信号与责任

| 签名 | 所有者与线程 | 行为 |
| --- | --- | --- |
| `CtSnapshot GetCtState() const` | Model，主线程 | 构造后可查询加载终态 |
| `SegmentationSnapshot GetSegmentationState() const` | Model，主线程 | 返回一致值；后台不直接修改该快照 |
| `OperationResult StartSegmentation()` | Model，主线程调用 | 先设置 running，再校验/查缓存/启动任务；重复启动返回 Busy，不另开任务 |
| `void segmentationStateChanged(SegmentationSnapshot state)` | Model 信号 → Control | 主线程发布开始与终态；先更新 Model，再发信号 |
| `WorkflowSnapshot BuildGuidanceSnapshot() const` | Control，主线程 | 验证一致性后复制；不能从网络线程读取 VTK |
| `OperationResult TryAddPoint(std::array<double,3> point)` | Control，主线程 | 有限坐标、CT 成功、计数 <3；成功后同时提交点容器、切片点和版本 |
| `OperationResult TryDeletePoint()` | Control，主线程 | 无点返回 NoPoint；成功则清理对应切片/三维对象并失效定位 |
| `OperationResult RequestProsthesisUpdate(IAirNavi::SentValue parameters)` | Control，主线程 | 校验点/参数后创建输入快照，置 running 并提交后台任务；成功返回只表示已受理 |
| `void ApplyProsthesisJobResult(ProsthesisJobResult result)` | Control，主线程 | 校验任务代次、点位版本；过期结果丢弃；应用后再置 ready/failed |
| `SaveResult SaveCurrentPlan()` | Control，主线程 | 前置校验、捕获 PlanPayload 与版本，同步原子提交，更新状态；所有保存入口复用 |
| `RequestContext RequestGuidance(WorkflowSnapshot state)` | AgentHttpClient，主线程 | 生成 UUID/generation，序列化新请求；失败结果异步排队发出，保证调用方先收到 context |
| `void Invalidate()` | AgentHttpClient，主线程 | generation 先递增再 abort，防止同步 finished 回调误用 |
| `void guidanceReady(RequestContext context, GuideResponseV2 response)` | HTTP → Control | 先结构验证；Control 再比较当前快照版本及最新 context |
| `void guidanceFailed(RequestContext context, TransportError error)` | HTTP → Control | 错误也必须过滤过期上下文 |
| `OperationResult ExecuteGuidanceNavigation(Action action, RequestContext context)` | Control，主线程 | 必须来自当前已展示建议、匹配版本/能力/前置；只导航 |

`ProsthesisJobInput` 明确定义为：quint64 generation、quint64 pointRevision、3 个点的值拷贝、IAirNavi::SentValue 的五个 double（upRadius/upHeight/midRadius/downRadius/downHeight）、现有 material 枚举、可选的当前矩阵值拷贝。五个尺寸要求有限且 >0；几何有效性由建模结果校验，不新增临床规格范围判断。

`ProsthesisJobResult` 为：generation、pointRevision、bool success、optional<ProsthesisErrorCode> error、QString localMessage，以及任务独占的网格输出和 optional<4×4 矩阵>。失败不携带可应用结果；成功交接后工作线程不再访问输出。Model 的分割任务同样捕获值输入，返回带 generation 的成功/失败结果，统一在主线程提交终态。

### 8.3 线程与生命周期

- Model、Control、View、HTTP 客户端、状态版本和 actor 只在主线程访问。后台只处理任务自有数据，不捕获可随窗口销毁的 this 来修改界面。
- Qt 跨线程值类型使用 Q_DECLARE_METATYPE 和 qRegisterMetaType，完成结果经 queued connection / QFutureWatcher 送回主线程。
- 分割和假体各自仅允许一个任务；任务计数涵盖两类。正常关闭在有任务时拒绝并显示等待，终态后可再次关闭；不自动替用户退出。
- 假体任务运行时仍可发生合法点位变化：立即使旧任务 generation 失效，状态变 needs_reposition、清空错误、隐藏旧定位；旧任务结束仅释放资源，不恢复 ready。新建模任务在旧任务清理后才允许受理。
- 不复用当前异步函数在工作线程直接访问 m_view / actor 的方式；迁移线程归属是实施前置工作。

## 9. 状态版本与保存时序

- state_revision 和 plan_revision 初始 0；任何对外可观察快照变化只增加一次 state_revision，同一批同步修改合并为一次提交。
- request_id / generation 每次请求新建；同状态刷新不增加 state_revision。计数到安全上限后停止引导并提示重启，不回绕。
- 点位真实变化增加本地 pointRevision，并使定位失效。points 或最终矩阵变化增加 plan_revision；纯页面、窗宽窗位、透明度、显示材质、未持久化尺寸不增加内容版本。
- 同一次用户操作内的多个 setter 只提交一次版本。即使内容后来改回旧值，版本也不倒退，必须重新保存。
- 点数不足、点位变化或建模开始导致 ready 失效时：save_status=not_started、save_error=null，保留历史 saved_plan_revision。假体失败后的再次编辑同样清除过期错误。
- 保存前要求 CT 成功、三点有限、假体 ready 且绑定当前 pointRevision、最终 4×4 矩阵有限。前置失败记录 SAVE_PRECONDITION_FAILED，不写文件。
- 本版保存为同步主线程操作，不进入嵌套事件循环，不允许保存期间重入编辑/保存。先置 running，再捕获 PlanPayload 和版本，写入 QSaveFile，只有 commit 成功才置 succeeded 并更新保存版本。
- 失败保留上一次保存版本，置 failed 和固定错误码；原有关闭失败询问仍可保留，但必须在保存方法返回后弹出。
- 同步保存可能在下一次事件循环前完成，因此允许 HTTP 只观察终态；规则支持 running 便于测试和将来实现，不能依赖每个中间状态都被发送。
- 保存文件只写原有 points 和 rotation_matrix 两个键，不新增 schema_version、不写假体规格、不新建第二个文件。完整假体可恢复文件另立版本设计。

重启后首次保存版本仍为 null；本版不解析旧文件来恢复“当前已保存”。显示的“已保存”只描述本进程当前有效取点和矩阵，不代表跨进程恢复能力。

## 10. 请求时序、错误过滤与交互

1. 业务事务完成后提交状态；立即调用 Invalidate 并清除主建议及告警的旧动作。
2. 同一事件循环的多次刷新合并；最终快照未变时，用户手动刷新仍发送新请求。
3. 网络客户端生成 context 后返回，响应或错误均异步发信号。
4. 客户端验证 HTTP 状态、体积、JSON、全部字段、UUID 和枚举；Control 同时检查最新 generation、request_id、state_revision 与当前快照。
5. 无 HTTP 错误 ID 或 ID=null 时使用本地 context；非 null 错误 ID 必须匹配。过期成功/错误都静默丢弃。
6. 应用响应时要求所有非 null 动作属于本次 supported_actions 且本地存在；unknown reason/alert/action/protocol 均视为协议错误，整条响应不执行。
7. 点击时再次核对 context 及前置条件；若失效则刷新，不执行旧动作。

Backend 不使用 state_revision 判断服务端新旧，也不维护请求历史。V2 的 request_id 只用于关联，不是幂等存储键。Qt 同一快照连续刷新出现乱序时，generation 与 request_id 能区分，不能仅比较 state_revision。

## 11. Backend 实现边界与验证

设计实施文件：`app/models/schemas_v2.py`、`app/services/guidance_v2.py`，在入口挂载 V2；复杂度需要时拆独立 router。业务规则不读文件、不调用模型、不写数据库、不修改输入。V2 错误中间件/处理器须隔离路径，并在读取实际请求字节时限制大小。

日志只记录 request_id、协议/规则版本、耗时、状态码、原因代码；不记录全量请求、原始错误进程输出。500 详细堆栈只留服务端日志，不能返回客户端。

验收分三层：

1. 设计验证：OpenAPI 3.1 校验、YAML/JSON 等价、共享样例 Schema、跨字段约束、规则匹配、关联和能力过滤。
2. Backend 实施验证：相同样例实际调用 V2，检查状态和响应；所有 V1 回归继续通过；传输错误与超限也实际执行。
3. Qt 实施验证：Qt 事件序列、线程归属、过期任务、导航、同步保存与 Windows 完整构建；以真实业务操作验证状态来源。

本次只完成第 1 层；不能把设计样例验证记为 V2 已上线或 Qt 构建通过。

## 12. D0 交付与变更记录

D0.1：分割非阻断、独立告警、保存范围和失效规则已确定。D0.2：状态及 I01–I09 已定义。D0.3：OpenAPI 与错误契约已输出。D0.4：内部值类型、方法、信号、线程和保存时序已定义。D0.5：主规则、告警、导航映射已确定。D0.6：共享正反例及 Qt 序列已输出。D0.7：统一设计版本 2.0.0，验证结果见检查记录。

这是一份可实施的设计基线，不是外部签字或产品验收记录。后续调整须先修改本文、机器契约和样例，再实现；若改变保存范围、分割前置条件或动作执行边界，必须明确记录设计变更，不能在实现中隐式扩大范围。
