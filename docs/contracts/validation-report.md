# V2 接口设计检查记录

日期：2026-10-14。契约：2.0.0。规则：rcviplan-guidance/1.0.0。

## 实际执行

使用 Python 3.12 项目解释器，临时目录中的 jsonschema 4.23.0、openapi-spec-validator 0.7.2、PyYAML 6.0.3 校验设计产物；没有修改项目运行依赖。

运行 `docs/contracts/validate_contract.py`，结果：

- OpenAPI 3.1 校验通过；YAML 与 JSON 等价。
- 25 个正常请求/响应样例通过 Schema、状态、关联、动作过滤和规则模板检查。
- 24 个非法请求被结构或一致性校验拒绝；错误响应 Schema 与预期错误分类通过。
- 全部 12 条主规则、3 个分割告警分支、I01–I09 均有样例覆盖。
- 5 个传输错误响应结构通过校验；未实际发送这些 HTTP 请求。
- 14 个 Qt 时序验收规范包含操作和预期；未执行 Qt 操作。
- 文档 JSON 示例、相对文件链接及差异空白检查通过。

## 源码核对与设计结论

已核对 RCVIPlan 的 page_segment / pb_autoSeg、page_selectPoint / pb_pointPick、page_navigation / pb_sentSetting 和 ShowSentSettingView；新增 pb_savePlan 明确列为待实施入口。

已核对 SaveSentPlan 只保存 points / rotation_matrix，因此本版维持文件格式并收窄保存提示。已核对 InitSentModel / UpdateSentModel 为异步逻辑，因此协议补充假体 running / failed，并规定主线程提交、任务代次过滤与生命周期处理。

## 未执行与使用限制

没有实现或启动 V2 端点，没有重新运行 V1 业务测试，没有编译 Qt，没有执行 Windows 联调或真实文件保存。本记录验证设计文件的内部一致性，不证明业务实现满足协议。

下一步：Qt Q1 与 Backend B1 按本契约实现；实现完成后，将相同共享样例用于真实接口测试，并执行 Qt 时序和联合验收。
