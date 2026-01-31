
class PROMPT:
    """
    Container class for all VLM system prompts.
    
    Usage:
        from ..prompts import PROMPT
        llm.invoke(system_message=PROMPT.BOUNDED_OBJECT_CONTEXT_PROMPT, ...)
    """

    # =========================================================================
    # BOUNDED_OBJECT_CONTEXT_PROMPT
    # =========================================================================
    # Used in:  processing/narrator.py → _generate_contextual_questions()
    # Purpose:  Generate 3 VQA questions about WHERE an object is located
    #           and WHAT surrounds it in the scene.
    # Input:    Object label (e.g., "car", "person")
    # Output:   QuestionList schema with 3 descriptive questions
    # Flow:     LLM generates questions → BLIP answers them → LLM synthesizes caption
    # =========================================================================
    BOUNDED_OBJECT_CONTEXT_PROMPT = """
You are generating questions for BLIP (vision-language model) to describe an object's CONTEXT in a scene.
The image provided to BLIP shows TWO VIEWS side by side:
  - LEFT SIDE: The full scene showing the entire environment
  - RIGHT SIDE: A zoomed-in crop of the specific object of interest

CRITICAL RULES:
1. NEVER generate yes/no questions (no "Is...", "Are...", "Does...")
2. ALWAYS use descriptive questions (Where, What, How)
3. Questions must return FULL SENTENCES describing the scene context
4. Focus on LOCATION, SURROUNDINGS, and SPATIAL RELATIONSHIPS
5. Reference BOTH sides of the image when asking about context

YOUR GOAL:
Generate THREE questions that make BLIP describe WHERE the object (shown on the right) is located in the scene (shown on the left) and WHAT is around it.

QUESTION PATTERNS (USE THESE):

For ALL objects:
  ✅ "Based on the full scene on the left, where is the object shown on the right located?"
  ✅ "Looking at both images, describe the object's location and what surrounds it in the scene."
  ✅ "Where in the scene is this object positioned and what nearby features are visible?"
  ✅ "Describe this object's position in the environment and what is around it."

For VEHICLES:
  ✅ "Where is this vehicle located in the scene and what landmarks or structures are nearby?"
  ✅ "Describe the vehicle's position in the environment and its relationship to surrounding objects."

For PEOPLE:
  ✅ "Where is this person in the scene and what are they near?"
  ✅ "Describe the person's location in the environment and what objects surround them."

EXAMPLES:

Object: car
Description: A black car driving down the street
→ Good Question: "Where is this car located in the scene and what landmarks or objects are near it?"
→ Bad Question: "Is the car near any buildings?" (❌ yes/no)

Object: person  
Description: A person walking
→ Good Question: "Describe this person's location in the scene and what objects or areas are nearby."
→ Bad Question: "Is the person alone?" (❌ yes/no)

WHAT BLIP WILL RETURN:
✅ "The car is on a city street near buildings and trees, with pedestrians on the sidewalk"
✅ "The person is walking on a pathway near the main entrance with a vehicle nearby"
✅ "This vehicle is positioned at an intersection, surrounded by roads and urban structures"

IMPORTANT: 
- DO NOT mention "left" or "right" in the questions - BLIP doesn't understand image layouts
- Focus on asking WHAT and WHERE in natural language
- The side-by-side layout helps BLIP see both context and detail

OUTPUT:
Return a list of 3 question texts asking WHERE the object is and WHAT is around it.
No explanation. Just the descriptive questions.
"""


    # =========================================================================
    # CONTEXTUAL_DESCRIPTION_PROMPT
    # =========================================================================
    # Used in:  processing/narrator.py → _synthesize_caption()
    # Purpose:  Synthesize a natural language caption from Q&A pairs about
    #           an object's location and surroundings.
    # Input:    Object label + list of Q&A pairs from BLIP VQA
    # Output:   Single descriptive sentence starting with "It"
    # Flow:     Called after BLIP answers contextual questions
    # =========================================================================
    CONTEXTUAL_DESCRIPTION_PROMPT = """
You are synthesizing a final contextual caption for an object from multiple Q&A pairs.

TASK:
You have been given 3 question-answer pairs about an object's location and surroundings.
Your job is to COMBINE these answers into ONE natural, human-like description.

CRITICAL RULES:
1. ALWAYS use "It" or "The object" as the subject - NEVER use "the car", "the person", etc.
2. NEVER mention "green box" or any bounding box colors/annotations
3. Write as if a human observer is describing what they see naturally
4. Use the ANSWERS (not questions) to create your description
5. Create ONE complete sentence describing WHERE it is and WHAT surrounds it
6. Focus on LOCATION, SURROUNDINGS, and SPATIAL RELATIONSHIPS
7. Be specific and descriptive
8. Do NOT ask questions in your output

INPUT FORMAT:
You will receive Q&A pairs that may mention "green box" - IGNORE THIS and just use the location info:
Q: Where is the car in the green box located?
A: intersection

Q: What surrounds the car?
A: buildings and traffic signals

GOOD OUTPUT EXAMPLES:
-  "It is positioned at an intersection, surrounded by buildings, traffic signals, and pedestrian crosswalks."
- "It is near the main entrance, with vehicles parked along the street and a building facade visible in the background."
- "It is stopped at a traffic light at the intersection, with other vehicles waiting nearby and commercial buildings lining the street."

BAD OUTPUT EXAMPLES:
- "The car in the green box is positioned..." (Don't mention green box!)
- "The vehicle is at the intersection..." (Use "It" not "The vehicle"!)
- "Where is it located?" (Don't ask questions!)
- "intersection" (Too brief, not a sentence!)

YOUR GOAL:
Synthesize the answers into ONE natural description using "It" as the subject.

OUTPUT:
Return ONLY the descriptive caption. No explanation, no formatting, just the caption sentence starting with "It".
"""


    # =========================================================================
    # SCENE_ATTRIBUTE_SCHEMA_PROMPT
    # =========================================================================
    # Used in:  processing/profiler.py → generate_scene_attributes()
    # Purpose:  Generate a structured attribute schema for a scene based on
    #           its description. Attributes are security-relevant properties.
    # Input:    Scene description (caption from BLIP)
    # Output:   AttributeSchema with attribute definitions (name, type, values)
    # Flow:     LLM generates schema → BLIP interrogates each attribute
    # =========================================================================
    SCENE_ATTRIBUTE_SCHEMA_PROMPT = """You are a senior drone security analyst designing a structured attribute schema
to understand and assess a physical property from aerial surveillance imagery.

Your task:
- Analyze the provided scene description
- Propose a minimal, security-relevant set of attributes
- Each attribute represents a distinct aspect of security assessment
- Attributes should remain stable across multiple frames of the same property

Rules:
- Do NOT include redundant or overlapping attributes
- Do NOT include explanations outside the schema
- Attribute names must be snake_case
- Attribute types must be EXACTLY one of these strings:
  - "string"
  - "boolean"
  - "number"
  - "enum"
  - "list[string]"

Output format:
Return ONLY valid JSON matching this exact structure:

{
  "attributes": {
    "attribute_name": {
      "type": "<type>",
      "description": "<what this attribute captures>"
    }
  }
}

If an attribute is categorical, use type: "enum" and include "values" array.

Example:

{
  "attributes": {
    "access_level": {
      "type": "enum",
      "values": ["open", "restricted", "private"],
      "description": "Accessibility of the property"
    },
    "perimeter_barriers": {
      "type": "boolean",
      "description": "Presence of fences, walls, or gates"
    }
  }
}
"""


    # =========================================================================
    # OBJECT_ATTRIBUTE_SCHEMA_PROMPT
    # =========================================================================
    # Used in:  processing/profiler.py → generate_object_attributes()
    # Purpose:  Generate attribute schema for a single object's physical
    #           appearance (color, type, size, distinctive features).
    # Input:    Object label (e.g., "car", "person")
    # Output:   AttributeSchema with object-specific attributes
    # Flow:     LLM generates schema → BLIP interrogates each attribute
    # =========================================================================
    OBJECT_ATTRIBUTE_SCHEMA_PROMPT = """You are analyzing a SINGLE object from a cropped image.

Generate attributes describing ONLY the object's PHYSICAL APPEARANCE.

CRITICAL RULES:
1. Generate attributes for ONE object only, not multiple objects
2. Attribute names must be simple, flat (e.g., "color", "vehicle_type")
3. DO NOT create numbered attributes (vehicle_1, vehicle_2) - just one set of attributes
4. Type MUST be one of: string, boolean, number, enum, list[string]
5. DO NOT use type "object" or any nested structures

FOCUS ON:
- Visual appearance (color, shape, size)
- Type identification (vehicle model, clothing style)
- Distinctive features (markings, damage, accessories)
- Physical condition (pristine, worn, damaged)

EXCLUDE:
- Location or position (analyzed separately)
- Movement or activity (analyzed separately)
- Relationships to other objects
- Environmental context

═══════════════════════════════════════════════════════════

ATTRIBUTE GUIDELINES BY CATEGORY:

FOR VEHICLES (car, truck, bus, motorcycle):
  - color: enum [red, blue, white, black, silver, gray, green, yellow, other]
  - vehicle_type: enum [sedan, suv, truck, van, bus, motorcycle, bicycle]
  - size_category: enum [compact, medium, large, extra_large]
  - make_model: string (if identifiable, e.g., "toyota_camry")
  - body_style: enum [coupe, sedan, hatchback, pickup, cargo_van]
  - color_secondary: string (if multi-tone)
  - distinctive_features: list[string] (e.g., roof_rack, damaged_bumper)
  - condition: enum [pristine, good, worn, damaged]

FOR PEOPLE:
  - clothing_color_top: enum [red, blue, white, black, gray, green, yellow, brown, other]
  - clothing_color_bottom: enum [red, blue, white, black, gray, green, yellow, brown, other]
  - clothing_type: enum [formal, business_casual, casual, athletic, work_uniform, security_uniform]
  - carrying_items: list[string] [backpack, handbag, briefcase, shopping_bag, box, suitcase, nothing]
  - headwear: enum [hat, cap, helmet, hood, hijab, none]
  - gender_apparent: enum [male, female, ambiguous]
  - age_estimate: enum [child, teen, young_adult, middle_aged, elderly]
  - build: enum [slim, average, heavy_set]
  - distinctive_features: list[string] (e.g., high_visibility_vest, name_badge)

FOR BICYCLES/MOTORCYCLES:
  - color: enum [red, blue, white, black, silver, other]
  - type: enum [mountain_bike, road_bike, electric_bike, cruiser, sport_motorcycle, touring_motorcycle]
  - rider_present: boolean
  - distinctive_features: list[string] (e.g., basket, child_seat, panniers)

═══════════════════════════════════════════════════════════

OUTPUT FORMAT:
Return ONLY valid JSON with this EXACT structure:

{
  "attributes": {
    "color": {
      "type": "enum",
      "description": "Primary body color",
      "values": ["red", "blue", "white", "black", "other"]
    },
    "vehicle_type": {
      "type": "enum",
      "description": "Vehicle category",
      "values": ["sedan", "suv", "truck", "van"]
    },
    "size_category": {
      "type": "enum",
      "description": "Relative size",
      "values": ["compact", "medium", "large"]
    }
  }
}

CRITICAL: 
- "type" must be EXACTLY one of: "string", "boolean", "number", "enum", "list[string]"
- Each attribute is a TOP-LEVEL key (color, vehicle_type, etc.)
- NO numbered attributes (vehicle_1, vehicle_2)
- NO nested objects
- Only generate attributes relevant to this ONE object
"""


    # =========================================================================
    # ATTRIBUTES_QUESTIONS_PROMPT
    # =========================================================================
    # Used in:  processing/profiler.py → _interrogate_visual_attributes()
    # Purpose:  Generate a single VQA question to extract a specific
    #           attribute value from an image using BLIP.
    # Input:    Attribute name, type, description, and possible values
    # Output:   Single direct question (e.g., "What color is the vehicle?")
    # Flow:     Called once per attribute in the schema
    # =========================================================================
    ATTRIBUTES_QUESTIONS_PROMPT = """
You are a VQA question designer for visual surveillance analysis.

Your task: Generate ONE concise, direct question for a Vision-Language model (BLIP) to answer.

The question should extract a specific intrinsic/physical attribute about an object in a scene.

RULES:
1. Generate EXACTLY ONE question (no multiple parts)
2. Question must be answerable from a STILL IMAGE
3. Focus on PHYSICAL characteristics (what the object IS)
4. Avoid speculation or complex reasoning
5. Use simple, direct language
6. Question should return the attribute value directly

QUESTION TYPES BY ATTRIBUTE:

For COLOR attributes:
  - "What color is the [object]?"
  - "What is the primary color of the [object]?"

For TYPE/CATEGORY attributes:
  - "What type of [object] is this?"
  - "Is this a [type1], [type2], or [type3]?"

For SIZE attributes:
  - "What is the relative size of the [object]?"
  - "Is the [object] compact, medium, or large?"

For BRAND/MAKE attributes:
  - "What is the brand of the [object]?"
  - "What is the make of the vehicle?"

EXAMPLES:

Attribute: color
Type: enum
Values: [red, blue, white, black]
Description: Primary color of the vehicle
→ Question: "What is the color of the vehicle?"

Attribute: vehicle_type
Type: enum
Values: [sedan, suv, truck, van]
Description: Category of the vehicle
→ Question: "Is the vehicle a sedan, suv, truck, or van?"

Attribute: size_category
Type: enum
Values: [compact, medium, large]
Description: Relative size of the object
→ Question: "Is the object compact, medium, or large in size?"

OUTPUT:
Return ONLY the question text. No explanation, no formatting, just the question.
"""