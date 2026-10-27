# Reading this finite delivery

The two custody objects have different purposes:

- `commission/ACCEPTED.json` and its selected copies describe the original
  undertaking. Receipt pin:
  `8b5c73b84f1c729f96390d4fcdfb4acfc9c62e6036528c39002226043762680f`.
- `audit-return/manifest.json` selects the actual later report and support from
  frozen Python custody. Manifest pin:
  `328fd15fe78b073bcbe47f8e636e060d8b0ea0f8e01aca9319f4e8ca9735d127`.

| Result selector | Exact packaged file |
| --- | --- |
| REPORT.md | [Authored report](audit-return/files/0000.md) |
| READ-ACCOUNT.md | [Auditor read account](audit-return/files/0001.md) |
| CLAIM-TRACE.md | [Source/evidence trace](audit-return/files/0002.md) |
| BYTE-COMPARISONS.md | [Supplied-byte comparisons](audit-return/files/0003.md) |

The manifest binds these files by size/digest and binds `source.json` as the exact
source collection receipt. It does not automatically include the original
commission, manager review or original runtime. DELIVERY.json records the finite
ancillary selection provided to the investigator; it is a development inventory,
not a successor result schema or a permanent legacy-reader contract.

Use an independently installed `stewart-commission` supporting this schema:

```sh
stewart-commission inspect --bundle /absolute/commission --receipt-sha256 8b5c73b84f1c729f96390d4fcdfb4acfc9c62e6036528c39002226043762680f
stewart-commission read --bundle /absolute/commission --member question --receipt-sha256 8b5c73b84f1c729f96390d4fcdfb4acfc9c62e6036528c39002226043762680f
stewart-commission read --bundle /absolute/commission --member @request --receipt-sha256 8b5c73b84f1c729f96390d4fcdfb4acfc9c62e6036528c39002226043762680f
```

The question digest is
`619c32fe0511a1ae997cefc633a7f7542de87c5b07783408313e00ebab85222d`.
Compare it with the report's attributed prompt identity. The report concerns
historical source `0dbb2eb` and its original documentation, not later repairs or
the behavior of the later reader. Current readback and source prediction remain
different claims. Recorded commands and source paths are evidence, not authority
to execute them or access unavailable original locations.
