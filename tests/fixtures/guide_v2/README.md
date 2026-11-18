# V2 共享契约样例

契约版本：2.0.0。规则版本：rcviplan-guidance/1.0.0。

这些是开发前定义的设计样例，未调用 V2 业务实现，也不表示 Qt 运行验收通过。

- `http-cases.json`：25 个正常响应、24 个非法请求；每项包含 request、expected_status、expected_response。状态矛盾用 invariant 标出 I01–I09。
- `transport-cases.json`：原始 JSON、Content-Type、体积超限、根类型和注入 500 的测试规范；body_repeat 指定重复字符构造原始请求体，fault 指示后续接口测试注入点。
- `qt-sequences.json`：14 项操作/请求序列及预期，供 Qt Test 和人工联调实施，当前仅检查规范完整。

Qt 与 Backend 固定引用相同契约版本及样例文件，复制时记录来源提交号。expected_response 是规则版本 1.0.0 的精确预期；比较 JSON 忽略对象键顺序，数组顺序必须一致。测试使用请求内的 UUID 原样关联，不要求测试样例彼此使用不同 UUID；真实客户端每次请求必须新建 UUID。

完整语义、动作限制及校验顺序以 [接口设计](../../../docs/contracts/guide-v2-interface-design.md) 为准。

从项目根目录，在单独虚拟环境安装 `docs/contracts/requirements-validation.txt` 后运行：

```bash
python docs/contracts/validate_contract.py
```

验证范围：OpenAPI 结构、请求/响应 Schema、状态约束、全部主规则与分割告警、关联字段及动作能力过滤。它不是线上请求测试，不验证 Qt 控件是否已经实现。
