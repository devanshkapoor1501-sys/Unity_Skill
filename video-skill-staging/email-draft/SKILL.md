---
name: email-draft
description: Create real Gmail drafts, verify them, and open every draft for review in a separate in-app browser tab. Use when Riley invokes /email-draft, asks to draft one or more Gmail messages, asks Codex to choose actionable inbox conversations and prepare replies, or wants saved Gmail drafts opened for review without sending them.
---

# Email Draft

Create saved Gmail drafts through the Gmail connector, verify them, and open each one in a separate in-app browser tab. Never send a message unless Riley separately and explicitly asks to send it.

## Workflow

1. Determine the draft targets.
   - If Riley names recipients or threads, use those.
   - If Riley asks to pick a number of people from the inbox, search a clear recent timeframe, exclude newsletters and automated noise, and prioritize direct requests, overdue replies, customer issues, scheduling, and qualified opportunities.
   - Read each selected thread before drafting. Do not rely on snippets when surrounding context could change the reply.

2. Write each draft.
   - Keep the language concise, natural, and ready to send.
   - Preserve recipients, CCs, facts, dates, and links from the thread.
   - Do not invent commitments, completed actions, prices, availability, or missing facts.
   - For replies, use the exact Gmail message ID as `reply_message_id` and keep the thread's subject. Gmail may reject a reply draft when the subject does not match.
   - Check group or support aliases carefully. Address the actual person when the visible sender is an alias and the thread provides the person's email.

3. Save each draft with `mcp__codex_apps__gmail_create_draft`.
   - Use `content_type="text/plain"` unless formatting is materially useful.
   - Create drafts only. Do not call a send action.

4. Retrieve and open each draft through the Gmail connector.
   - Take the `message_id` returned by `gmail_create_draft`.
   - Call `mcp__codex_apps__gmail_read_email` with that `message_id`.
   - Verify the returned message has the `DRAFT` label and that recipient, subject, and body match the intended draft.
   - Use the returned `display_url` to open the verified draft in a new in-app browser tab.
   - Do not construct or guess a Gmail URL from `draft_id`, `message_id`, or `thread_id`. The connector's `display_url` is the reusable API-native link.
   - If `display_url` is missing, retry the read once after confirming the draft with `gmail_list_drafts`. If it remains missing, report the missing link instead of inventing one.
   - Open every verified draft in its own new tab, keep those tabs open as deliverables, and bring the in-app browser into view for Riley.
   - Do not print, expose, or hyperlink the `display_url` in the chat response when the tab opened successfully.

5. Return the results.
   - Lead with the fact that the drafts are saved, unsent, and open in separate browser tabs.
   - Return exactly one bullet per draft in this format:

     `- Recipient - Subject - twenty-word summary`

   - The summary must describe what the drafted reply says, not merely summarize the incoming message.
   - Make every summary exactly 20 whitespace-delimited words. Hyphenated terms count as one word. Do not count the recipient or subject as part of the summary.
   - Validate every summary with `scripts/check_summaries.py` before responding. Revise any line that does not equal 20 words.
   - End with a brief reminder that nothing was sent. Do not add inbox-triage commentary unless Riley asks for it.

## Example

`- Michael - Agent Native Podcast - Confirms tomorrow's recording time, directs Michael to the calendar's Google Meet link, and says no formal preparation is required beforehand.`

The example summary contains exactly 20 words.
