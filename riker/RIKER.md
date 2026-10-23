# Asking Riker for help

Riker is accessed through a separate Project conversation. Requests and replies are passed between that conversation and the local Stewart agent by you.

## For the local agent

The user's “We should ask Riker for help” requests a message they can relay. For a new conversation, prepare a ready-to-paste opening using [the template](THREAD-ONRAMP-TEMPLATE.md), with the question or task, relevant context, and necessary excerpts or command outputs. Identify any files the user needs to attach; a local filesystem path alone does not make its contents available to Riker. For an existing conversation, prepare a follow-up message. The user relays messages in both directions. After receiving the reply, continue the local task in light of that assistance.

## Sending a request

1. Ask the local agent to prepare the opening message and identify any attachments.
2. Open the Riker Project and start a new conversation.
3. Paste the prepared opening message, add any context you want to supply, and attach the identified files. If assembling the opening yourself, use [THREAD-ONRAMP-TEMPLATE.md](THREAD-ONRAMP-TEMPLATE.md).
4. Send the message. The Project's instructions and core facts are already configured; they do not need to be pasted again in every thread.

## Returning the reply

Copy Riker's reply back to the local agent. For follow-up questions about the same request, continue in the existing Riker conversation and relay the new messages in both directions. Start a separate conversation for a separate request when useful.

Riker's Project permits public web search but not GitHub plugins or authenticated GitHub connectors. Supply repository-specific material explicitly when it is needed.

## Data sent to Riker

Riker may be accessed through an external service with its own data-processing and retention policies. Text, source excerpts, logs, and attachments you submit may be handled and retained under that service's policies. Check the destination and its applicable terms before sharing sensitive or restricted material; do not forward credentials or information you are not authorized to disclose.
