# playbooks.ai - AI Agents for Humans

## Overview

Playbooks.ai is an innovative open-source project that empowers anyone to create AI agents using human-readable and LLM-understandable playbooks. Our platform simplifies the process of designing, deploying, and managing AI agents, making it accessible to both technical and non-technical users.

### Key Features

- **Powerful AI Agents**: Write simple playbooks to create powerful AI agents.
- **Voltron AI Assistant**: Voltron is an AI agent that helps you write and update playbooks.
- **Web-based Studio App**: Comprehensive environment to create, edit, debug, improve and deploy playbooks based AI agents.
- **Playbooks Hub**: Community-driven platform for sharing and discovering playbooks.
- **Interactive Demo**: Try out playbook editing and execution on our website [runplaybooks.ai](https://runplaybooks.ai).

## Getting Started

### Writing Playbooks

Playbooks are written in a structured markdown format. Here's a simple example:

```markdown
# AuthenticateUser()

## Trigger
When user authentication is required.

## Steps
- Request last 4 digits of SSN and account number from user.
- $auth_token = AuthMethod1($last_4_ssn, $account_number)
- If $auth_token is valid:
   - $user_name, $account_number = LoadAccount($auth_token)
   - Return ($user_name, $account_number)
- Else:
   - Apologize and offer alternative authentication method.
   - Request email, last 4 digits of credit card, and zip code.
   - $auth_token = AuthMethod2($email, $last_4_cc, $zip_code)
   - If $auth_token is valid:
     - $user_name, $account_number = LoadAccount($auth_token)
     - Return ($user_name, $account_number)
   - Else:
     - Apologize for unsuccessful authentication.
     - Offer to connect with a human agent.
     - ConnectWithHumanAgent()
     - Return

## Notes
- Ensure proper error handling for API calls.
- Consider implementing a retry mechanism for failed authentications.
```

### Playbook Language Specification

- **Playbook Name and Parameters**: Use H1 header (`#`). Format: `# PlaybookName(param1, param2, ...)`
- **Sections**: Use H2 headers (`##`) for Trigger, Steps, and Notes.
- **Variables**: Prefix with `$` symbol (e.g., `$variable_name`).
- **Function Calls**: `FunctionName(param1, param2, ...)`
- **Playbook Calls**: `play PlaybookName(param1, param2, ...)`
- **Logic Structure**: Use If, Else, For loops, and Return statements.

### Project Configuration

Projects are configured using a JSON file. Example:

```json
{
  "project_name": "Bank Customer Support Agent",
  "description": "AI agent for handling bank customer inquiries",
  "version": "1.0.0",
  "functions": [
    {
      "name": "AuthMethod1",
      "description": "Primary user authentication method",
      "type": "http",
      "url": "https://api.example.com/auth/method1",
      "method": "POST",
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "last_4_ssn": "$last_4_ssn",
        "account_number": "$account_number"
      }
    }
  ]
}
```

## Web-based Studio App

Our studio app provides a comprehensive environment for AI agent development:

- User, project, and organization management
- Environment management (dev, prod, etc.)
- Version control and deployment
- Authentication and authorization
- Interactive playbook editor
- Voltron AI assistant for playbook creation and editing
- Sandbox environment for testing and debugging
- Git-backed version control
- External tool/function configuration

## Community and Collaboration

Join our vibrant community on the Playbooks Hub:

- Discover and share playbooks
- Collaborate on projects
- Learn from other developers and AI enthusiasts

## Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get involved.

## Support

If you find playbooks.ai useful, consider supporting the project:

- Star us on [GitHub](https://github.com/playbooks-ai/playbooks-ai)
- [Donate](https://playbooks.ai/donate) to support ongoing development

## License

Playbooks.ai is open-source software licensed under the [MIT license](LICENSE).
