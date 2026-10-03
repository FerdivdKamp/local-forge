# Review answer key

The seeded defect is in `checkout.py:3`: a percentage discount is subtracted as a fixed amount. For example, `charge(200, 10)` returns 190 instead of 180. A valid review should identify this behavior and location. Extra unsupported findings count as false positives. Human adjudication is required.
