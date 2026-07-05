# Standard 000: 标准文档地图

## 1. 目的

本文档定义 `token_parse_sys` 的标准文档组织方式。

后续人或 agent 在新增功能、修改层级边界、推进生产、淘汰旧口径时，应先找到对应层级标准，再执行代码或配置变更。

## 2. 标准文档分类

```text
docs/standards/
  000-standards-map.md
  001-system-structure-and-model-guidance.md
  002-data-foundation-integration.md
  003-remote-system-execution-layout.md
  004-experience-primitive-label-standard.md
  005-production-promotion-standard.md
  layer-standard-template.md
  layers/
    010-data-foundation-layer-standard.md
    020-l0-data-access-layer-standard.md
    030-l1-analysis-snapshot-layer-standard.md
    040-research-layer-standard.md
    050-l2-primitives-layer-standard.md
    060-l3-labels-layer-standard.md
    070-l4-strategy-dsl-layer-standard.md
    080-l5-signal-engine-layer-standard.md
    090-l6-backtest-engine-layer-standard.md
    100-observation-optimization-layer-standard.md
```

## 3. 每层标准必须覆盖的问题

每一层标准文档必须覆盖：

- 层级定义。
- 所有权和职责。
- 输入和输出。
- 不允许做什么。
- 生产准入。
- 生产准出。
- 什么时候可以迭代增加。
- 什么时候必须淘汰或降级。
- 质量和异常监控。
- 复杂性控制。
- agent 执行检查清单。

## 4. 状态词汇

统一状态：

```text
research_only
candidate
production_candidate
approved_production
test_tracking
active_production
deprecated
```

不同层可以只使用其中一部分，但不能随意发明同义状态。

## 5. 使用规则

当新增功能时：

```text
1. 先判断属于哪一层。
2. 阅读对应层级标准。
3. 判断是 research_only、candidate 还是 production_candidate。
4. 如果要进入生产，必须运行 production_promotion_review。
5. 修改 registry 或 workflow 后补测试。
6. 文档、代码、配置必须同步更新。
```

当 agent 不确定归属时：

```text
默认放在 research 或 workflows，不要直接放入基础生产层。
```
