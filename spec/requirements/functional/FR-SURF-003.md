---
type: Functional Requirement
title: "Gemini Enterprise app"
description: "Users run workflows from the Gemini Enterprise app, and the platform acts as the user signed in to Gemini Enterprise."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: planned
---

# Statement

The system shall make its workflows available in the Gemini Enterprise app through agents deployed on Gemini Enterprise Platform, acting with the identity of the user signed in to Gemini Enterprise.

# Acceptance criteria

- The platform's agent deployment is registered in the organisation's Gemini Enterprise app.
- The registration carries an OAuth authorization, so that after the user consents once Gemini Enterprise passes that user's token to the agent on each call.
- The authorization requests the `openid` and `email` scopes, so the platform can read the user ID and account from the token ([DEC-0001](../../decisions/DEC-0001.md)).
- The agent makes every platform call with that token. A call that arrives without a user token is refused; the agent never falls back to its own service identity.
- A user can start a workflow, supply its inputs in conversation and receive its result with links to its artifacts.
- A human task raised by a run started from Gemini Enterprise can be answered by the same user in the Gemini Enterprise conversation or in sdlc_ui; whichever answers first wins, and the other then shows it as answered.
- The question in Gemini Enterprise is short (approve or reject, pick findings, confirm a scope change, supply a value); a long document is linked to its preview in sdlc_ui rather than shown in full.

# Notes

Waits for identity mode `oauth`, switched off for now ([DEC-0010](../../decisions/DEC-0010.md)).

Google documents this flow: Gemini Enterprise obtains an OAuth access token or ID token on behalf of the signed-in user after consent and sends it in the `Authorization` header of calls to a registered A2A agent; an ADK agent on Agent Runtime receives it through the authorization ID named in its registration (the authorization needs the `cloud-platform` scope). The platform registers one A2A agent, the [A2A router](FR-SURF-002.md), for the whole catalog and ad-hoc chat.

To verify: that Gemini Enterprise shows an A2A task in the *input-required* state as a question in the conversation and sends the user's reply, with the user's token, back to the A2A router.

# Citations

[1] [Register and manage A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
[2] [Register and manage ADK agents hosted on Agent Runtime](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
