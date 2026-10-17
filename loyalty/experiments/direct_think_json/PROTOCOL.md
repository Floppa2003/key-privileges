# Direct think=true JSON probe

User-selected simplification: send the full frozen evidence directly to Qwen and request the final JSON in one call.

- Qwen3.5-4B, same pinned local weights/runtime.
- `think=true`.
- All frozen 1024px images and full text.
- TARGET and the exact practical JSON schema are visible in the model message.
- The same schema is also passed as Ollama `format`.
- `num_predict=8192`; request timeout 1800s.
- One request per case, no retry for a preferred answer.
- No intermediate description, no second converter, no Jev, no merchant-specific rules, no response repair.
- Four familiar diagnostic cases only: museum, bookshop, theatre, Nevsky hotel.
- publication_allowed=false; no production/Sheets/main changes.

Semantic review remains separate from schema validity. A sensible card-presenting hint is not itself a fatal error; wrong programme attribution, wrong benefit/value/deadline, or lost material conditions are material errors.
