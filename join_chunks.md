1️⃣ Step 1 — Chunk the text
chunks = chunk_text(text)

Here, your long article is split into multiple smaller “chunks” of ~800 tokens each.

Each chunk is small enough for the model to process without hitting its token limit.

For example, if your article has 2500 tokens and chunk size is 800 → chunks will be 4 items:

tokens 0–799

tokens 800–1599

tokens 1600–2399

tokens 2400–2499

2️⃣ Step 2 — Summarize each chunk
chunk_summaries = []
for chunk in chunks:
    chunk_summaries.append(summarize_chunk(chunk))

Each chunk is sent to summarize_chunk() which:

cleans extra spaces

tokenizes the chunk

runs the model to generate a summary

The result is one summary per chunk

Example:

chunks = [chunk1, chunk2, chunk3]
chunk_summaries = [summary1, summary2, summary3]
3️⃣ Step 3 — Combine the chunk summaries
combined_summary = " ".join(chunk_summaries)

After summarizing chunks individually, you join them into one combined text.

This combined summary may still be too long or redundant.

Example:

summary1 = "AI is transforming industries."
summary2 = "AI is used in healthcare and finance."
summary3 = "AI will continue growing in the future."
combined_summary = "AI is transforming industries. AI is used in healthcare and finance. AI will continue growing in the future."
4️⃣ Step 4 — Optional final summary pass
if len(chunk_summaries) > 1:
    final_summary = summarize_chunk(combined_summary)
    return final_summary

If there was more than one chunk, we summarize the combined text again.

This creates a short, clean, final summary.

Example final output:

"AI is transforming industries, including healthcare and finance, and will continue growing."
5️⃣ Step 5 — Return result
return combined_summary

If the text was short enough to fit in one chunk, we just return the first chunk summary.

Otherwise, we return the final cleaned summary from step 4.