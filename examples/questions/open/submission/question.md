---
stewart: question/1
# Question family: open-inquiry, inquiry-framing or comparison.
# Run `stewart help forms` to read each family's instructions.
family: open-inquiry
# Provider model used for every run of this audit.
model: claude-opus-5-5
# Existing directory in which Stewart creates the return package.
destination: /var/tmp
# Cumulative limits across all runs, from the provider's usage reports.
limit-turns: 200
limit-input-tokens: 20000000
limit-output-tokens: 400000
# Optional label for your own line of questions.
inquiry: reminder-restarts
---
Audit our app to make sure there are no bugs.
