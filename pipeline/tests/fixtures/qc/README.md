# QC fixtures (A10)

`ninja.json` (known negative: mixed-style render) and `rocket.json` (known
positive) pin the vision-model responses from the calibration runs — scores,
rubric version, and threshold — plus a prose description of the source render.

No binary images are stored: the deterministic suite
(`test_rubric_calibration.py`) runs the pins through the real rubric code
path (`parse_scores` → `evaluate`), and the live script
(`scripts/qc_calibration.py --live`) performs the same assertion against real
vision calls. If live disagrees with a pin, the pin is stale — refresh it and
record the drift; never loosen the assertion.
