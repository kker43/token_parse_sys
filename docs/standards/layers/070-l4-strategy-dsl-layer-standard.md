# Layer Standard 070: L4 Strategy DSL 策略组合层

## 1. 层级定义

L4 定义如何使用 L3 标签进行召回、过滤、排序和策略候选构建。

它回答：

```text
哪些标签组合成一条可回测、可跟踪的策略？
```

## 2. 所有权和职责

本层拥有：

- `StrategyDSL`。
- candidate pool。
- stage pipeline。
- 策略状态。
- 策略准入规则。

本层不拥有：

- 原始数据读取。
- L2/L3 计算细节。
- 真实信号执行。

## 3. 输入和输出

输入：

- 已批准或候选 L3 标签。
- 回测准入配置。

输出：

- L4 draft 策略。
- test_tracking 策略。
- 策略配置。

## 4. 边界和禁止事项

禁止：

- 直接引用 raw close/open/amount。
- 绕过 L3 标签做策略。
- 无回测证据升级 test_tracking。

## 5. 生产准入

L4 进入 test_tracking 前必须：

- L2/L3 缺口已解决。
- L6 回测达到准入。
- 样本数足够。
- 失败案例有记录。

## 6. 生产准出

L4 可交给 L5 生成信号前必须：

- status 为 test_tracking 或 approved。
- 策略版本锁定。
- 依赖标签版本锁定。

## 7. 迭代增加规则

策略变体应批量比较，不要频繁小改线上口径。

推荐方式：

```text
strategy_x_candidate_v1
strategy_x_candidate_v2
strategy_x_test_tracking_v1
```

## 8. 淘汰和降级规则

如果观察期表现持续不达标、回撤超限、命中样本衰减，应降级为 draft 或 deprecated。

## 9. 质量和异常监控

监控：

- 召回数量。
- 策略命中率。
- 回测和实盘观察偏差。
- 标签依赖缺失。

## 10. 复杂性控制

L4 可以组合多标签，但 pipeline 阶段必须可解释。复杂组合应拆成召回、过滤、排序、风控阶段。

## 11. Agent 检查清单

- [ ] 只引用 L3 标签字段。
- [ ] 有回测结果。
- [ ] 状态升级有证据。
- [ ] 策略版本已锁定。
