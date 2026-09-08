# 08 — Frontend

## Goal

Provide a clear scientific decision-support interface, not a UI-heavy chatbot.

## Layout

Suggested layout:

```text
+------------------------------------------------------+
| Darukaa BioIntel                                     |
+---------------------------+--------------------------+
| Conversation              | Environmental Profile   |
|                           |                          |
| User message              | Region                   |
| Assistant assessment      | Soil                     |
| Recommendation cards      | Climate                  |
| Evidence                  | Land use                 |
|                           | Biodiversity             |
+---------------------------+--------------------------+
```

## Main UI Components

### 1. Conversation
- text input
- message history
- clarification questions
- recommendation responses

### 2. Environmental Profile
Show known variables and their values.

Unknown fields can be displayed as missing rather than guessed.

### 3. Recommendation Card

Each recommendation should visibly contain:
- action
- why it works
- impacted metrics
- time horizon
- evidence

### 4. Evidence Section
Show source title/publisher and concise relevant evidence.

### 5. Limitations
Show uncertainty or missing evidence clearly.

## UX Priorities

1. readability
2. evidence visibility
3. environmental context
4. recommendation clarity
5. responsive behavior

Do not spend disproportionate effort on:
- animations
- decorative effects
- complex navigation
- unnecessary dashboards

## Scientific Transparency

Avoid presenting inferred values as measured facts.

Use labels such as:
- User provided
- Retrieved
- Not provided
- Evidence limited

## Accessibility

Use semantic HTML, readable contrast, keyboard-friendly controls, and clear loading/error states.
