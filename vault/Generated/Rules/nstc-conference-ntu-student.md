---
entity_type: "rule"
entity_id: "nstc-conference-ntu-student"
aliases: ["臺大學生在線上系統的校內送件：機構彙送日前一日17:00。"]
rule_kind: "relative_deadline"
actor: "student"
scope: "ntu"
cycle: "current"
review_status: "pending"
managed: true
tags: ["opengsa/rule"]
---

# 臺大學生在線上系統的校內送件：機構彙送日前一日17:00。

> [!info] 自動產生的資料檢視
> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。

[[Generated/Programs/nstc-grad-conference-policy|國科會研究生國際會議補助]]

## 結構化欄位

```json
{
  "anchor_rule_id": "nstc-conference-institution",
  "offset": -1,
  "unit": "day",
  "time": "17:00",
  "timezone": "Asia/Taipei"
}
```

## 證據

- [[Generated/Sources/doc-82e732a493acd30b20ee2163|臺大國科會會議補助程序]] · body / text-block 298
  - revision: `1c27ab87860638bc6dc2f5970c724c2721e9cc17b96641a4c4a72bfd3bcd8580`
  - block hash: `59677d18641c32944191870caa446739717856a455b61683a298907f9c709196`

## 依賴的上游規則

[[Generated/Rules/nstc-conference-institution|nstc-conference-institution]]
