---
name: validate-eld
description: Upload an ELD CSV through the full 7-agent validation + AI correction pipeline via the REST API. Use to verify end-to-end behavior after changes to the pipeline, correction agent, or FMCSA rules. Trigger with /validate-eld <path-to-csv>.
disable-model-invocation: true
---

Upload an ELD CSV file to the running local API and inspect the full pipeline output.

The CSV file path is provided via $ARGUMENTS.

## Steps

1. Confirm the dev server is running (Docker or bare Python on port 8000).

2. POST the file to the upload endpoint:
```bash
curl -s -X POST http://localhost:8000/api/v1/eld/upload/ \
  -F "file=@$ARGUMENTS"
```

3. Parse the JSON response and report:
   - `compliance_score`
   - `status` (PASS / FAIL)
   - `corrected_csv_available`
   - `corrected_csv_filename`
   - Number of entries in `change_log`
   - `validation_summary.errors_remaining`
   - `final_verdict` (FMCSA COMPLIANT / MANUAL REVIEW REQUIRED)

4. If `corrected_csv_available` is true, download the corrected file:
```bash
# Replace <id> with the eld_file id from the response
curl -s http://localhost:8000/api/v1/eld/<id>/corrected-csv/ -o corrected_output.csv
```

5. Report any remaining errors from `validation_summary.errors` if present.

## ELD Rules to verify in output
- No `000000` time entries injected by correction
- No records present that were not in the original file
- Zero-value login/logout events must not be flagged or corrected
