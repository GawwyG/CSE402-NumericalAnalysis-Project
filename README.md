# CSE402 Numerical Analysis Project — Reproducibility

## Environment
Python 3.x, installed via:
\`\`\`
pip install -r requirements.txt
\`\`\`

## Running validation (Member E)
\`\`\`
python -m src.validation.opendss        # generate OpenDSS references
python -m src.validation.crosscheck     # compare vs Member A's NR solver
python -m src.validation.antifloat_study
\`\`\`

## Data provenance
See data/provenance.yml for the source and status (official vs.
reconstructed) of every feeder used.