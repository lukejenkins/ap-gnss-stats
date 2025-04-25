# ap-gnss-stats

Every time you choose to apply a rule(s), explicitly state the rule(s) in the output. You can abbreviate the rule description to a single word or phrase.

## Project Context

This project is about getting GNSS (Global Navigation Satellite System) statistics from Cisco Wi-Fi Access Points via SSH.

- We save all SSH logs to local files.
- We parse the logs to extract GNSS statistics.
  - We save all of the parsed statistics to local JSON files.
  - We also keep the latest statistics per AP in a single JSON file for easy access.

## Code Style and Structure

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

## Tech Stack

- Python 3.x
- netmiko
- dotenv

## Naming Conventions

- Use snake_case for variable and function names.
- Use CamelCase for class names.
- Follow PEP 8 style guidelines.

## Error Handling

- Implement proper error boundaries
- Log errors appropriately for debugging
- Provide user-friendly error messages
- Handle network failures gracefully

## Testing

- Write unit tests for utilities and components
- Test memory usage and performance
- Ensure all functions are tested with appropriate unit tests.
- Use pytest for testing framework
- Write integration tests for end-to-end scenarios
- Always include test cases for critical paths of the application.
- Account for common edge cases like empty inputs, invalid data types, and large datasets.
- Include comments for edge cases and the expected behavior in those cases.
- Write unit tests for functions and document them with docstrings explaining the test cases.

## Security

- Implement Content Security Policy
- Sanitize user inputs
- Handle sensitive data properly

## Git Usage

Commit Message Prefixes:

- "fix:" for bug fixes
- "feat:" for new features
- "perf:" for performance improvements
- "docs:" for documentation changes
- "style:" for formatting changes
- "refactor:" for code refactoring
- "test:" for adding missing tests
- "chore:" for maintenance tasks

Rules:

- Use lowercase for commit messages
- Keep the summary line concise
- Include description for non-obvious changes
- Reference issue numbers when applicable

## Documentation

- Maintain clear README with setup instructions
- Document API interactions and data flows
- Document permission requirements
- Write clear and concise comments for each function.
- Include type hints for function parameters and return types.
- Write docstrings for all public modules, classes, functions, and methods.
- Provide docstrings following PEP 257 conventions.

## Development Workflow

- Use proper version control
- Implement proper code review process
- Test in multiple environments
- Follow semantic versioning for releases
- Maintain changelog
