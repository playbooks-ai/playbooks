# Playbooks
A framework for creating AI agents using human-readable and LLM-executed playbooks.

## Quick start

It all starts with a playbook. Here is an example playbook -

- Create hello.md with the following playbook

```
# HelloWorld

## Trigger
When the user starts a conversation or asks for a greeting.

## Steps
- Greet the user with a friendly "Hello, World!" message.
- Explain that this is a demonstration of a simple Hello World playbook.
- Say goodbye to the user.
```

- Run the playbook

```bash
pip install playbooks
playbooks run hello.md
```

Now, try modifying the hello.md playbook to greet the user with "Hello Playbooks!" instead and give it a try. Easy, right?

Now take a look at some example playbooks in examples folder. Try writing your own playbooks. Don't worry, the syntax is quite flexible and forgiving.

## Why playbooks?

It all started with a simple question - Why can't we train AI agents just like we train human agents using training material that gives them basic information and a few playbooks to follow?

One of the biggest challenges in building and using AI agents today is the difficulty specifying and modifying agent behavior. If agents are configured using code, it is hard for business users to make changes. On the other hand, if a UI based configuration system is used, such systems typically lack fluidity and offer limited customizability, which makes them not suitable for Enterprise use. One can be brave and write complex prompts to configure agents, but LLMs cannot follow such prompts faithfully! Can't use code, can't use UI builders, can't use complex prompts - what can we do?

We need a mechanism to configure AI agents that is easy to understand and modify, leverages LLM's ability to make intelligent decisions, while ensuring adherance to the provided guidelines.

Playbooks is the perfect middle ground. Agent behavior is written in an easily readable English-like pseudocode, and the framework takes care of advanced capabilities like 
- ensuring proper step by step control flow, 
- calling internal (other playbooks) and external (APIs) tools, 
- managing complex behaviors written using 100s or 1000s of playbooks, 
- multi-agent communication, 
- external event triggered playbooks, and so on. 

Not only that, business users can use a copilot that can transparently make changes to the playbooks on their behalf, enabling them to easily make changes to agent behavior, such as listing caveats and special cases, adding new business logic, and so on.

## Contributing

Welcome to the Playbooks community! We're excited to have you contribute. 

If you want to help, checkout some of the issues marked as `good-first-issue` or `help-wanted` found [here](https://github.com/playbooks-ai/playbooks/labels/good%20first%20issue). They could be anything from code improvements, a guest blog post, or a new cookbook.

### Development Environment Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/playbooks-ai/playbooks.git
   cd playbooks
   ```

2. **Install Dependencies**
   ```bash
   # Install Python dependencies
   pip install -r api/requirements.txt
   pip install -r requirements.txt

   # Install Node.js dependencies for the website
   cd website
   npm install
   cd ..
   ```

3. **Environment Variables**
   Create a `.env` file in the root directory:
   ```bash
   ANTHROPIC_API_KEY=your_api_key_here
   ```

4. **Docker Setup (Optional)**
   ```bash
   # Build and start containers
   docker-compose up --build
   ```

### Running the Development Server

1. **Start the FastAPI Server**
   ```bash
   cd playbooks
   uvicorn api.main:app --reload
   ```

2. **Start the Next.js Website**
   ```bash
   cd website
   npm run dev
   ```

The API will be available at `http://localhost:8000` and the website at `http://localhost:3000`.

### Testing

We maintain high test coverage to ensure code quality. Here's what you need to know:

1. **Running Tests**
   ```bash
   # Run all tests
   pytest

   # Run specific test file
   pytest tests/test_runner.py

   # Run with coverage report
   pytest --cov=playbooks tests/ --cov-report=term-missing
   ```

2. **Test Guidelines**
   - Write tests for all new features
   - Maintain test coverage above 80%
   - Use meaningful test names that describe the behavior being tested
   - Mock external dependencies (e.g., LLM API calls)

3. **Coverage Requirements**
   We use `pytest-cov` to track code coverage. Aim for 80+% coverage.

4. **Writing Tests**
   - Use `pytest` fixtures for setup/teardown
   - Use `pytest.mark.parametrize` for testing multiple inputs
   - Mock LLM API calls using `pytest-mock`
   ```python
   def test_anthropic_generate(mocker):
       mock_client = mocker.patch('anthropic.Anthropic')
       mock_client.return_value.messages.create.return_value = ...
       llm = AnthropicLLM(api_key="test")
       result = llm.generate("test prompt")
       assert result == expected_output
   ```

### Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow the existing code style
   - Add/update tests as needed
   - Update documentation if required

3. **Commit Guidelines**
   - Use clear, descriptive commit messages
   - Reference issue numbers in commit messages
   - Keep commits focused and atomic

4. **Submit PR**
   - Create a pull request against the `main` branch
   - Fill out the PR template completely
   - Add relevant labels
   - Request review from maintainers

5. **PR Checklist**
   - [ ] Tests pass
   - [ ] Code follows style guidelines
   - [ ] Documentation is updated
   - [ ] Changes are tested locally
   - [ ] PR description explains changes and motivation
   - [ ] Test coverage is maintained or improved

### Code Style Guidelines

- Follow PEP 8 for Python code
- Use type hints for Python functions
- Follow React/Next.js best practices for frontend code
- Document public APIs and complex logic
- Keep functions focused and under 50 lines when possible

### Getting Help

- Join our [Discord community](https://discord.com/channels/1320659147133423667/1320659147133423670)
- Check existing issues and discussions
- Reach out to maintainers

We appreciate your contributions to making Playbooks better! If you have any questions, don't hesitate to ask.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 

# Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

<a href="https://github.com/playbooks-ai/playbooks/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=playbooks-ai/playbooks" />
</a>