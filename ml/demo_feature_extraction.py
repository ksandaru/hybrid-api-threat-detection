"""Standalone demo: compares payload-level feature extraction on a benign
request vs. a SQL injection attack payload, using the same canonical
feature contract (features.py) the training pipeline and detection
middleware both rely on.

Run:
    .\\ml\\venv\\Scripts\\python ml\\demo_feature_extraction.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from features import extract_payload_features

samples = {
    "benign search": "laptop",
    "SQL injection attack": "' OR '1'='1' UNION SELECT username, password FROM users --",
}

for name, text in samples.items():
    print(f"--- {name}: {text!r} ---")
    for key, value in extract_payload_features(text).items():
        print(f"  {key}: {value}")
    print()
