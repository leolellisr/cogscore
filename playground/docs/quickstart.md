# Quickstart

## Validate a result bundle

Activate the local Python environment:

```bash
source .venv/bin/activate
Validate a motivation result bundle:
python tools/validate_result_bundle.py data/uploads/example_motivation_bundle.zip
Validate an attention result bundle:
python tools/validate_result_bundle.py data/uploads/example_attention_bundle.zip
Expected output:
[OK] Result bundle is valid.
Result bundle structure
See:
docs/result_bundle_format.md
