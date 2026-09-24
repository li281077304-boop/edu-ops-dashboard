# Standalone Widget V0.2 status

Status snapshot for this source branch. This is not a release-readiness declaration.

- PYTHON_METRICS = PASS
- CONTRACT_V2 = PASS
- PYTHON_TESTS = PASS
- ANDROID_SOURCE_IMPLEMENTED = PASS
- ANDROID_UNIT_TEST = TECHNICAL_OPEN_LOCAL_SDK_MISSING
- ANDROID_BUILD = TECHNICAL_OPEN_LOCAL_SDK_MISSING
- DEVICE_UAT = NOT_RUN

Android SDK platforms/build-tools are not installed in the standard local SDK
location. No SDK was installed and no license was accepted for this work.

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
`production_hours`, `planned_hours`, status/class normalizers, and
`weekly_average_lessons`. Rows with missing required fields, invalid dates,
unknown status/class type, or exact duplicates fail closed. Rows outside the
configured artificial month are excluded and counted in warnings.

Contract V2 carries only the 16 schedule-derived metrics requested for the
standalone card. Metrics requiring independent enrollment, revenue, or renewal
sources are not guessed or emitted as unavailable-value cards.
