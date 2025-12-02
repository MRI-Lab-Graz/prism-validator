# Survey Library & Workflow

The **Survey Library** is a centralized repository for "Golden Master" questionnaire templates. It ensures consistency across studies by providing a single source of truth for survey definitions (questions, scales, metadata).

## Workflow Overview

The library operates on a **Draft & Publish** model, similar to Git, to prevent accidental changes to production templates.

### 1. Golden Masters (Read-Only)
*   Files in the root `survey_library/` folder are **Golden Masters**.
*   They are **read-only** and cannot be edited directly.
*   These files represent the approved, validated versions of questionnaires.

### 2. Checkout & Edit (Drafts)
*   To make changes, you must **Checkout** a survey.
*   This creates a copy in the `survey_library/drafts/` folder.
*   You can edit the draft using the built-in **Simple Editor** (GUI) or the **Advanced JSON Editor**.
*   The editor supports:
    *   **Metadata**: Description, Units, Data Type.
    *   **Ranges**: Absolute Min/Max and "Normal" (Warning) Min/Max.
    *   **Questions**: Adding, removing, and reordering items.

### 3. Validation & Submission
*   When your edits are complete, click **Submit**.
*   **Automated Validation**: The system checks your draft against the entire library to ensure **variable uniqueness**.
    *   *Example*: If you define a variable `age` that already exists in another survey with a different definition, the submission is blocked.
*   **Merge Request**: If validation passes, the draft is moved to `survey_library/merge_requests/`.
*   A repository maintainer must then review and manually move the file to the root folder to update the Golden Master.

## Web Interface

The Survey Library is fully integrated into the Prism-Validator web interface:

1.  **Library Dashboard**: View all surveys, their status (Live/Draft), and perform actions (Checkout, Edit, Submit).
2.  **Editor**: A user-friendly form-based editor for modifying survey content.
3.  **Survey Export**: Select multiple questionnaires from the library and export them as a single LimeSurvey (`.lss`) file for data collection.

## Directory Structure

```
survey_library/
├── survey-bdi.json          # Golden Master (Live)
├── survey-ads.json          # Golden Master (Live)
├── drafts/
│   └── survey-ads.json      # Work-in-progress draft
└── merge_requests/
    └── survey-new.json      # Submitted for review
```
