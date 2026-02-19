# Deferred Items - Phase 04

## Pre-existing Issues

1. **tests/slack/test_triggers.py** imports `negotiation.slack.triggers` which does not exist yet. This is a test file created ahead of the triggers module (likely for 04-02). The test file causes collection errors when running `pytest tests/slack/` but is not related to 04-03 work. Will be resolved when 04-02 creates the triggers module.
