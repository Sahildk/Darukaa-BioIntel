# 00 — Project Brief

## Objective

Build an AI-powered conversational system that:
1. Maintains a structured knowledge base of biodiversity and environmental metrics.
2. Understands user queries about ecosystems, land, and climate conditions.
3. Generates actionable, non-obvious recommendations to improve biodiversity.
4. Supports every recommendation with scientific reasoning and evidence.

## Challenge Positioning

The challenge explicitly states that this is not a UI-heavy application. The priority is depth of thinking, system design, and scientific reasoning.

The target behavior is an AI environmental scientist rather than a generic chatbot.

## Required Knowledge Areas

The knowledge layer should cover:
- Soil health: pH, organic carbon, moisture
- Land use / land cover
- Biodiversity indicators: species richness, habitat diversity
- Climate factors: temperature, rainfall
- Human impact: pollution, deforestation

## Required Capabilities

### Knowledge System
Use a retrievable knowledge layer rather than relying only on prompts. The challenge explicitly allows approaches such as:
- RAG
- embeddings
- vector databases
- structured datasets

The knowledge base should index credible research papers, reports, and/or environmental datasets.

### Conversational Intelligence
The system should:
- ask clarifying questions when inputs are incomplete
- maintain multi-turn context
- adapt later responses based on previous information

### Evidence-Backed Recommendations
Each recommendation must contain:
- what to do
- why it works
- which environmental metric improves
- a reference to a study/report/model

### Multi-Metric Reasoning
Connect multiple variables, including:
- soil health ↔ biodiversity
- water availability ↔ species survival
- land use ↔ habitat fragmentation

### Input
Mandatory:
- natural-language text

Also support:
- structured input such as JSON

Bonus:
- geographic coordinates/spatial context

### Output
Each recommendation should clearly contain:
- recommendation
- impacted metrics
- time horizon: short / medium / long term
- confidence level where useful

## Official Evaluation Weights

- Depth of Reasoning: 30%
- Scientific Grounding: 25%
- Knowledge System Design: 20%
- Conversational Intelligence: 15%
- Output Clarity: 10%

## Official Constraints

- No generic LLM-only solution.
- No shallow or obvious recommendations.
- Demonstrate knowledge grounding and reasoning.
- Handle at least 3 environmental variables together.

## Example Scenario From Challenge

Input:
- Soil organic carbon: 0.3%
- Rainfall: low
- Crop: monoculture wheat
- Region: semi-arid

Expected direction:
- suggest an intervention such as agroforestry/intercropping
- explain impact on soil carbon and biodiversity
- provide measurable improvement estimates only when supported by evidence
- reference credible sources such as FAO or IPCC

Do not invent numerical improvement estimates if the retrieved evidence does not support them.
