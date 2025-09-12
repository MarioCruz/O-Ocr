#!/usr/bin/env python3
"""Simple script to edit custom poem settings"""

import json
import os

def edit_custom_settings():
    settings_file = 'custom_poem_settings.json'
    
    # Load current settings
    try:
        with open(settings_file, 'r') as f:
            data = json.load(f)
        settings = data['custom_poem']
    except (FileNotFoundError, KeyError):
        settings = {
            "name": "Custom Poem",
            "description": "User-defined poem structure and content",
            "structure": "Free verse with custom requirements",
            "document_contains": ["Student name", "School name", "Poem text"],
            "prompt_template": "Transcribe everything in this image including {document_contains}. Preserve exact formatting, line breaks, and punctuation. Use [?] for unclear words. At the end, add exactly these lines:\nPOEM_TITLE: [actual title]\nPOEM_THEME: [theme]\nPOEM_LANGUAGE: [language]\nCUSTOM_STRUCTURE: {structure}\nConfidence: X/10"
        }
    
    print("Current Custom Poem Settings:")
    print(f"Name: {settings['name']}")
    print(f"Description: {settings['description']}")
    print(f"Structure: {settings['structure']}")
    print(f"Document Contains: {', '.join(settings['document_contains'])}")
    print()
    
    # Edit settings
    settings['name'] = input(f"Name [{settings['name']}]: ") or settings['name']
    settings['description'] = input(f"Description [{settings['description']}]: ") or settings['description']
    settings['structure'] = input(f"Poem Structure [{settings['structure']}]: ") or settings['structure']
    
    print("Document Contains (comma-separated):")
    current_contains = ', '.join(settings['document_contains'])
    new_contains = input(f"[{current_contains}]: ") or current_contains
    settings['document_contains'] = [item.strip() for item in new_contains.split(',')]
    
    # Update prompt template
    settings['prompt_template'] = (
        "Transcribe everything in this image including {document_contains}. "
        "Preserve exact formatting, line breaks, and punctuation. "
        "Use [?] for unclear words. At the end, add exactly these lines:\n"
        "POEM_TITLE: [actual title]\n"
        "POEM_THEME: [theme]\n"
        "POEM_LANGUAGE: [language]\n"
        "CUSTOM_STRUCTURE: {structure}\n"
        "Confidence: X/10"
    )
    
    # Save settings
    data = {'custom_poem': settings}
    with open(settings_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSettings saved to {settings_file}")

if __name__ == '__main__':
    edit_custom_settings()