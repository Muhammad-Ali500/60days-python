Chunking Function
def chunk_text(text, max_tokens=800):
    tokens = tokenizer.encode(text)
    chunks = []

    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(tokenizer.decode(chunk))

    return chunks
🧠 Step-by-Step Explanation
1️⃣ tokenizer.encode(text)

This converts your text into token IDs.

Example:

Text:

"Artificial Intelligence is powerful"

After encoding:

[31414, 21098, 16, 2436]

These numbers are what the transformer model understands.

Important:
👉 The model works on tokens, not words.
👉 One word ≠ one token.
👉 Long text = long list of numbers.

2️⃣ Why We Need Chunking

Your model can only process about:

1024 tokens

If your article has:

5000 tokens

The model will cut everything after 1024.

That means:

❌ information loss
❌ weak summary
❌ incomplete understanding

So we split the long list into smaller parts.

3️⃣ This Line Is The Core
for i in range(0, len(tokens), max_tokens):

This means:

Start at 0
Go until total tokens
Move in steps of max_tokens

If:

len(tokens) = 2400
max_tokens = 800

Then:

i = 0
i = 800
i = 1600

So we create:

tokens[0:800]

tokens[800:1600]

tokens[1600:2400]

Three chunks.

4️⃣ Slicing the Tokens
chunk = tokens[i:i + max_tokens]

This extracts a slice of the token list.

Think of it like cutting a long rope into pieces.

5️⃣ Decoding Back to Text
tokenizer.decode(chunk)

Why decode?

Because:

Model.generate() expects text input again.

So flow is:

Text → tokens → split tokens → decode back to text → summarize
📊 Visual Flow

Long Article
↓
Tokenized → [0,1,2,3,4,5,6,7,8,9,...]
↓
Split every 800 tokens
↓
Chunk 1 → summarize
Chunk 2 → summarize
Chunk 3 → summarize
↓
Combine summaries
↓
Final summary

⚠ Important Engineering Detail

Why max_tokens=800 and not 1024?

Because:

Model limit ≈ 1024
We need space for:

special tokens

summary generation

safety margin

So we keep it below limit.