# Standalone Widget V0.2 status

Status snapshot for this source branch. This is not a release-readiness declaration.

- PYTHON_METRICS = PASS
- CONTRACT_V2 = PASS
- PYTHON_TESTS = PASS (66 passed, local)
- ANDROID_SOURCE_IMPLEMENTED = PASS
- ANDROID_UNIT_TEST = PASS (3 tests, local)
- ANDROID_BUILD = PASS (Debug APK, local)
- DEVICE_UAT = NOT_RUN

An earlier GitHub Actions run `35963925513` passed on `ubuntu-24.04` for the
parallel V0.2 implementation. The current merged implementation was separately
verified locally with the test/build results above. Local Android device UAT
has not been performed.

The Android app starts with “尚未导入数据”. It imports a V2 `widget-data.json`,
validates the contract, saves the last valid payload locally, and renders from
that cache while offline. It contains no sample business figures.

The one-shot desktop command is:

```sh
edu-ops-widget --input "/path/to/排课列表.xlsx" --output "/path/to/widget-data.json"
```

If `--input` is omitted, the command discovers the newest `排课列表_*.xls` or
`排课列表_*.xlsx` under `~/Downloads` and `~/Desktop`. The metrics reuse the
repository's `ScheduleRecord`, artificial-month configuration,
`production_hours`, `planned_hours`, `is_one_to_one`, and
`weekly_average_lessons`. Production totals use completed rows only; planned
totals are separate. Rows with missing required fields, invalid dates, unknown
status/class type, or exact duplicates fail closed. Rows outside the configured
artificial month are excluded and counted in warnings.

Contract V2 carries only the 16 schedule-derived metrics requested for the
standalone card. Metrics requiring independent enrollment, revenue, or renewal
sources are not guessed or emitted as unavailable-value cards.
