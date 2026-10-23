# sample_resumes/

This directory holds **synthetic** resume files used for development and testing only.

## Rules

- **Never commit real people's resumes.** Real resumes are excluded by `.gitignore`.
- All files placed here should be generated or invented for testing purposes.
- The directory is intentionally empty when the repository is cloned.

## Generating test files

Run the helper from the project root:

```powershell
python tests/create_test_files.py
```

This creates a small set of synthetic PDF and DOCX resumes inside `sample_resumes/`.
