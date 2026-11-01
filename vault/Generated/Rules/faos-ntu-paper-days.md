---
entity_type: "rule"
entity_id: "faos-ntu-paper-days"
aliases: ["臺大校內：基金會截止前5日將紙本送秘書室；日別與假日調整未載明。"]
rule_kind: "relative_deadline"
actor: "student"
scope: "ntu"
cycle: "2025-05-22"
review_status: "pending"
managed: true
tags: ["opengsa/rule"]
---

# 臺大校內：基金會截止前5日將紙本送秘書室；日別與假日調整未載明。

> [!info] 自動產生的資料檢視
> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。

[[Generated/Programs/faos-student-conference|傑出人才基金會優秀學生出國開會補助]]

## 結構化欄位

```json
{
  "anchor_rule_id": "faos-agency-months",
  "offset": -5,
  "unit": "day",
  "day_basis": "not_stated",
  "holiday_adjustment": "not_stated",
  "delivery": "paper_received",
  "office": "臺大秘書室"
}
```

## 證據

- [[Generated/Sources/doc-c327b135dc202bdf07bef717|臺大秘書室申辦提醒（114.5.22）]] · PDF page 1
  - revision: `8f93b2438eb64b87e16334fbef726ad3ed17fab5418fa628dfab16c85a38738a`
  - block hash: `2a5bedaf1433ff3161df89dd81354d687f7e079890bcdb74760632fac97b1eee`

## 依賴的上游規則

[[Generated/Rules/faos-agency-months|faos-agency-months]]
