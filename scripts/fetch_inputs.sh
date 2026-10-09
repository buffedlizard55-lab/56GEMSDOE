#!/bin/bash
# Alias referenced by registry/input_pins.json ("scripts/fetch_inputs.sh does this end to end").
# The implementation lives in download_competition_data.sh (the name used by the standing brief).
exec bash "$(dirname "$0")/download_competition_data.sh" "$@"
