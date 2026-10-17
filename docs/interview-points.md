# Interview points

Short, honest talking points for Jagadish-governed-data-agent. Every number quoted is from the
real run shown in the README.

- Governance before retrieval: the retriever never sees a denied source, so nothing can leak through the answer.
- Every decision cites a rule ID such as POL-ROLE-03, which makes access reviews and audits straightforward.
- Real run: the same salary question is refused for an analyst and answered for a manager; five requests, five ledger entries, chain verified.
- Honest gap: retrieval is keyword-based, so an 'average' question returns rows; text-to-SQL is the next layer.

## Likely follow-up questions

- Why not filter the answer instead? (Once data is in the model context it can leak; deny before retrieval.)
- How would you keep the registry current? (Generate it from Purview, not by hand.)
- What about prompt injection in documents? (Documents only reach allowed users; add content scanning for instructions.)
