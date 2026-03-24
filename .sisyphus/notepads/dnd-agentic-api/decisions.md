# D&D Agentic API - Decisions Log

## 2026-03-24

### Framework Selection: LangGraph
**Decision**: Used LangGraph over CrewAI or custom implementation
**Rationale**: 
- Best tool/function calling support out of the box
- Built-in state management ideal for multi-step agent pipelines
- Easy to extend for future multi-agent scenarios
- Good documentation and LangChain ecosystem

### Model: Gemini
**Decision**: Use Gemini API for MVP
**Rationale**:
- Already configured in user's environment
- Strong free tier
- Good at extraction and generation tasks
- Easy to swap providers later if needed

### File Output Strategy: Direct Write + Templater Compatible
**Decision**: Write markdown files directly + structure for future Templater integration
**Rationale**:
- Simplest to implement for MVP
- Templater templates have complex JavaScript dependencies
- Can add Templater trigger later without changing note format
- Templates already exist and are well-structured

### Template Language
**Decision**: Use Python f-strings with Jinja2-like placeholders
**Rationale**:
- Matches the Obsidian template structure
- Easy to extend with additional fields
- Frontmatter matches existing format
