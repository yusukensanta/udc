"""The reference configuration of PRD §13.3.

An existing single-binary engine (the DuckDB CLI) driven by a script that adds the four things a
careful engineer would add around it:

1. a per-attempt staging prefix,
2. a row-count check that reads the staged output back,
3. a ledger of completed units, so that a re-run skips them,
4. a completion marker written after the output is in place.

It is the baseline UDC is measured against (hypotheses H2 and H3), so it is meant to be a fair,
ordinary implementation: not a straw man, and not a reimplementation of UDC.
"""
