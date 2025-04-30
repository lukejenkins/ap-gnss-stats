# AI Rules for ap-gnss-stats

- Write code with clear variable names and include explanatory comments for non-obvious logic. Avoid shorthand syntax and complex patterns.
- Provide full implementations rather than partial snippets. Include import statements, required dependencies, and initialization code.
- Add defensive coding patterns and clear error handling. Include validation for user inputs and explicit type checking.
- Suggest simpler solutions first, then offer more optimized versions with explanations of the trade-offs.
- Briefly explain why certain approaches are used and link to relevant documentation or learning resources.
- When suggesting fixes for errors, explain the root cause and how the solution addresses it to build understanding. Ask for confirmation before proceeding.
- Offer introducing basic test cases that demonstrate how the code works and common edge cases to consider.
- Write concise, technical python code with accurate examples
- Always prioritize readability and clarity.
- Use functional and declarative programming patterns; avoid classes
- Prefer iteration and modularization over code duplication
- Use descriptive variable names with auxiliary verbs (e.g., isLoading, hasError)
- Use the `typing` module for type annotations (e.g., `List[str]`, `Dict[str, int]`).
- Break down complex functions into smaller, more manageable functions.
- Write code with good maintainability practices, including comments on why certain design decisions were made.
- Handle edge cases and write clear exception handling.
- For libraries or external dependencies, mention their usage and purpose in comments.
- Use consistent naming conventions and follow language-specific best practices.
- Write concise, efficient, and idiomatic code that is also easily understandable.

## PYTHON_GUIDELINES

### Code Style & Standards

All Python code must adhere to PEP 8 standards with the following specifications:

- Line length: maximum 88 characters (Black default)
- Indentation: 4 spaces, no tabs
- Naming conventions:
  - `snake_case` for variables, functions, methods, modules
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
  - Private attributes/methods prefixed with underscore (`_private_method`)
- String quotes: prefer double quotes (`"`) for strings
- Provide docstrings following PEP 257 conventions.
- Docstrings: Google style format for all modules, classes, and functions

## Tech Stack

- Python 3.x
- netmiko
- dotenv
- aiofiles
