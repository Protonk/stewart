---
stewart: question/2
# Question family: open-inquiry, inquiry-framing or comparison.
# Run `stewart help forms` to read each family's instructions.
family: comparison
material-roles: [{"role":"alternative","source":"materials/a.py","label":"A"},{"role":"alternative","source":"materials/b.py","label":"B"},{"role":"criterion","source":"materials/requirements.txt"}]
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
Compare implementations A and B against R1 and R2 under the supplied restart assumptions. Explain the tradeoffs supported by this packet.
